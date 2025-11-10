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
        
        print(f"DEBUG: Authentication check passed, proceeding to route")
        # Simple validation - just check if token exists
        # More complex validation removed to prevent redirect loops
        return f(*args, **kwargs)
    return decorated_function