"""
Authentication utilities for the Flask application
"""
from functools import wraps
from flask import session, redirect, url_for, request
import requests


def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from datetime import datetime, timedelta, timezone as tz
        
        print(f"\n=== DEBUG login_required ===")
        print(f"Route: {request.endpoint}")
        print(f"URL: {request.url}")
        print(f"Has access_token: {bool(session.get('access_token'))}")
        print(f"Has user_email: {bool(session.get('user_email'))}")
        print(f"Session keys: {list(session.keys())}")
        
        # Check if user has valid access token and email
        if not session.get('access_token') or not session.get('user_email'):
            print(f"DEBUG: Not authenticated, redirecting to login")
            print(f"DEBUG: Storing next_url: {request.url}")
            # Store the intended destination
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))
        
        # Check absolute session timeout (4 hours)
        login_time_str = session.get('login_time')
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                session_age = (datetime.now(tz.utc) - login_time).total_seconds()
                max_session_seconds = 4 * 60 * 60  # 4 hours
                
                print(f"DEBUG: Session age: {session_age:.0f} seconds ({session_age/60:.1f} minutes)")
                print(f"DEBUG: Max allowed: {max_session_seconds} seconds ({max_session_seconds/3600} hours)")
                
                if session_age > max_session_seconds:
                    print(f"DEBUG: Absolute session timeout exceeded, clearing session")
                    session.clear()
                    session['next_url'] = request.url
                    from flask import flash
                    flash('Your session has expired after 4 hours. Please log in again.', 'warning')
                    return redirect(url_for('auth.login'))
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error parsing login_time: {e}")
                # If we can't parse login_time, clear session for safety
                session.clear()
                session['next_url'] = request.url
                return redirect(url_for('auth.login'))
        
        print(f"DEBUG: Authentication check passed, proceeding to route")
        # Simple validation - just check if token exists
        # More complex validation removed to prevent redirect loops
        return f(*args, **kwargs)
    return decorated_function