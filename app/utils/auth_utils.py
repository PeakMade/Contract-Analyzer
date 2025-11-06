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
        # Check if user has valid access token and email
        if not session.get('access_token') or not session.get('user_email'):
            # Store the intended destination
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))
        
        # Simple validation - just check if token exists
        # More complex validation removed to prevent redirect loops
        return f(*args, **kwargs)
    return decorated_function