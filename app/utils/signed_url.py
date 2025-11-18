"""
Signed URL utilities for sessionless downloads.

Provides HMAC-SHA256 signed URLs with expiration for secure downloads
that don't depend on Flask session cookies.
"""

import hmac
import hashlib
import time
import os
from flask import url_for


def make_signed_path(contract_id: str, ttl_sec: int = 300) -> str:
    """
    Generate a signed download path with expiration.
    
    Args:
        contract_id: The contract ID to generate download URL for
        ttl_sec: Time-to-live in seconds (default 5 minutes)
        
    Returns:
        Relative URL path with signature and expiration, e.g.:
        /contracts/ABC123/download_edited?exp=1234567890&sig=abcdef...
        
    Example:
        download_path = make_signed_path('ABC123', ttl_sec=300)
        # Returns: /contracts/ABC123/download_edited?exp=1234567890&sig=...
    """
    # Get secret from environment (must be set in Azure)
    secret = os.getenv('DOWNLOAD_URL_SECRET', 'dev-download-secret')
    
    # Calculate expiration timestamp
    exp = int(time.time() + ttl_sec)
    
    # Create message to sign: contract_id + expiration
    message = f"{contract_id}:{exp}"
    
    # Generate HMAC-SHA256 signature
    sig = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Build signed URL path (relative, not absolute)
    path = url_for(
        'download_edited_contract',
        contract_id=contract_id,
        exp=exp,
        sig=sig
    )
    
    return path


def verify_signed(contract_id: str, exp: str, sig: str) -> bool:
    """
    Verify a signed URL is valid and not expired.
    
    Args:
        contract_id: The contract ID from URL
        exp: Expiration timestamp from query string
        sig: HMAC signature from query string
        
    Returns:
        True if signature is valid and not expired, False otherwise
        
    Example:
        if verify_signed(contract_id, request.args.get('exp'), request.args.get('sig')):
            # Allow download
        else:
            # Reject request
    """
    try:
        # Get secret from environment
        secret = os.getenv('DOWNLOAD_URL_SECRET', 'dev-download-secret')
        
        # Check expiration
        exp_int = int(exp)
        if time.time() > exp_int:
            print(f"SIGNED URL EXPIRED: {contract_id} (expired at {exp_int})")
            return False
        
        # Recreate message and signature
        message = f"{contract_id}:{exp}"
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        if hmac.compare_digest(sig, expected_sig):
            print(f"SIGNED URL VERIFIED: {contract_id} (expires in {exp_int - int(time.time())}s)")
            return True
        else:
            print(f"SIGNED URL INVALID: {contract_id} (signature mismatch)")
            return False
            
    except (ValueError, TypeError) as e:
        print(f"SIGNED URL ERROR: {contract_id} - {e}")
        return False
