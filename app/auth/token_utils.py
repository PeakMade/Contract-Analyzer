"""
Token refresh utilities for maintaining valid access tokens.

This module provides functions to automatically refresh access tokens
before they expire, enabling sliding session behavior where active users
don't need to re-authenticate.
"""

from flask import session, current_app
from datetime import datetime, timedelta, timezone as tz
import msal
import logging

logger = logging.getLogger(__name__)


class AuthRequired(Exception):
    """Raised when authentication is required but not available."""
    pass


def token_expiring_soon(skew_seconds=300):
    """
    Check if the access token is expiring soon.
    
    Args:
        skew_seconds: Number of seconds before expiration to consider "expiring soon"
                     Default is 300 seconds (5 minutes)
    
    Returns:
        bool: True if token expires within skew_seconds, False otherwise
        
    Raises:
        AuthRequired: If no token_expires_at in session
    """
    expires_at_str = session.get('token_expires_at')
    if not expires_at_str:
        raise AuthRequired("No token expiration time in session")
    
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        now = datetime.now(tz.utc)
        time_until_expiry = (expires_at - now).total_seconds()
        
        logger.debug(f"Token expires in {time_until_expiry:.0f} seconds")
        return time_until_expiry < skew_seconds
    except (ValueError, AttributeError) as e:
        logger.error(f"Failed to parse token expiration: {e}")
        raise AuthRequired("Invalid token expiration format")


def refresh_access_token():
    """
    Use the refresh token to obtain a new access token.
    
    Returns:
        dict: Token result from MSAL containing new access_token and expires_in
        
    Raises:
        AuthRequired: If no refresh token available or refresh fails
    """
    refresh_token = session.get('refresh_token')
    if not refresh_token:
        logger.warning("No refresh token available - user must re-authenticate")
        raise AuthRequired("No refresh token available")
    
    try:
        # Create MSAL app
        msal_app = msal.ConfidentialClientApplication(
            current_app.config['CLIENT_ID'],
            authority=current_app.config['AUTHORITY'],
            client_credential=current_app.config['CLIENT_SECRET']
        )
        
        # Use refresh token to get new access token
        result = msal_app.acquire_token_by_refresh_token(
            refresh_token,
            scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"]
        )
        
        if 'access_token' not in result:
            error = result.get('error', '')
            error_desc = result.get('error_description', 'Token refresh failed')
            
            # Check for expired/revoked refresh token (AADSTS50173)
            if 'AADSTS50173' in error_desc or 'expired' in error_desc.lower() or 'revoked' in error_desc.lower():
                logger.warning(f"Refresh token expired or revoked - user must re-authenticate: {error_desc}")
                raise AuthRequired("Your session has expired. Please log in again.")
            
            # Check for invalid refresh token
            if 'AADSTS70000' in error_desc or 'invalid' in error_desc.lower():
                logger.warning(f"Invalid refresh token - user must re-authenticate: {error_desc}")
                raise AuthRequired("Invalid session. Please log in again.")
            
            # Generic token refresh failure
            logger.error(f"Token refresh failed: {error_desc}")
            raise AuthRequired(f"Token refresh failed: {error_desc}")
        
        # Check if Azure AD issued a new refresh token (rolling refresh)
        new_refresh_token = result.get('refresh_token')
        if new_refresh_token:
            logger.info("Successfully refreshed access token - new refresh token issued (rolling refresh)")
        else:
            logger.warning("Successfully refreshed access token - but NO new refresh token issued (single-use token)")
        
        return result
        
    except Exception as e:
        logger.error(f"Exception during token refresh: {str(e)}")
        raise AuthRequired(f"Token refresh error: {str(e)}")


def ensure_fresh_access_token():
    """
    Ensure the access token is valid and not expiring soon.
    
    If the token is expiring within 5 minutes, automatically refresh it
    using the refresh token. Updates session with new tokens.
    
    This should be called before making API calls to Microsoft Graph or SharePoint.
    
    Raises:
        AuthRequired: If token refresh fails or no refresh token available
    """
    # Check if user is authenticated
    if not session.get('access_token'):
        raise AuthRequired("No access token in session")
    
    # Check if token is expiring soon
    try:
        if not token_expiring_soon(skew_seconds=300):  # 5 minutes before expiry
            # Token is still fresh, nothing to do
            return
    except AuthRequired:
        # If we can't determine expiration, try to refresh anyway
        logger.warning("Unable to determine token expiration, attempting refresh")
    
    # Token is expiring soon, refresh it
    logger.info("Access token expiring soon, refreshing...")
    result = refresh_access_token()
    
    # Update session with new tokens
    session['access_token'] = result['access_token']
    
    # Update refresh token if a new one was provided (rolling refresh)
    if result.get('refresh_token'):
        old_refresh_token = session.get('refresh_token', '')[:20] + "..."
        new_refresh_token = result['refresh_token'][:20] + "..."
        session['refresh_token'] = result['refresh_token']
        logger.info(f"Refresh token renewed: old={old_refresh_token}, new={new_refresh_token}")
    else:
        logger.warning("No new refresh token provided - using same refresh token (may expire absolutely)")
    
    # Update expiration time
    expires_in = result.get('expires_in', 3600)
    token_expires_at = datetime.now(tz.utc) + timedelta(seconds=expires_in)
    session['token_expires_at'] = token_expires_at.isoformat()
    
    logger.info(f"Token refreshed successfully, expires at {token_expires_at}")
