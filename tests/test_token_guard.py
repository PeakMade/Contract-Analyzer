"""
Unit tests for token_guard module.
Tests JWT parsing, expiration checking, and error handling.
"""
import pytest
import time
import base64
import json
from app.auth.token_guard import (
    token_exp_soon,
    ensure_token_or_401,
    get_token_info,
    TokenExpiredError,
    _decode_jwt_payload
)


def create_test_jwt(exp: int = None, iat: int = None, **extra_claims) -> str:
    """
    Create a fabricated JWT for testing (not cryptographically signed).
    
    Args:
        exp: Expiration timestamp (defaults to 1 hour from now)
        iat: Issued at timestamp (defaults to now)
        **extra_claims: Additional claims to include in payload
    
    Returns:
        JWT token string (header.payload.signature)
    """
    # Default timestamps
    current_time = int(time.time())
    if exp is None:
        exp = current_time + 3600  # 1 hour from now
    if iat is None:
        iat = current_time
    
    # Create header
    header = {
        "alg": "RS256",
        "typ": "JWT"
    }
    
    # Create payload
    payload = {
        "exp": exp,
        "iat": iat,
        "sub": "test-user-123",
        "aud": "test-audience",
        **extra_claims
    }
    
    # Encode to base64url
    def b64url_encode(data: dict) -> str:
        json_str = json.dumps(data, separators=(',', ':'))
        b64 = base64.urlsafe_b64encode(json_str.encode('utf-8'))
        # Remove padding
        return b64.decode('utf-8').rstrip('=')
    
    header_b64 = b64url_encode(header)
    payload_b64 = b64url_encode(payload)
    
    # Fake signature (not real cryptographic signature)
    signature = "fake_signature_for_testing_only"
    
    return f"{header_b64}.{payload_b64}.{signature}"


class TestDecodeJWTPayload:
    """Tests for _decode_jwt_payload function."""
    
    def test_decode_valid_jwt(self):
        """Test decoding a valid JWT."""
        token = create_test_jwt(exp=1234567890, iat=1234560000)
        payload = _decode_jwt_payload(token)
        
        assert payload['exp'] == 1234567890
        assert payload['iat'] == 1234560000
        assert payload['sub'] == 'test-user-123'
    
    def test_decode_jwt_with_extra_claims(self):
        """Test decoding JWT with custom claims."""
        token = create_test_jwt(custom_claim="test_value", role="admin")
        payload = _decode_jwt_payload(token)
        
        assert payload['custom_claim'] == 'test_value'
        assert payload['role'] == 'admin'
    
    def test_decode_invalid_format(self):
        """Test decoding JWT with invalid format."""
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_jwt_payload("not.a.valid.jwt.token")
        
        with pytest.raises(ValueError, match="Invalid JWT format"):
            _decode_jwt_payload("only_two.parts")
    
    def test_decode_invalid_base64(self):
        """Test decoding JWT with invalid base64."""
        with pytest.raises(ValueError, match="Invalid JWT token"):
            _decode_jwt_payload("header.!!!invalid_base64!!!.signature")


class TestTokenExpSoon:
    """Tests for token_exp_soon function."""
    
    def test_token_not_expiring_soon(self):
        """Test token that has plenty of time left."""
        future_exp = int(time.time()) + 3600  # 1 hour from now
        token = create_test_jwt(exp=future_exp)
        
        assert token_exp_soon(token, skew_sec=120) is False
    
    def test_token_expiring_soon(self):
        """Test token that expires within skew window."""
        near_future_exp = int(time.time()) + 60  # 1 minute from now
        token = create_test_jwt(exp=near_future_exp)
        
        assert token_exp_soon(token, skew_sec=120) is True
    
    def test_token_already_expired(self):
        """Test token that has already expired."""
        past_exp = int(time.time()) - 3600  # 1 hour ago
        token = create_test_jwt(exp=past_exp)
        
        assert token_exp_soon(token, skew_sec=120) is True
    
    def test_token_at_exact_skew_boundary(self):
        """Test token expiring exactly at skew boundary."""
        boundary_exp = int(time.time()) + 120  # Exactly 120 seconds
        token = create_test_jwt(exp=boundary_exp)
        
        # Should be considered expiring soon (<=)
        assert token_exp_soon(token, skew_sec=120) is True
    
    def test_token_missing_exp_claim(self):
        """Test token without exp claim."""
        # Create token manually without exp
        header_payload = {
            "iat": int(time.time()),
            "sub": "test-user"
        }
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(header_payload).encode('utf-8')
        ).decode('utf-8').rstrip('=')
        
        token = f"header.{payload_b64}.signature"
        
        # Should treat missing exp as expired
        assert token_exp_soon(token, skew_sec=120) is True
    
    def test_token_custom_skew(self):
        """Test with custom skew value."""
        exp_5_min = int(time.time()) + 300  # 5 minutes from now
        token = create_test_jwt(exp=exp_5_min)
        
        # Should not be expiring with 2 min skew
        assert token_exp_soon(token, skew_sec=120) is False
        
        # Should be expiring with 10 min skew
        assert token_exp_soon(token, skew_sec=600) is True


