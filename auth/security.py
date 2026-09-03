"""Authentication and security middleware"""
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import jwt

from core import db
from core.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

API_KEY_HEADER = "X-API-Key"

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class TokenPayload:
    def __init__(self, sub: str, tenant_id: str, roles: list, exp: datetime):
        self.sub = sub
        self.tenant_id = tenant_id
        self.roles = roles
        self.exp = exp


def create_access_token(username: str, tenant_id: str, roles: list, expires_delta: timedelta = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": username, "tenant_id": tenant_id, "roles": roles, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return TokenPayload(
            sub=payload.get("sub"),
            tenant_id=payload.get("tenant_id"),
            roles=payload.get("roles", []),
            exp=datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc),
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate against the persisted user store (SQLite)."""
    user = db.get_user(username)
    if not user or not user.get("is_active"):
        return None
    if not db.verify_password(password, user["password_hash"]):
        return None
    user["roles"] = user["roles"].split(",")
    return user


def validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    key_data = db.get_api_key(api_key)
    if not key_data:
        return None
    key_data["permissions"] = key_data["permissions"].split(",")
    return key_data


def generate_api_key(tenant_id: str, permissions: Optional[list] = None) -> str:
    return db.create_api_key(tenant_id, permissions)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    api_key: str = Depends(api_key_header),
) -> Dict[str, Any]:
    """Get the current user from a JWT token or an API key. Raises if neither
    is present or valid - there is no anonymous fallback here anymore, because
    a header-only fallback made every 'protected' route effectively public."""
    if credentials:
        token_data = decode_access_token(credentials.credentials)
        return {
            "username": token_data.sub,
            "tenant_id": token_data.tenant_id,
            "roles": token_data.roles,
            "auth_method": "jwt",
        }

    if api_key:
        key_data = validate_api_key(api_key)
        if key_data:
            return {
                "username": "api_user",
                "tenant_id": key_data["tenant_id"],
                "roles": key_data.get("permissions", []),
                "auth_method": "api_key",
            }
        raise AuthenticationError("Invalid API key")

    raise AuthenticationError("No authentication credentials provided")


def require_role(required_role: str):
    async def role_checker(user: Dict = Depends(get_current_user)):
        if required_role not in user.get("roles", []):
            raise AuthorizationError(f"Role '{required_role}' required")
        return user

    return role_checker


def require_permission(permission: str):
    async def permission_checker(user: Dict = Depends(get_current_user)):
        if permission not in user.get("roles", []) and "admin" not in user.get("roles", []):
            raise AuthorizationError(f"Permission '{permission}' required")
        return user

    return permission_checker


class RateLimiter:
    """Simple in-memory rate limiter. Fine to keep in-process (it's a
    performance guard, not a source of truth) - a multi-instance deployment
    would move this to Redis, noted in README."""

    def __init__(self):
        self._requests: Dict[str, list] = {}

    def check_rate_limit(self, key: str, limit: int = 100, window_seconds: int = 60) -> bool:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        bucket = self._requests.setdefault(key, [])
        bucket[:] = [ts for ts in bucket if ts > window_start]

        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


rate_limiter = RateLimiter()


async def check_rate_limit(request: Request, user: Dict = Depends(get_current_user)):
    """Authenticated + rate-limited dependency. Auth is now mandatory, and the
    tenant_id used everywhere downstream comes from the authenticated
    principal - never from a client-supplied header - so one tenant can no
    longer read another tenant's data just by changing a header."""
    key = f"{user['tenant_id']}:{request.client.host if request.client else 'unknown'}"
    limit = 1000 if user["auth_method"] == "api_key" else 300

    if not rate_limiter.check_rate_limit(key, limit=limit):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    return user
