"""
Admin utilities for checking user permissions via SharePoint

NOTE: Previous version used Office365-REST-Python-Client library with CAML queries.
Switched to Microsoft Graph API for consistency with sharepoint_service.py.
See git history to revert if needed.
"""
from functools import wraps
from flask import session, redirect, url_for, request, flash, current_app
import requests
import msal
import os
import logging

logger = logging.getLogger(__name__)


def _get_access_token():
    """Get access token using client credentials flow for Microsoft Graph API"""
    try:
        client_id = os.getenv('O365_CLIENT_ID')
        client_secret = os.getenv('O365_CLIENT_SECRET')
        tenant_id = os.getenv('O365_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            logger.error("SharePoint credentials not configured")
            return None
        
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )
        
        # Get token for Microsoft Graph
        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            logger.error(f"Failed to get access token: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting access token: {str(e)}")
        return None


def _get_site_id(access_token):
    """Get the SharePoint site ID using Graph API"""
    try:
        graph_url = "https://graph.microsoft.com/v1.0"
        site_url = f"{graph_url}/sites/peakcampus.sharepoint.com:/sites/BaseCampApps"
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.get(site_url, headers=headers)
        
        if response.status_code == 200:
            site_data = response.json()
            return site_data['id']
        else:
            logger.error(f"Failed to get site ID: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting site ID: {str(e)}")
        return None


def is_admin(user_email):
    """
    Check if a user is an admin by querying SharePoint admin list via Microsoft Graph API
    
    Args:
        user_email (str): Email address to check
        
    Returns:
        bool: True if user is an admin and active, False otherwise
    """
    if not user_email:
        logger.warning("No email provided for admin check")
        return False
    
    try:
        print(f"\n=== DEBUG is_admin (Graph API) ===")
        print(f"Checking admin status for: {user_email}")
        
        # Get access token
        access_token = _get_access_token()
        if not access_token:
            logger.error("Failed to get access token")
            return False
        
        # Get site ID
        site_id = _get_site_id(access_token)
        if not site_id:
            logger.error("Failed to get site ID")
            return False
        
        # Get admin list configuration
        admin_list_id = current_app.config.get('SP_ADMIN_LIST_ID')
        email_column = current_app.config.get('SP_ADMIN_EMAIL_COLUMN', 'Email')
        active_column = current_app.config.get('SP_ADMIN_ACTIVE_COLUMN', 'Active')
        
        print(f"DEBUG: Site ID: {site_id}")
        print(f"DEBUG: Admin List ID: {admin_list_id}")
        print(f"DEBUG: Email Column: {email_column}")
        print(f"DEBUG: Active Column: {active_column}")
        
        if not admin_list_id:
            logger.error("SP_ADMIN_LIST_ID not configured")
            return False
        
        # Query the admin list using Microsoft Graph API
        graph_url = "https://graph.microsoft.com/v1.0"
        items_url = f"{graph_url}/sites/{site_id}/lists/{admin_list_id}/items?$expand=fields"
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        print(f"DEBUG: Querying admin list via Graph API")
        response = requests.get(items_url, headers=headers)
        
        print(f"DEBUG: Response status: {response.status_code}")
        
        if response.status_code == 200:
            items_data = response.json()
            items = items_data.get('value', [])
            
            print(f"DEBUG: Query returned {len(items)} items")
            
            # Check if user exists and is active
            for item in items:
                fields = item.get('fields', {})
                item_email = fields.get(email_column, '').lower()
                is_active = fields.get(active_column, False)
                
                print(f"DEBUG: Checking item - Email: {item_email}, Active: {is_active} (type: {type(is_active)})")
                
                # Handle both boolean True and string representations
                if item_email == user_email.lower() and is_active in [True, 'Yes', 'yes', 1, '1']:
                    logger.info(f"Admin check passed for {user_email}")
                    print(f"DEBUG: ✓ User is an active admin!")
                    return True
            
            logger.info(f"Admin check failed for {user_email}")
            print(f"DEBUG: User is NOT found as active admin in list")
            return False
        else:
            logger.error(f"Failed to query admin list: {response.status_code} - {response.text}")
            print(f"DEBUG ERROR: Graph API query failed")
            return False
        
    except Exception as e:
        logger.error(f"Error checking admin status: {str(e)}")
        print(f"DEBUG ERROR in is_admin: {str(e)}")
        import traceback
        print(f"DEBUG Traceback: {traceback.format_exc()}")
        return False


def admin_required(f):
    """
    Decorator to require admin privileges for routes
    User must be authenticated AND listed as active admin in SharePoint
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"\n=== DEBUG admin_required ===")
        print(f"Route: {request.endpoint}")
        
        # First check if user is logged in
        if not session.get('access_token') or not session.get('user_email'):
            print(f"DEBUG: User not authenticated")
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))
        
        user_email = session.get('user_email')
        print(f"DEBUG: Checking admin status for {user_email}")
        
        # Check admin status (with caching in session)
        # Cache admin status for 5 minutes to avoid excessive SharePoint queries
        if 'is_admin' not in session or session.get('admin_check_email') != user_email:
            admin_status = is_admin(user_email)
            session['is_admin'] = admin_status
            session['admin_check_email'] = user_email
            print(f"DEBUG: Admin status checked and cached: {admin_status}")
        else:
            admin_status = session.get('is_admin', False)
            print(f"DEBUG: Using cached admin status: {admin_status}")
        
        if not admin_status:
            logger.warning(f"Unauthorized admin access attempt by {user_email}")
            print(f"DEBUG: Access denied - user is not an admin")
            flash('Access denied. This page requires administrator privileges.', 'error')
            return redirect(url_for('index'))
        
        print(f"DEBUG: Admin check passed, proceeding to route")
        return f(*args, **kwargs)
    
    return decorated_function
