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


def _update_file_creator(file_id: str, drive_id: str, user_email: str, site_id: str) -> bool:
    """
    Update the file's Modified By field to show the actual user.
    
    Args:
        file_id: The DriveItem ID from the file upload response
        drive_id: SharePoint drive ID  
        user_email: Email of the user to set as creator/modifier
        site_id: SharePoint site ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"\n=== DEBUG _update_file_creator (sp_upload) ===")
        print(f"File ID: {file_id}")
        print(f"User Email: {user_email}")
        
        token = _get_bearer_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Get user ID from email
        user_lookup_url = f"https://graph.microsoft.com/v1.0/users/{user_email}"
        user_response = requests.get(user_lookup_url, headers=headers)
        
        if user_response.status_code != 200:
            print(f"✗ Failed to lookup user: {user_response.status_code}")
            return False
        
        user_data = user_response.json()
        user_id = user_data.get('id')
        print(f"✓ Found user ID: {user_id}")
        
        # Get list item for the file
        list_item_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}/listItem"
        list_item_response = requests.get(list_item_url, headers=headers)
        
        if list_item_response.status_code != 200:
            print(f"✗ Failed to get list item: {list_item_response.status_code}")
            return False
        
        list_item_data = list_item_response.json()
        list_item_id = list_item_data.get('id')
        print(f"✓ Found list item ID: {list_item_id}")
        
        # Update the Editor field
        update_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{drive_id}/items/{list_item_id}/fields"
        update_data = {'EditorLookupId': user_id}
        
        update_response = requests.patch(update_url, headers=headers, json=update_data)
        
        if update_response.status_code == 200:
            print(f"✓ Successfully updated file creator")
            return True
        else:
            print(f"✗ Failed to update: {update_response.status_code} - {update_response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Exception updating file creator: {e}")
        return False


def upload_file(
    drive_id: str,
    folder_path: str,
    filename: str,
    content: bytes,
    user_email: str = None,
    site_id: str = None
) -> Dict:
    """
    Upload a file to SharePoint using delegated user token.
    
    Args:
        drive_id: SharePoint drive ID
        folder_path: Folder path within drive (e.g., "Contracts" or "" for root)
        filename: Name for the uploaded file
        content: File content as bytes
        user_email: Email of user to attribute file to (optional)
        site_id: SharePoint site ID (required if user_email provided)
    
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
            
            # Update file creator if user_email and site_id provided
            if user_email and site_id:
                file_id = result.get('id')
                print(f"\nUpdating file creator to: {user_email}")
                _update_file_creator(file_id, drive_id, user_email, site_id)
            elif user_email and not site_id:
                print(f"⚠ Warning: user_email provided but site_id missing, cannot update creator")
            
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
