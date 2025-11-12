"""
SharePoint contract download service using Microsoft Graph API.
Downloads contract files and returns temporary file paths.
"""
import os
import logging
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Tuple
import requests
from flask import session

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Base exception for download failures."""
    pass


def _get_bearer_token() -> str:
    """
    Retrieve bearer token from Flask session and check if it's expired.
    
    Raises:
        PermissionError: If token is missing or expired.
    """
    from datetime import datetime
    
    token = session.get('access_token')
    
    if not token:
        logger.warning("No access token found in session")
        raise PermissionError("SESSION_EXPIRED")
    
    # Check if token is expired (if expiration time is stored)
    token_expires_str = session.get('token_expires_at')
    if token_expires_str:
        try:
            token_expires_at = datetime.fromisoformat(token_expires_str)
            if datetime.utcnow() >= token_expires_at:
                logger.warning("Access token has expired")
                print(f"DEBUG sp_download: Token expired at {token_expires_at} UTC")
                raise PermissionError("SESSION_EXPIRED")
            else:
                time_left = (token_expires_at - datetime.utcnow()).total_seconds() / 60
                print(f"DEBUG sp_download: Token valid for {time_left:.1f} more minutes")
        except ValueError as e:
            logger.warning(f"Could not parse token expiration: {e}")
            # Continue with token anyway - API will reject if expired
    
    return token


def _attempt_token_refresh() -> str:
    """
    Attempt to refresh the access token using MSAL silent acquisition.
    
    Returns:
        New access token if successful.
    
    Raises:
        PermissionError: If refresh fails or user needs to re-authenticate.
    """
    try:
        from flask import current_app
        import msal
        
        # Get user email from session
        user_email = session.get('user_email')
        if not user_email:
            logger.warning("Cannot refresh token: no user_email in session")
            raise PermissionError("SESSION_EXPIRED")
        
        # Create MSAL app
        msal_app = msal.ConfidentialClientApplication(
            current_app.config['CLIENT_ID'],
            authority=current_app.config['AUTHORITY'],
            client_credential=current_app.config['CLIENT_SECRET']
        )
        
        # Attempt silent token acquisition
        accounts = msal_app.get_accounts(username=user_email)
        if accounts:
            logger.info(f"Attempting silent token refresh for {user_email}")
            print(f"DEBUG sp_download: Attempting silent token refresh")
            result = msal_app.acquire_token_silent(
                scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"],
                account=accounts[0]
            )
            
            if result and 'access_token' in result:
                # Update session with new token
                session['access_token'] = result['access_token']
                logger.info("Successfully refreshed access token")
                print(f"DEBUG sp_download: Token refreshed successfully")
                return result['access_token']
        
        logger.warning("Silent token refresh failed - user needs to re-authenticate")
        print(f"DEBUG sp_download: Silent token refresh failed")
        raise PermissionError("SESSION_EXPIRED")
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        print(f"DEBUG sp_download: Token refresh error: {str(e)}")
        raise PermissionError("SESSION_EXPIRED")


def _extract_item_id_from_url(document_url: str) -> str:
    """
    Extract SharePoint item unique ID from document URL.
    
    SharePoint document URLs contain the item ID in the sourcedoc parameter:
    https://.../_layouts/15/Doc.aspx?sourcedoc=%7BGUID%7D&file=...
    
    Args:
        document_url: SharePoint document URL
    
    Returns:
        Item unique ID (GUID without braces)
    
    Raises:
        ValueError: If URL format is invalid or item ID cannot be extracted
    """
    import urllib.parse
    
    try:
        # Parse URL and extract query parameters
        parsed = urllib.parse.urlparse(document_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Get sourcedoc parameter (URL-encoded GUID)
        sourcedoc = query_params.get('sourcedoc', [None])[0]
        if not sourcedoc:
            raise ValueError("No sourcedoc parameter in URL")
        
        # URL decode the GUID (e.g., %7B...%7D becomes {...})
        decoded_guid = urllib.parse.unquote(sourcedoc)
        
        # Remove braces if present
        item_id = decoded_guid.strip('{}')
        
        logger.debug(f"Extracted item ID from URL: {item_id}")
        return item_id
        
    except Exception as e:
        logger.error(f"Failed to extract item ID from URL: {str(e)}")
        raise ValueError(f"Invalid document URL format: {str(e)}")


def _verify_drive_access(drive_id: str, token: str) -> dict:
    """
    Verify that the drive exists and is accessible with the current token.
    
    Args:
        drive_id: The SharePoint drive ID to verify
        token: Bearer token for authorization
    
    Returns:
        dict: Drive information if accessible
    
    Raises:
        RuntimeError: If drive is not accessible
    """
    graph_base = "https://graph.microsoft.com/v1.0"
    drive_url = f"{graph_base}/drives/{drive_id}"
    
    print(f"DEBUG sp_download: Verifying drive access: {drive_url}")
    logger.info(f"Verifying drive access for drive_id: {drive_id}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(drive_url, headers=headers, timeout=10)
        print(f"DEBUG sp_download: Drive verification response: {response.status_code}")
        
        if response.status_code == 200:
            drive_info = response.json()
            drive_name = drive_info.get('name', 'Unknown')
            drive_type = drive_info.get('driveType', 'Unknown')
            print(f"DEBUG sp_download: ✓ Drive accessible - Name: '{drive_name}', Type: {drive_type}")
            logger.info(f"Drive verified: name={drive_name}, type={drive_type}")
            return drive_info
        elif response.status_code == 401:
            error_msg = response.text[:200]
            print(f"DEBUG sp_download: ✗ 401 accessing drive: {error_msg}")
            raise RuntimeError(f"401 Unauthorized accessing drive. Token may lack permissions. Error: {error_msg}")
        elif response.status_code == 404:
            print(f"DEBUG sp_download: ✗ 404 - Drive not found")
            raise RuntimeError(f"Drive ID not found: {drive_id}. Check DRIVE_ID in .env file.")
        else:
            error_msg = response.text[:200]
            print(f"DEBUG sp_download: ✗ Drive access failed: {response.status_code} - {error_msg}")
            raise RuntimeError(f"Cannot access drive: HTTP {response.status_code}")
    except requests.RequestException as e:
        print(f"DEBUG sp_download: ✗ Request exception: {str(e)}")
        raise RuntimeError(f"Network error verifying drive: {str(e)}")


def _get_contract_metadata(contract_id: str, token: str) -> Tuple[str, str, str, str]:
    """
    Get contract file metadata from SharePoint.
    
    Returns:
        Tuple of (drive_id, item_id, server_relative_path, file_extension)
    
    Raises:
        FileNotFoundError: If contract not found.
        RuntimeError: On API errors.
    """
    from app.services.sharepoint_service import SharePointService
    
    try:
        sp_service = SharePointService()
        contract = sp_service.get_contract_by_id(contract_id)
        
        if not contract:
            raise FileNotFoundError(f"Contract {contract_id} not found")
        
        # Try to get file location from stored fields (legacy approach)
        drive_id = contract.get('fields', {}).get('DriveId')
        item_id = contract.get('fields', {}).get('ItemId')
        server_relative_path = contract.get('fields', {}).get('ServerRelativePath')
        
        print(f"DEBUG sp_download: Initial metadata - drive_id={drive_id}, item_id={item_id}, server_relative_path={server_relative_path}")
        
        # If item_id not found in fields, extract from Document_x0020_Link URL
        if not item_id:
            document_url = contract.get('document_url') or contract.get('fields', {}).get('Document_x0020_Link')
            print(f"DEBUG sp_download: Attempting to extract item ID from URL")
            print(f"DEBUG sp_download: document_url = {document_url}")
            logger.debug(f"Attempting to extract item ID from document_url: {document_url}")
            if document_url:
                try:
                    item_id = _extract_item_id_from_url(document_url)
                    print(f"DEBUG sp_download: Successfully extracted item_id = {item_id}")
                    logger.info(f"Extracted item ID from document URL: {item_id}")
                except ValueError as e:
                    print(f"DEBUG sp_download: Failed to extract item ID: {e}")
                    logger.warning(f"Could not extract item ID from URL: {e}")
            else:
                print(f"DEBUG sp_download: No document_url found in contract data")
                logger.warning("No document_url found in contract data")
        
        # Get file extension from filename
        file_name = contract.get('file_name') or contract.get('fields', {}).get('filename', 'contract.docx')
        file_ext = os.path.splitext(file_name)[1] or '.docx'
        
        logger.info(f"Contract metadata retrieved: contract_id={contract_id}, has_drive_id={bool(drive_id)}, has_item_id={bool(item_id)}")
        
        return drive_id, item_id, server_relative_path, file_ext
        
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve contract metadata: {str(e)}")
        raise RuntimeError("Failed to retrieve contract information")


def _download_file_content(url: str, token: str, retry_with_refresh: bool = True) -> bytes:
    """
    Download file content from Microsoft Graph with token refresh on 401.
    
    Args:
        url: Microsoft Graph API URL to download from.
        token: Bearer token for authorization.
        retry_with_refresh: If True and 401 received, attempt token refresh and retry once.
    
    Raises:
        PermissionError: On 401 status after token refresh attempt.
        FileNotFoundError: On 404 status.
        RuntimeError: On other HTTP errors or permission issues.
    """
    print(f"DEBUG sp_download: Downloading from URL: {url}")
    logger.info(f"Attempting download from: {url}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/octet-stream'
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=(5, 30),  # connect timeout 5s, read timeout 30s
            stream=True
        )
        
        print(f"DEBUG sp_download: Download response status: {response.status_code}")
        
        # For non-200 responses, try to get error details
        if not response.ok:
            try:
                error_body = response.text
                print(f"DEBUG sp_download: Error response body: {error_body[:500]}")
                logger.error(f"Graph API error: {error_body[:500]}")
            except:
                pass
        
        # Handle specific status codes
        if response.status_code == 401:
            logger.warning("Received 401 Unauthorized during download")
            print(f"DEBUG sp_download: 401 Unauthorized, retry_with_refresh={retry_with_refresh}")
            
            if retry_with_refresh:
                # Attempt to refresh the token and retry once
                try:
                    print(f"DEBUG sp_download: Attempting token refresh after 401")
                    new_token = _attempt_token_refresh()
                    # Retry download with refreshed token (no further refresh attempts)
                    return _download_file_content(url, new_token, retry_with_refresh=False)
                except PermissionError:
                    # Token refresh failed, user needs to re-authenticate
                    raise PermissionError("SESSION_EXPIRED")
            else:
                # Already tried refresh, this is a permissions issue
                logger.error("401 after token refresh - likely a permissions issue")
                print(f"DEBUG sp_download: 401 persists after token refresh")
                raise RuntimeError(
                    "Access denied to contract file. This may be a SharePoint permissions issue. "
                    "Please verify the file is accessible and the app has the required permissions."
                )
        
        elif response.status_code == 404:
            logger.debug(f"File not found at URL (404)")
            print(f"DEBUG sp_download: 404 Not Found")
            raise FileNotFoundError("File not found at this URL")
        
        elif response.status_code == 403:
            logger.error(f"403 Forbidden - insufficient permissions")
            print(f"DEBUG sp_download: 403 Forbidden")
            raise RuntimeError(
                "Insufficient permissions to access the file. "
                "The file may require special SharePoint permissions."
            )
        
        elif response.status_code in (429, 503):
            logger.warning(f"Received {response.status_code}, rate limited or service unavailable")
            print(f"DEBUG sp_download: {response.status_code} - will retry")
            raise RuntimeError(f"SharePoint service temporarily unavailable ({response.status_code})")
        
        elif not response.ok:
            logger.error(f"Download failed with status {response.status_code}")
            print(f"DEBUG sp_download: Download failed with status {response.status_code}")
            raise RuntimeError(f"Failed to download contract file (HTTP {response.status_code})")
        
        print(f"DEBUG sp_download: Download successful, content length: {len(response.content)} bytes")
        return response.content
        
    except requests.Timeout:
        logger.error("Download request timed out")
        print(f"DEBUG sp_download: Request timed out")
        raise RuntimeError("Download request timed out")
    except (PermissionError, FileNotFoundError, RuntimeError):
        # Re-raise our custom exceptions
        raise
    except requests.RequestException as e:
        logger.error(f"Download request failed: {type(e).__name__}: {str(e)}")
        print(f"DEBUG sp_download: Request exception: {type(e).__name__}")
        raise RuntimeError("Failed to download contract file")


def download_contract(contract_id: str) -> Path:
    """
    Download a contract file from SharePoint using delegated user token.
    
    Tries multiple URL patterns in sequence to locate the file:
    1. Direct path in ContractFiles drive (matches upload location)
    2. Drive item ID (if available from metadata)
    3. Site default drive with item ID
    4. Contracts subfolder in ContractFiles drive
    
    Args:
        contract_id: The SharePoint list item ID.
    
    Returns:
        Path to the temporary file containing the contract.
    
    Raises:
        PermissionError: If session token is missing or expired.
        FileNotFoundError: If contract file not found after all attempts.
        RuntimeError: On other download failures.
    """
    start_time = time.time()
    
    try:
        # Get bearer token from session
        token = _get_bearer_token()
        
        # Get contract metadata
        from app.services.sharepoint_service import SharePointService
        sp_service = SharePointService()
        contract = sp_service.get_contract_by_id(contract_id)
        
        if not contract:
            raise FileNotFoundError(f"Contract {contract_id} not found in SharePoint list")
        
        # Extract metadata
        file_name = contract.get('file_name', 'contract.docx')
        file_ext = os.path.splitext(file_name)[1] or '.docx'
        document_url = contract.get('document_url') or contract.get('fields', {}).get('Document_x0020_Link')
        
        # Try to extract item ID from URL
        item_id = None
        if document_url:
            try:
                item_id = _extract_item_id_from_url(document_url)
                print(f"DEBUG sp_download: Extracted item_id = {item_id}")
                logger.info(f"Extracted item ID from URL: {item_id}")
            except ValueError as e:
                print(f"DEBUG sp_download: Could not extract item ID: {e}")
                logger.warning(f"Could not extract item ID: {e}")
        
        # Get configuration
        graph_base = "https://graph.microsoft.com/v1.0"
        drive_id = os.getenv('DRIVE_ID', '')  # ContractFiles library drive
        site_id = os.getenv('O365_SITE_ID', '')
        
        print(f"DEBUG sp_download: Metadata - file_name={file_name}, item_id={item_id}")
        print(f"DEBUG sp_download: Config - drive_id={drive_id[:20]}..., site_id={site_id}")
        
        # === OPTION D: Verify drive access before attempting download ===
        if drive_id:
            try:
                drive_info = _verify_drive_access(drive_id, token)
                print(f"DEBUG sp_download: Drive verification successful")
            except RuntimeError as e:
                print(f"DEBUG sp_download: Drive verification failed: {str(e)}")
                logger.error(f"Drive verification failed: {str(e)}")
                # Don't fail completely - continue with attempts but warn user
                print(f"DEBUG sp_download: Continuing with download attempts despite drive verification failure")
        
        # Build list of URLs to try (in order of likelihood)
        download_attempts = []
        
        # Method 1: Direct path in ContractFiles drive (MOST LIKELY - matches upload)
        if drive_id and file_name:
            url = f"{graph_base}/drives/{drive_id}/root:/{file_name}:/content"
            download_attempts.append(("ContractFiles root path", url))
        
        # Method 2: Drive item ID (if available from legacy metadata)
        drive_id_meta = contract.get('fields', {}).get('DriveId')
        item_id_meta = contract.get('fields', {}).get('ItemId')
        if drive_id_meta and item_id_meta:
            url = f"{graph_base}/drives/{drive_id_meta}/items/{item_id_meta}/content"
            download_attempts.append(("Drive item ID (metadata)", url))
        
        # Method 3: ContractFiles drive with extracted item ID
        if drive_id and item_id:
            url = f"{graph_base}/drives/{drive_id}/items/{item_id}/content"
            download_attempts.append(("ContractFiles drive with item ID", url))
        
        # Method 4: Site default drive with item ID
        if site_id and item_id:
            url = f"{graph_base}/sites/{site_id}/drive/items/{item_id}/content"
            download_attempts.append(("Site default drive with item ID", url))
        
        # Method 5: Contracts subfolder in ContractFiles drive
        if drive_id and file_name:
            url = f"{graph_base}/drives/{drive_id}/root:/Contracts/{file_name}:/content"
            download_attempts.append(("Contracts subfolder", url))
        
        if not download_attempts:
            raise RuntimeError(
                f"Cannot construct download URLs: missing required configuration. "
                f"Need DRIVE_ID={bool(drive_id)}, file_name={bool(file_name)}"
            )
        
        print(f"DEBUG sp_download: Will try {len(download_attempts)} URL patterns")
        
        # Try each URL pattern in sequence
        last_error = None
        for attempt_num, (method_name, url) in enumerate(download_attempts, 1):
            try:
                print(f"DEBUG sp_download: Attempt {attempt_num}/{len(download_attempts)}: {method_name}")
                print(f"DEBUG sp_download: URL: {url}")
                logger.info(f"Download attempt {attempt_num}: {method_name}")
                
                # Attempt download (with token refresh on 401)
                content = _download_file_content(url, token, retry_with_refresh=True)
                
                # Success! Save to temporary file
                temp_file = NamedTemporaryFile(mode='wb', suffix=file_ext, delete=False)
                temp_file.write(content)
                temp_file.flush()
                temp_file.close()
                
                duration = time.time() - start_time
                size_kb = len(content) / 1024
                
                print(f"DEBUG sp_download: ✓ SUCCESS with {method_name}")
                logger.info(
                    f"Contract downloaded successfully: contract_id={contract_id}, "
                    f"method={method_name}, size={size_kb:.1f}KB, duration={duration:.2f}s"
                )
                
                return Path(temp_file.name)
                
            except FileNotFoundError as e:
                # 404 - file not at this URL, try next
                print(f"DEBUG sp_download: ✗ 404 Not Found, trying next URL...")
                logger.debug(f"Attempt {attempt_num} failed: {method_name} - {str(e)}")
                last_error = e
                continue
                
            except PermissionError:
                # Authentication failure - don't continue trying
                raise
                
            except RuntimeError as e:
                # Other error (403, timeout, etc.) - log and try next
                error_msg = str(e)
                if "401 after token refresh" in error_msg or "403 Forbidden" in error_msg:
                    # Permission issue - don't continue
                    raise
                print(f"DEBUG sp_download: ✗ Error: {error_msg}, trying next URL...")
                logger.debug(f"Attempt {attempt_num} failed: {method_name} - {error_msg}")
                last_error = e
                continue
        
        # All attempts failed
        print(f"DEBUG sp_download: All {len(download_attempts)} download attempts failed")
        logger.error(f"Failed to download contract after {len(download_attempts)} attempts")
        raise FileNotFoundError(
            f"Contract file not found at any expected location. "
            f"Tried {len(download_attempts)} different URLs. "
            f"Last error: {last_error}"
        )
        
    except (PermissionError, FileNotFoundError):
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Download failed: contract_id={contract_id}, duration={duration:.2f}s, error={type(e).__name__}")
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError("An unexpected error occurred during download")


def download_contract_by_filename(drive_id: str, filename: str) -> bytes:
    """
    Download a contract file by filename from SharePoint drive.
    
    Args:
        drive_id: SharePoint drive ID
        filename: Name of the file to download
    
    Returns:
        bytes: File content
    
    Raises:
        FileNotFoundError: If file not found
        PermissionError: If SESSION_EXPIRED or access denied
        DownloadError: If download fails for other reasons
    """
    token = _get_bearer_token()
    
    # Download URL: /drives/{driveId}/root:/{filename}:/content
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{filename}:/content"
    
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"DEBUG sp_download: Downloading file by name: {filename}")
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            print(f"DEBUG sp_download: ✓ Download successful - {len(response.content)} bytes")
            return response.content
        elif response.status_code == 404:
            raise FileNotFoundError(f"File not found: {filename}")
        elif response.status_code == 401:
            raise PermissionError("SESSION_EXPIRED")
        else:
            error_msg = f"Download failed: HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg += f" - {error_data['error'].get('message', 'Unknown error')}"
            except:
                pass
            raise DownloadError(error_msg)
    
    except requests.exceptions.RequestException as e:
        raise DownloadError(f"Network error: {str(e)}")
