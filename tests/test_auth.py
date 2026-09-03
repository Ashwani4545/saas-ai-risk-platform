"""Tests for authentication and security"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.security import (
    create_access_token,
    decode_access_token,
    authenticate_user,
    validate_api_key,
    AuthenticationError
)
from core.db import verify_password


class TestAuthentication:
    """Test authentication functions"""
    
    def test_create_and_decode_token(self):
        """Test JWT token creation and decoding"""
        token = create_access_token(
            username="testuser",
            tenant_id="tenant_1",
            roles=["user", "predict"]
        )
        
        assert token is not None
        
        payload = decode_access_token(token)
        assert payload.sub == "testuser"
        assert payload.tenant_id == "tenant_1"
        assert "user" in payload.roles
    
    def test_authenticate_user_success(self):
        """Test successful user authentication"""
        user = authenticate_user("admin", "admin123")
        
        assert user is not None
        assert user["tenant_id"] == "admin"
        assert "admin" in user["roles"]
    
    def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password"""
        user = authenticate_user("admin", "wrongpassword")
        
        assert user is None
    
    def test_authenticate_user_nonexistent(self):
        """Test authentication with non-existent user"""
        user = authenticate_user("nonexistent", "password")
        
        assert user is None
    
    def test_validate_api_key_success(self):
        """Test API key validation"""
        result = validate_api_key("demo-api-key-tenant1")
        
        assert result is not None
        assert result["tenant_id"] == "tenant_1"
    
    def test_validate_api_key_invalid(self):
        """Test invalid API key"""
        result = validate_api_key("invalid-key")
        
        assert result is None
    
    def test_verify_password(self):
        """Test password verification"""
        import hashlib
        password = "testpassword"
        hashed = hashlib.sha256(password.encode()).hexdigest()
        
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False


class TestTokenExpiry:
    """Test token expiration"""
    
    def test_expired_token(self):
        """Test that expired tokens raise error"""
        from datetime import timedelta
        
        # Create token with negative expiry (already expired)
        token = create_access_token(
            username="test",
            tenant_id="test",
            roles=["user"],
            expires_delta=timedelta(seconds=-1)
        )
        
        with pytest.raises(AuthenticationError):
            decode_access_token(token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
