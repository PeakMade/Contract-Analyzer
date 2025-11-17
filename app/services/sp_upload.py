"""
SharePoint file upload service using delegated user authentication.
"""

from typing import Dict
import requests
from flask import session
import os

print("\n=== DEBUG: sp_upload.py module loaded ===")


class UploadError(Exception):
    """Raised when file upload to SharePoint fails."""
    pass


def _get_bearer_token() -> str:
    """
    Get bearer token from Flask session.
    
    Returns:
        Bearer token string
    
    Raises:
        PermissionError: If token not found in session
    """
    print(f"\n=== DEBUG _get_bearer_token ===")
    print(f"Session keys: {list(session.keys())}")
    
    access_token = session.get('access_token')
    if not access_token:
        print(f"✗ ERROR: No access_token in session")
        raise PermissionError("SESSION_EXPIRED")
    
    print(f"✓ Token found (length: {len(access_token)})")
    return access_token


def upload_file(
    drive_id: str,
    folder_path: str,
    filename: str,
    content: bytes
) -> Dict:
    """
    Upload a file to SharePoint using delegated user token.
    
    Args:
        drive_id: SharePoint drive ID
        folder_path: Folder path within drive (e.g., "Contracts" or "" for root)
        filename: Name for the uploaded file
        content: File content as bytes
    
    Returns:
        Dict with upload response containing 'id', 'name', 'webUrl', etc.
    
    Raises:
        PermissionError: If SESSION_EXPIRED
        UploadError: If upload fails (network, permissions, etc.)
    """
    print(f"\n{'='*60}")
    print(f"=== DEBUG upload_file ===")
    print(f"{'='*60}")
    print(f"Drive ID: {drive_id}")
    print(f"Folder path: '{folder_path}'")
    print(f"Filename: {filename}")
    print(f"Content size: {len(content):,} bytes")
    
    token = _get_bearer_token()
    
    # Construct upload URL
    # Format: /drives/{driveId}/root:/{folder_path}/{filename}:/content
    # URL encode only the filename to handle spaces and special characters
    from urllib.parse import quote
    
    print(f"\n=== DEBUGGING URL CONSTRUCTION ===")
    print(f"Raw filename: '{filename}'")
    print(f"Filename length: {len(filename)}")
    print(f"Folder path: '{folder_path}'")
    print(f"Drive ID: '{drive_id}'")
    
    # URL encode the filename (not the path separators)
    encoded_filename = quote(filename)
    print(f"Encoded filename: '{encoded_filename}'")
    
    if folder_path and folder_path.strip():
        # Remove leading/trailing slashes from folder_path
        folder_path = folder_path.strip('/')
        path = f"{folder_path}/{encoded_filename}"
        print(f"Path (with folder): '{path}'")
    else:
        path = encoded_filename
        print(f"Path (root): '{path}'")
    
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{path}:/content"
    print(f"Final URL: {url}")
    print(f"URL length: {len(url)}")
    print(f"=== END URL CONSTRUCTION ===\n")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    print(f"\nSending PUT request to SharePoint...")
    try:
        response = requests.put(url, headers=headers, data=content, timeout=60)
        print(f"Response status: {response.status_code}")
        
        if response.status_code in (200, 201):
            result = response.json()
            print(f"✓ Upload successful!")
            print(f"  File ID: {result.get('id', 'N/A')}")
            print(f"  File name: {result.get('name', filename)}")
            if 'webUrl' in result:
                print(f"  Web URL: {result['webUrl'][:60]}...")
            print(f"{'='*60}\n")
            return result
        elif response.status_code == 401:
            print(f"✗ ERROR: 401 Unauthorized - Token expired")
            raise PermissionError("SESSION_EXPIRED")
        else:
            error_msg = f"Upload failed: HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_detail = error_data['error'].get('message', 'Unknown error')
                    error_msg += f" - {error_detail}"
                    print(f"✗ ERROR: {error_msg}")
            except:
                error_msg += f" - {response.text[:200]}"
                print(f"✗ ERROR: {error_msg}")
            
            raise UploadError(error_msg)
    
    except requests.exceptions.RequestException as e:
        print(f"✗ ERROR: Network error - {str(e)}")
        raise UploadError(f"Network error during upload: {str(e)}")


def generate_edited_filename(original_filename: str) -> str:
    """
    Generate edited filename by adding _edited suffix before extension.
    
    Args:
        original_filename: Original filename (e.g., "Service_Agreement.docx")
    
    Returns:
        Edited filename (e.g., "Service_Agreement_edited.docx")
    
    Examples:
        >>> generate_edited_filename("Contract.docx")
        'Contract_edited.docx'
        >>> generate_edited_filename("My_File.DOCX")
        'My_File_edited.DOCX'
    """
    if '.' in original_filename:
        base, ext = original_filename.rsplit('.', 1)
        return f"{base}_edited.{ext}"
    else:
        return f"{original_filename}_edited"
