from flask import Blueprint, request, session, redirect, url_for, current_app, flash
import msal
import requests
import logging

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)

def get_msal_app():
    """Create MSAL app"""
    return msal.ConfidentialClientApplication(
        current_app.config['CLIENT_ID'],
        authority=current_app.config['AUTHORITY'],
        client_credential=current_app.config['CLIENT_SECRET']
    )

@auth_bp.route('/login')
def login():
    """Start Microsoft authentication"""
    try:
        # Check if already logged in
        if session.get('access_token') and session.get('user_email'):
            logger.info("User already authenticated, redirecting to home")
            return redirect(url_for('index'))
        
        # Clear any existing session data to prevent conflicts
        session.clear()
        
        # Create auth URL
        msal_app = get_msal_app()
        auth_url = msal_app.get_authorization_request_url(
            scopes=["User.Read"],
            redirect_uri=current_app.config['REDIRECT_URI']
        )
        
        logger.info("Redirecting to Microsoft login")
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        flash('Authentication error occurred. Please try again.', 'error')
        return redirect('/')

@auth_bp.route('/redirect')
def redirect_handler():
    """Handle Microsoft redirect"""
    try:
        # Get authorization code and check for errors
        code = request.args.get('code')
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        
        if error:
            logger.error(f"OAuth error: {error} - {error_description}")
            flash(f'Login failed: {error_description or error}', 'error')
            return redirect('/')
            
        if not code:
            logger.error("No authorization code received")
            flash('Login failed: No authorization code received', 'error')
            return redirect('/')
        
        # Exchange code for token
        msal_app = get_msal_app()
        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=["User.Read"],
            redirect_uri=current_app.config['REDIRECT_URI']
        )
        
        if 'access_token' not in result:
            error_desc = result.get('error_description', 'Token acquisition failed')
            logger.error(f"Token acquisition failed: {error_desc}")
            flash(f'Authentication failed: {error_desc}', 'error')
            return redirect('/')
        
        # Get user info
        headers = {'Authorization': f"Bearer {result['access_token']}"}
        user_response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        
        if user_response.status_code != 200:
            logger.error(f"Failed to get user info: {user_response.status_code}")
            flash('Failed to get user information', 'error')
            return redirect('/')
        
        user_info = user_response.json()
        email = user_info.get('mail') or user_info.get('userPrincipalName', '')
        
        # Check domain restriction (allow peakmade.com)
        if not email.lower().endswith('@peakmade.com'):
            logger.warning(f"Domain restriction: {email} not allowed")
            flash('Access denied. Only @peakmade.com email addresses are allowed.', 'error')
            session.clear()
            return redirect('/')
        
        # Store minimal user information in session
        session['access_token'] = result['access_token']
        session['user_name'] = user_info.get('displayName', email.split('@')[0])
        session['user_email'] = email
        
        logger.info(f"Authentication successful for {email}")
        flash(f"Welcome, {user_info.get('displayName', email)}!", 'success')
        
        # Redirect to intended page or homepage
        next_url = session.pop('next_url', '/')
        return redirect(next_url)
        
    except Exception as e:
        logger.error(f"Auth redirect error: {str(e)}")
        flash('Authentication error occurred. Please try again.', 'error')
        session.clear()
        return redirect('/')

@auth_bp.route('/logout')
def logout():
    """Logout user"""
    try:
        session.clear()
        
        # Build proper logout URL
        tenant_id = current_app.config['TENANT_ID']
        post_logout_uri = url_for('index', _external=True)
        logout_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout?post_logout_redirect_uri={post_logout_uri}"
        
        flash('You have been logged out successfully.', 'info')
        return redirect(logout_url)
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        session.clear()
        return redirect('/')