class TestEnsureTokenOr401:
    """Tests for ensure_token_or_401 function."""
    
    def test_valid_token_passes(self):
        """Test that valid token is returned."""
        future_exp = int(time.time()) + 3600
        token = create_test_jwt(exp=future_exp)
        
        result = ensure_token_or_401(token, skew_sec=120)
        assert result == token
    
    def test_expired_token_raises(self):
        """Test that expired token raises exception."""
        past_exp = int(time.time()) - 100
        token = create_test_jwt(exp=past_exp)
        
        with pytest.raises(TokenExpiredError, match="SESSION_EXPIRED"):
            ensure_token_or_401(token, skew_sec=120)
    
    def test_expiring_soon_token_raises(self):
        """Test that soon-to-expire token raises exception."""
        soon_exp = int(time.time()) + 60  # 1 minute
        token = create_test_jwt(exp=soon_exp)
        
        with pytest.raises(TokenExpiredError, match="SESSION_EXPIRED"):
            ensure_token_or_401(token, skew_sec=120)
    
    def test_none_token_raises(self):
        """Test that None token raises exception."""
        with pytest.raises(TokenExpiredError, match="SESSION_EXPIRED"):
            ensure_token_or_401(None, skew_sec=120)
    
    def test_empty_token_raises(self):
        """Test that empty string token raises exception."""
        with pytest.raises(TokenExpiredError, match="SESSION_EXPIRED"):
            ensure_token_or_401("", skew_sec=120)


class TestGetTokenInfo:
    """Tests for get_token_info function."""
    
    def test_get_info_valid_token(self):
        """Test getting info from valid token."""
        exp = int(time.time()) + 1800  # 30 minutes from now
        iat = int(time.time()) - 300  # 5 minutes ago
        token = create_test_jwt(exp=exp, iat=iat)
        
        info = get_token_info(token)
        
        assert info['exp'] == exp
        assert info['iat'] == iat
        assert info['is_expired'] is False
        assert 1700 < info['remaining_seconds'] < 1900  # ~30 min (with tolerance)
    
    def test_get_info_expired_token(self):
        """Test getting info from expired token."""
        exp = int(time.time()) - 600  # 10 minutes ago
        token = create_test_jwt(exp=exp)
        
        info = get_token_info(token)
        
        assert info['exp'] == exp
        assert info['is_expired'] is True
        assert info['remaining_seconds'] < 0
    
    def test_get_info_invalid_token(self):
        """Test getting info from invalid token."""
        info = get_token_info("invalid.token.here")
        
        assert info['exp'] is None
        assert info['iat'] is None
        assert info['remaining_seconds'] is None
        assert info['is_expired'] is True
        assert 'error' in info


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""
    
    def test_token_lifecycle(self):
        """Test complete token lifecycle from fresh to expired."""
        # Fresh token (1 hour validity)
        fresh_token = create_test_jwt(exp=int(time.time()) + 3600)
        assert token_exp_soon(fresh_token, skew_sec=120) is False
        assert ensure_token_or_401(fresh_token) == fresh_token
        
        # Nearly expired token (1 minute left)
        nearly_expired = create_test_jwt(exp=int(time.time()) + 60)
        assert token_exp_soon(nearly_expired, skew_sec=120) is True
        with pytest.raises(TokenExpiredError):
            ensure_token_or_401(nearly_expired, skew_sec=120)
        
        # Expired token
        expired = create_test_jwt(exp=int(time.time()) - 60)
        assert token_exp_soon(expired, skew_sec=120) is True
        with pytest.raises(TokenExpiredError):
            ensure_token_or_401(expired, skew_sec=120)
    
    def test_different_skew_values(self):
        """Test behavior with different skew values."""
        # Token expires in 5 minutes
        token = create_test_jwt(exp=int(time.time()) + 300)
        
        # Conservative skew (10 min) - should reject
        with pytest.raises(TokenExpiredError):
            ensure_token_or_401(token, skew_sec=600)
        
        # Standard skew (2 min) - should accept
        assert ensure_token_or_401(token, skew_sec=120) == token
        
        # No skew - should accept
        assert ensure_token_or_401(token, skew_sec=0) == token


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
