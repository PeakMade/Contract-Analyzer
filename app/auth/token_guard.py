"""
Token guard utility for JWT validation and expiration checking.
Prevents unnecessary API calls with expired tokens.
"""
import base64
import json
import time
import logging
from typing import Optional
from flask import session

logger = logging.getLogger(__name__)


class TokenExpiredError(PermissionError):
    """Raised when token is expired or missing."""
    pass


def _decode_jwt_payload(token: str) -> dict:
    """
    Decode JWT payload without signature verification.
    
    Args:
        token: JWT token string (format: header.payload.signature)
    
    Returns:
        Decoded payload as dictionary
    
    Raises:
        ValueError: If token format is invalid or payload can't be decoded
    """
    try:
        # Split token into parts
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format: expected 3 parts separated by dots")
        
        # Get payload (second part)
        payload_b64 = parts[1]
        
        # Add padding if needed (base64 requires length to be multiple of 4)
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += '=' * padding
        
        # Decode base64url (replace URL-safe chars back to standard base64)
        payload_b64 = payload_b64.replace('-', '+').replace('_', '/')
        payload_json = base64.b64decode(payload_b64)
        
        # Parse JSON
        payload = json.loads(payload_json)
        
        return payload
        
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to decode JWT payload: {e}")
        raise ValueError(f"Invalid JWT token: {e}")


def token_exp_soon(token: str, skew_sec: int = 120) -> bool:
    """
    Check if token will expire soon (within skew_sec seconds).
    
    Args:
        token: JWT token string
        skew_sec: Number of seconds before expiration to consider "soon" (default: 120)
    
    Returns:
        True if token expires within skew_sec seconds, False otherwise
    
    Raises:
        ValueError: If token format is invalid
    """
    try:
        payload = _decode_jwt_payload(token)
        
        # Get expiration time
        exp = payload.get('exp')
        if exp is None:
            logger.warning("JWT token missing 'exp' claim")
            return True  # Treat missing exp as expired
        
        # Check if expiring soon
        current_time = time.time()
        time_until_exp = exp - current_time
        
        is_expiring_soon = time_until_exp <= skew_sec
        
        if is_expiring_soon:
            logger.debug(f"Token expires in {time_until_exp:.1f}s (skew: {skew_sec}s)")
        
        return is_expiring_soon
        
    except ValueError:
        # Invalid token format - treat as expired
        return True


def ensure_token_or_401(token: Optional[str] = None, skew_sec: int = 120) -> str:
    """
    Ensure token is present and not expired, otherwise raise PermissionError.
    
    Args:
        token: JWT token string. If None, attempts to get from Flask session.
        skew_sec: Number of seconds before expiration to reject token (default: 120)
    
    Returns:
        Valid token string
    
    Raises:
        PermissionError: If token is missing, expired, or will expire soon (SESSION_EXPIRED)
    """
    # Get token from parameter or session
    if token is None:
        token = session.get('access_token')
    
    if not token:
        logger.warning("No access token found")
        raise TokenExpiredError("SESSION_EXPIRED")
    
    # Check if token is expired or expiring soon
    if token_exp_soon(token, skew_sec):
        logger.warning("Access token is expired or expiring soon")
        raise TokenExpiredError("SESSION_EXPIRED")
    
    return token


def get_token_info(token: str) -> dict:
    """
    Get token information including expiration time and remaining lifetime.
    
    Args:
        token: JWT token string
    
    Returns:
        Dictionary with token info:
        - exp: Expiration timestamp
        - iat: Issued at timestamp (if present)
        - remaining_seconds: Seconds until expiration
        - is_expired: Boolean indicating if token is expired
    """
    try:
        payload = _decode_jwt_payload(token)
        
        exp = payload.get('exp')
        iat = payload.get('iat')
        current_time = time.time()
        
        info = {
            'exp': exp,
            'iat': iat,
            'remaining_seconds': exp - current_time if exp else None,
            'is_expired': exp < current_time if exp else True
        }
        
        return info
        
    except ValueError as e:
        return {
            'exp': None,
            'iat': None,
            'remaining_seconds': None,
            'is_expired': True,
            'error': str(e)
        }
