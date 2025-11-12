"""
SharePoint file upload service using delegated user authentication.
"""

from typing import Dict
import requests
from flask import session
import os


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
    access_token = session.get('access_token')
    if not access_token:
        raise PermissionError("SESSION_EXPIRED")
    
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
    token = _get_bearer_token()
    
    # Construct upload URL
    # Format: /drives/{driveId}/root:/{folder_path}/{filename}:/content
    if folder_path and folder_path.strip():
        # Remove leading/trailing slashes from folder_path
        folder_path = folder_path.strip('/')
        path = f"{folder_path}/{filename}"
    else:
        path = filename
    
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{path}:/content"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    try:
        response = requests.put(url, headers=headers, data=content, timeout=60)
        
        if response.status_code in (200, 201):
            return response.json()
        elif response.status_code == 401:
            raise PermissionError("SESSION_EXPIRED")
        else:
            error_msg = f"Upload failed: HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg += f" - {error_data['error'].get('message', 'Unknown error')}"
            except:
                error_msg += f" - {response.text[:200]}"
            
            raise UploadError(error_msg)
    
    except requests.exceptions.RequestException as e:
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
