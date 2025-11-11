"""
Manual test script for token_guard functionality.
Run this to verify token guard is working correctly.
"""
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_token_guard import create_test_jwt
from app.auth.token_guard import (
    token_exp_soon,
    ensure_token_or_401,
    get_token_info,
    TokenExpiredError
)


def test_valid_token():
    """Test with a valid token."""
    print("\n=== Test 1: Valid Token ===")
    future_exp = int(time.time()) + 3600
    token = create_test_jwt(exp=future_exp)
    
    print(f"Token expires in: {future_exp - int(time.time())} seconds")
    print(f"Token exp soon (120s skew): {token_exp_soon(token, skew_sec=120)}")
    
    try:
        result = ensure_token_or_401(token)
        print(f"✓ Token validation passed")
    except TokenExpiredError as e:
        print(f"✗ Token validation failed: {e}")
    
    info = get_token_info(token)
    print(f"Token info: remaining={info['remaining_seconds']:.1f}s, expired={info['is_expired']}")


def test_expiring_soon():
    """Test with a token expiring soon."""
    print("\n=== Test 2: Token Expiring Soon ===")
    soon_exp = int(time.time()) + 60  # 1 minute
    token = create_test_jwt(exp=soon_exp)
    
    print(f"Token expires in: {soon_exp - int(time.time())} seconds")
    print(f"Token exp soon (120s skew): {token_exp_soon(token, skew_sec=120)}")
    
    try:
        result = ensure_token_or_401(token, skew_sec=120)
        print(f"✗ Token validation passed (should have failed)")
    except TokenExpiredError as e:
        print(f"✓ Token validation correctly rejected: {e}")


def test_expired_token():
    """Test with an expired token."""
    print("\n=== Test 3: Expired Token ===")
    past_exp = int(time.time()) - 300  # 5 minutes ago
    token = create_test_jwt(exp=past_exp)
    
    print(f"Token expired: {int(time.time()) - past_exp} seconds ago")
    print(f"Token exp soon (120s skew): {token_exp_soon(token, skew_sec=120)}")
    
    try:
        result = ensure_token_or_401(token)
        print(f"✗ Token validation passed (should have failed)")
    except TokenExpiredError as e:
        print(f"✓ Token validation correctly rejected: {e}")
    
    info = get_token_info(token)
    print(f"Token info: remaining={info['remaining_seconds']:.1f}s, expired={info['is_expired']}")


def test_invalid_token():
    """Test with an invalid token format."""
    print("\n=== Test 4: Invalid Token Format ===")
    invalid_token = "not.a.valid.jwt"
    
    print(f"Token exp soon: {token_exp_soon(invalid_token, skew_sec=120)}")
    
    try:
        result = ensure_token_or_401(invalid_token)
        print(f"✗ Token validation passed (should have failed)")
    except TokenExpiredError as e:
        print(f"✓ Token validation correctly rejected: {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("Token Guard Manual Test Suite")
    print("=" * 60)
    
    test_valid_token()
    test_expiring_soon()
    test_expired_token()
    test_invalid_token()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
