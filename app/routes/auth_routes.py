from flask import Blueprint, request, session, redirect, url_for, current_app, flash
import msal
import requests
import logging
import secrets

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
        print(f"\n=== DEBUG /auth/login ===")
        print(f"Session before check: {dict(session)}")
        print(f"Has access_token: {bool(session.get('access_token'))}")
        print(f"Has user_email: {bool(session.get('user_email'))}")
        
        # Check if already logged in
        if session.get('access_token') and session.get('user_email'):
            logger.info("User already authenticated, redirecting to home")
            print(f"DEBUG: Already authenticated, redirecting to index")
            print(f"DEBUG: url_for('index') = {url_for('index')}")
            return redirect(url_for('index'))
        
        print(f"DEBUG: Clearing session")
        # Clear any existing session data to prevent conflicts
        session.clear()
        
        # CSRF protection: generate state token
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        print(f"DEBUG: Generated OAuth state token")
        
        # Create auth URL with all required scopes for file access
        msal_app = get_msal_app()
        auth_url = msal_app.get_authorization_request_url(
            scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"],
            redirect_uri=current_app.config['REDIRECT_URI'],
            state=state,
            prompt="select_account"
        )
        
        print(f"DEBUG: REDIRECT_URI configured: {current_app.config['REDIRECT_URI']}")
        print(f"DEBUG: Auth URL: {auth_url}")
        logger.info("Redirecting to Microsoft login")
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        print(f"DEBUG ERROR in login: {str(e)}")
        flash('Authentication error occurred. Please try again.', 'error')
        return redirect('/')

@auth_bp.route('/redirect')
def redirect_handler():
    """Handle Microsoft redirect"""
    try:
        print(f"\n=== DEBUG /auth/redirect ===")
        print(f"Query params: {dict(request.args)}")
        print(f"Session before processing: {dict(session)}")
        
        # CSRF protection: verify state token
        received_state = request.args.get('state')
        stored_state = session.get('oauth_state')
        
        print(f"DEBUG: State received: {bool(received_state)}")
        print(f"DEBUG: State stored: {bool(stored_state)}")
        print(f"DEBUG: State matches: {received_state == stored_state}")
        
        if not received_state or received_state != stored_state:
            logger.error("OAuth state mismatch - possible CSRF attack")
            print(f"DEBUG: CSRF state validation failed")
            session.clear()
            flash('Invalid authentication state. Please try again.', 'error')
            return redirect('/')
        
        # Get authorization code and check for errors
        code = request.args.get('code')
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        
        print(f"DEBUG: code present: {bool(code)}")
        print(f"DEBUG: error: {error}")
        
        if error:
            logger.error(f"OAuth error: {error} - {error_description}")
            print(f"DEBUG: OAuth error received")
            flash(f'Login failed: {error_description or error}', 'error')
            return redirect('/')
            
        if not code:
            logger.error("No authorization code received")
            print(f"DEBUG: No code in redirect")
            flash('Login failed: No authorization code received', 'error')
            return redirect('/')
        
        print(f"DEBUG: Exchanging code for token")
        # Exchange code for token with all required scopes
        msal_app = get_msal_app()
        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"],
            redirect_uri=current_app.config['REDIRECT_URI']
        )
        
        print(f"DEBUG: Token result keys: {list(result.keys())}")
        print(f"DEBUG: Has access_token: {bool(result.get('access_token'))}")
        
        if 'access_token' not in result:
            error_desc = result.get('error_description', 'Token acquisition failed')
            logger.error(f"Token acquisition failed: {error_desc}")
            print(f"DEBUG: Token acquisition failed: {error_desc}")
            flash(f'Authentication failed: {error_desc}', 'error')
            return redirect('/')
        
        print(f"DEBUG: Getting user info from Graph API")
        # Get user info
        headers = {'Authorization': f"Bearer {result['access_token']}"}
        user_response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        
        print(f"DEBUG: User info response status: {user_response.status_code}")
        
        if user_response.status_code != 200:
            logger.error(f"Failed to get user info: {user_response.status_code}")
            print(f"DEBUG: Failed to get user info")
            flash('Failed to get user information', 'error')
            return redirect('/')
        
        user_info = user_response.json()
        email = user_info.get('mail') or user_info.get('userPrincipalName', '')
        
        print(f"DEBUG: User email: {email}")
        
        # Check domain restriction (allow peakmade.com)
        if not email.lower().endswith('@peakmade.com'):
            logger.warning(f"Domain restriction: {email} not allowed")
            print(f"DEBUG: Domain restriction failed for {email}")
            flash('Access denied. Only @peakmade.com email addresses are allowed.', 'error')
            session.clear()
            return redirect('/')
        
        print(f"DEBUG: Setting session data")
        # Store minimal user information in session
        session['access_token'] = result['access_token']
        
        # Store token expiration in UTC to avoid timezone issues
        from datetime import datetime, timedelta
        expires_in = result.get('expires_in', 3600)  # Default 1 hour
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        session['token_expires_at'] = token_expires_at.isoformat()
        print(f"DEBUG: Token expires at: {token_expires_at} UTC (in {expires_in} seconds)")
        
        session['user_name'] = user_info.get('displayName', email.split('@')[0])
        session['user_email'] = email
        
        # Check admin status and cache in session
        from app.utils.admin_utils import is_admin
        admin_status = is_admin(email)
        session['is_admin'] = admin_status
        print(f"DEBUG: Admin status for {email}: {admin_status}")
        
        print(f"DEBUG: Session after setting: {list(session.keys())}")
        
        logger.info(f"Authentication successful for {email}")
        flash(f"Welcome, {user_info.get('displayName', email)}!", 'success')
        
        # Redirect to intended page or homepage
        next_url = session.pop('next_url', '/')
        print(f"DEBUG: Redirecting to next_url: {next_url}")
        print(f"DEBUG: url_for('index') would be: {url_for('index')}")
        return redirect(next_url)
        
    except Exception as e:
        logger.error(f"Auth redirect error: {str(e)}")
        print(f"DEBUG ERROR in redirect_handler: {str(e)}")
        import traceback
        print(f"DEBUG Traceback: {traceback.format_exc()}")
        flash('Authentication error occurred. Please try again.', 'error')
        session.clear()
        return redirect('/')

@auth_bp.route('/logout')
def logout():
    """Logout user"""
    try:
        user_email = session.get('user_email', 'Unknown')
        logger.info(f"User {user_email} logging out")
        
        session.clear()
        
        # Build proper Microsoft logout URL
        tenant_id = current_app.config['TENANT_ID']
        post_logout_uri = url_for('index', _external=True)
        logout_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout?post_logout_redirect_uri={post_logout_uri}"
        
        print(f"DEBUG: Logging out, redirecting to Microsoft logout")
        print(f"DEBUG: Post-logout URI: {post_logout_uri}")
        
        flash('You have been logged out successfully.', 'info')
        return redirect(logout_url)
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        print(f"DEBUG ERROR in logout: {str(e)}")
        session.clear()
        return redirect('/')