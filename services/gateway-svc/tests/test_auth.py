"""
Tests for the JWT authentication middleware.

Covers:
  - Valid token → request passes with user attached
  - Invalid token → 401 response
  - Expired token → 401 with token_expired error
  - Missing token → 401
  - No token on public endpoints → passes through
  - Malformed Authorization header → 401
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

# Monorepo path setup
# Add repo root and the gateway-svc parent so we can import src.middleware.*
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SVC_DIR = _REPO_ROOT / "services" / "gateway-svc"
for p in [str(_REPO_ROOT), str(_SVC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import via the src package so relative imports (..config) resolve correctly
from src.middleware.auth import (
    SKIP_PATTERNS,
    AuthMiddleware,
    UserInfo,
    _should_skip_auth,
    create_test_token,
)
from src.config import config


# ── Fixtures ──


@pytest.fixture
def app():
    """Create a minimal FastAPI app with auth middleware for testing."""
    app = FastAPI()

    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/v1/auth/login")
    async def login():
        return {"token": "fake"}

    @app.get("/api/v1/protected")
    async def protected(request: Request):
        user = request.state.user
        return {
            "user_id": user.user_id,
            "role": user.role,
            "permissions": user.permissions,
            "store_id": user.store_id,
        }

    @app.get("/api/v1/admin/dashboard")
    async def admin_dashboard(request: Request):
        return {"admin": True}

    app.add_middleware(AuthMiddleware)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ── Helpers ──


def _make_token(user_id: str = "u_test_001", **overrides) -> str:
    """Create a valid test JWT token."""
    return create_test_token(user_id=user_id, **overrides)


# ── Tests ──


@pytest.mark.asyncio
async def test_public_health_endpoint_no_auth(client):
    """Health endpoint should be accessible without authentication."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_public_auth_login_endpoint_no_auth(client):
    """Auth login endpoint should be accessible without authentication."""
    response = await client.get("/api/v1/auth/login")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token(client):
    """Protected endpoint should return user info with a valid token."""
    token = _make_token(user_id="u_test_001", role="admin", permissions=["read", "write"], store_id="s_001")
    response = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "u_test_001"
    assert data["role"] == "admin"
    assert data["permissions"] == ["read", "write"]
    assert data["store_id"] == "s_001"


@pytest.mark.asyncio
async def test_protected_endpoint_missing_token(client):
    """Protected endpoint should return 401 without a token."""
    response = await client.get("/api/v1/protected")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == 1001


@pytest.mark.asyncio
async def test_protected_endpoint_invalid_token(client):
    """Protected endpoint should return 401 with an invalid token."""
    response = await client.get(
        "/api/v1/protected",
        headers={"Authorization": "Bearer invalidtoken123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_expired_token(client):
    """Protected endpoint should return 401 with an expired token."""
    token = _make_token(user_id="u_test_001", expire_minutes=-5)  # Expired 5 min ago
    response = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == 1003  # TOKEN_EXPIRED


@pytest.mark.asyncio
async def test_protected_endpoint_malformed_header(client):
    """Protected endpoint should return 401 with a malformed Authorization header."""
    response = await client.get(
        "/api/v1/protected",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_empty_bearer(client):
    """Protected endpoint should return 401 with an empty Bearer token."""
    response = await client.get(
        "/api/v1/protected",
        headers={"Authorization": "Bearer "},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_skip_pattern_health():
    """Test that health endpoint matches skip pattern."""
    assert _should_skip_auth("/api/v1/health") is True


@pytest.mark.asyncio
async def test_skip_pattern_auth():
    """Test that auth endpoints match skip pattern."""
    assert _should_skip_auth("/api/v1/auth/login") is True
    assert _should_skip_auth("/api/v1/auth/register") is True
    assert _should_skip_auth("/api/v1/auth/refresh") is True


@pytest.mark.asyncio
async def test_no_skip_for_protected():
    """Test that protected endpoints do not match skip pattern."""
    assert _should_skip_auth("/api/v1/products") is False
    assert _should_skip_auth("/api/v1/tts/synthesize") is False
    assert _should_skip_auth("/api/v1/users/me") is False


@pytest.mark.asyncio
async def test_user_info_has_permission():
    """Test UserInfo.has_permission method."""
    user = UserInfo(
        user_id="u_test",
        role="user",
        permissions=["read", "write"],
    )
    assert user.has_permission("read") is True
    assert user.has_permission("write") is True
    assert user.has_permission("admin") is False


@pytest.mark.asyncio
async def test_user_info_is_admin():
    """Test UserInfo.is_admin method."""
    admin = UserInfo(user_id="u_adm", role="admin", permissions=[])
    super_admin = UserInfo(user_id="u_sup", role="super_admin", permissions=[])
    regular = UserInfo(user_id="u_usr", role="user", permissions=[])

    assert admin.is_admin() is True
    assert super_admin.is_admin() is True
    assert regular.is_admin() is False


@pytest.mark.asyncio
async def test_create_test_token_defaults():
    """Test create_test_token produces valid tokens."""
    token = create_test_token()
    payload = jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algorithm])
    assert payload["sub"] == "u_test_001"
    assert payload["role"] == "user"
    assert "exp" in payload
    assert "iat" in payload
