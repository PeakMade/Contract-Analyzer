
from flask import Blueprint, request, session, redirect, url_for, current_app, flash, jsonify
import msal
import requests
import logging
import secrets
from app.services.activity_logger import logger as activity_logger

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)

@auth_bp.route('/api/log-start-session', methods=['POST'])
def log_start_session():
    """API endpoint to log Start Session activity (called from JS on tab open)"""
    try:
        user_email = session.get('user_email')
        user_name = session.get('user_name')
        if not user_email:
            return jsonify({"success": False, "error": "No user_email in session"}), 401
        result = activity_logger.log_start_session(user_email=user_email, user_display_name=user_name)
        return jsonify({"success": result})
    except Exception as e:
        logger.error(f"Error logging start session: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route('/api/log-end-session', methods=['POST'])
def log_end_session():
    """API endpoint to log End Session activity (called from JS on browser/tab close)"""
    try:
        user_email = session.get('user_email')
        user_name = session.get('user_name')
        if not user_email:
            return jsonify({"success": False, "error": "No user_email in session"}), 401
        result = activity_logger.log_end_session(user_email=user_email, user_display_name=user_name)
        return jsonify({"success": result})
    except Exception as e:
        logger.error(f"Error logging end session: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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
        # Note: MSAL automatically adds offline_access - do NOT include it explicitly
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
        # Exchange code for token - MSAL automatically includes offline_access for refresh token
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
        # Store tokens and expiration (refresh_token enables silent renewal)
        session['access_token'] = result['access_token']
        session['refresh_token'] = result.get('refresh_token')  # Will be None if offline_access not granted
        
        # Store token expiration with timezone-aware UTC datetime
        from datetime import datetime, timedelta, timezone as tz
        expires_in = result.get('expires_in', 3600)  # Default 1 hour
        token_expires_at = datetime.now(tz.utc) + timedelta(seconds=expires_in)
        session['token_expires_at'] = token_expires_at.isoformat()
        
        # Store login time for absolute session timeout (security requirement)
        session['login_time'] = datetime.now(tz.utc).isoformat()
        print(f"DEBUG: Login time set: {session['login_time']}")
        print(f"DEBUG: Token expires at: {token_expires_at} (in {expires_in} seconds)")
        print(f"DEBUG: Refresh token available: {bool(result.get('refresh_token'))}")
        
        session['user_name'] = user_info.get('displayName', email.split('@')[0])
        session['user_email'] = email
        
        # Check admin status and cache in session
        from app.utils.admin_utils import is_admin
        admin_status = is_admin(email)
        session['is_admin'] = admin_status
        print(f"DEBUG: Admin status for {email}: {admin_status}")
        
        print(f"DEBUG: Session after setting: {list(session.keys())}")
        
        # Log the user login to SharePoint
        print(f"\n{'*'*60}")
        print(f"DEBUG: ATTEMPTING TO LOG LOGIN TO SHAREPOINT")
        print(f"DEBUG: Email: {email}")
        print(f"DEBUG: Display Name: {user_info.get('displayName', email.split('@')[0])}")
        print(f"{'*'*60}")
        
        try:
            login_result = activity_logger.log_login(
                user_email=email,
                user_display_name=user_info.get('displayName', email.split('@')[0])
            )
            print(f"\n{'*'*60}")
            print(f"DEBUG: LOGIN LOGGING RESULT: {login_result}")
            print(f"{'*'*60}\n")
        except Exception as e:
            print(f"\n{'*'*60}")
            print(f"DEBUG: EXCEPTION CALLING log_login(): {e}")
            import traceback
            traceback.print_exc()
            print(f"{'*'*60}\n")
        
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
    """Logout user - only invalidates current user's session"""
    try:
        user_email = session.get('user_email', 'Unknown')
        user_name = session.get('user_name', 'Unknown')
        logger.info(f"User {user_email} logging out")
        
        # Log the logout activity BEFORE clearing session
        from app.services.activity_logger import logger as activity_logger
        try:
            # Log End Session when user explicitly logs out
            activity_logger.log_end_session(user_email=user_email, user_display_name=user_name)
            # Log Logout activity
            activity_logger.log_logout(user_email=user_email, user_display_name=user_name)
            print(f"DEBUG: Logged End Session and Logout for {user_email}")
        except Exception as e:
            print(f"DEBUG: Failed to log logout activities: {e}")
            # Non-critical - don't block logout
        
        # Flask-Session automatically handles session file deletion when session.clear() is called
        # Do NOT manually delete session files or iterate through the session directory
        # This ensures only the current user's session is invalidated
        session.clear()
        
        # Redirect to login page which will show Microsoft account picker
        # User stays signed in to Microsoft but can select their account again
        print(f"DEBUG: User {user_email} logged out, redirecting to login page")
        
        flash('You have been logged out successfully.', 'info')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        print(f"DEBUG ERROR in logout: {str(e)}")
        session.clear()
        return redirect('/')

@auth_bp.route('/ping')
def ping():
    """
    Keep-alive endpoint for maintaining session and refreshing tokens.
    
    Called periodically by client-side JavaScript to:
    1. Verify user is still authenticated
    2. Refresh access token if expiring soon
    3. Keep sliding session alive
    
    Returns:
        200: User authenticated, token refreshed if needed
        401: User not authenticated, should redirect to login
    """
    try:
        # Check if user is authenticated
        if not session.get('access_token') or not session.get('user_email'):
            logger.debug("Ping: User not authenticated")
            return {'status': 'unauthenticated'}, 401
        
        # Try to ensure token is fresh
        from app.auth.token_utils import ensure_fresh_access_token, AuthRequired
        try:
            ensure_fresh_access_token()
            logger.debug(f"Ping: Token refreshed for {session.get('user_email')}")
            return {'status': 'ok', 'message': 'Token refreshed successfully'}, 200
        except AuthRequired as e:
            logger.warning(f"Ping: Token refresh failed - {str(e)}")
            session.clear()
            return {'status': 'auth_required', 'message': str(e)}, 401
            
    except Exception as e:
        logger.error(f"Ping error: {str(e)}")
        return {'status': 'error', 'message': 'Server error'}, 500