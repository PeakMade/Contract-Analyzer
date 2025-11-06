from flask import Blueprint, request, session, redirect, url_for, current_app, flash
import msal
import requests

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

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
    # Check if already logged in
    if 'user' in session:
        return redirect(url_for('index'))
    
    # Create auth URL
    msal_app = get_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        current_app.config['SCOPE'],
        redirect_uri=current_app.config['REDIRECT_URI']
    )
    return redirect(auth_url)

@auth_bp.route('/redirect')
def redirect_handler():
    """Handle Microsoft redirect"""
    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('Login failed', 'error')
        return redirect(url_for('index'))
    
    # Exchange code for token
    msal_app = get_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=current_app.config['SCOPE'],
        redirect_uri=current_app.config['REDIRECT_URI']
    )
    
    if 'access_token' not in result:
        flash('Authentication failed', 'error')
        return redirect(url_for('index'))
    
    # Get user info
    headers = {'Authorization': f"Bearer {result['access_token']}"}
    user_response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
    
    if user_response.status_code != 200:
        flash('Failed to get user info', 'error')
        return redirect(url_for('index'))
    
    user_info = user_response.json()
    email = user_info.get('mail') or user_info.get('userPrincipalName', '')
    
    # Check domain
    if not email.endswith('@peakmade.com'):
        flash('Only @peakmade.com emails allowed', 'error')
        return redirect(url_for('index'))
    
    # Store in session
    session['user'] = user_info
    session['access_token'] = result['access_token']
    
    flash(f"Welcome, {user_info.get('displayName', email)}!", 'success')
    return redirect(url_for('index'))

@auth_bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    logout_url = f"{current_app.config['AUTHORITY']}/oauth2/v2.0/logout?post_logout_redirect_uri={url_for('index', _external=True)}"
    return redirect(logout_url)