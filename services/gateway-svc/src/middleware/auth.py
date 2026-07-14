"""
JWT Authentication Middleware for FastAPI.

Extracts and validates Bearer tokens from the Authorization header.
Attaches user info to request.state.user for downstream handlers.

Skip patterns (no auth required):
  - /api/v1/health
  - /api/v1/auth/* (register, login, refresh)
  - /docs, /openapi.json (OpenAPI docs)
"""

from __future__ import annotations

import re
import time
from typing import Any

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from libs.common.logging import get_logger

from ..config import config

logger = get_logger(__name__)

# ── Skip patterns (no auth required) ──

SKIP_PATTERNS: list[re.Pattern] = [
    re.compile(r"^/api/v1/health$"),
    re.compile(r"^/api/v1/auth/"),
    re.compile(r"^/docs$"),
    re.compile(r"^/openapi.json$"),
    re.compile(r"^/redoc$"),
    re.compile(r"^/$"),
]


def _should_skip_auth(path: str) -> bool:
    """Check if the request path should skip authentication."""
    for pattern in SKIP_PATTERNS:
        if pattern.match(path):
            return True
    return False


# ── User info dataclass (attached to request.state) ──


class UserInfo:
    """Authenticated user information attached to request.state.user."""

    def __init__(
        self,
        user_id: str,
        role: str,
        permissions: list[str],
        store_id: str | None = None,
        token_payload: dict[str, Any] | None = None,
    ):
        self.user_id = user_id
        self.role = role
        self.permissions = permissions
        self.store_id = store_id
        self.token_payload = token_payload or {}

    def has_permission(self, permission: str) -> bool:
        """Check if the user has a specific permission."""
        return permission in self.permissions

    def is_admin(self) -> bool:
        """Check if the user has the admin role."""
        return self.role in ("admin", "super_admin")


# ── Middleware ──


class AuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for JWT authentication.

    Extracts and validates Bearer tokens from the Authorization header.
    On success, attaches a UserInfo object to request.state.user.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip auth for public endpoints
        if _should_skip_auth(request.url.path):
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning(
                "auth.missing_token",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": 1001,
                        "message": "Missing or invalid Authorization header. "
                        "Expected format: Bearer <token>",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]  # Strip "Bearer "

        # Decode and verify JWT
        try:
            payload = jwt.decode(
                token,
                config.jwt_secret,
                algorithms=[config.jwt_algorithm],
                options={"verify_exp": True},
            )
        except jwt.ExpiredSignatureError:
            logger.warning("auth.token_expired", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": 1003,
                        "message": "Token has expired. Please refresh your token.",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as exc:
            logger.warning("auth.invalid_token", path=request.url.path, error=str(exc))
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": 1001,
                        "message": f"Invalid token: {str(exc)}",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract user info from payload
        user = UserInfo(
            user_id=payload.get("sub", payload.get("user_id", "")),
            role=payload.get("role", "user"),
            permissions=payload.get("permissions", []),
            store_id=payload.get("store_id"),
            token_payload=payload,
        )

        if not user.user_id:
            logger.warning("auth.missing_user_id", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": 1001,
                        "message": "Token payload missing user identifier (sub/user_id).",
                    }
                },
            )

        # Attach user to request state
        request.state.user = user

        return await call_next(request)


# ── Token creation utility (used by tests) ──


def create_test_token(
    user_id: str = "u_test_001",
    role: str = "user",
    permissions: list[str] | None = None,
    store_id: str | None = None,
    expire_minutes: int | None = None,
    **extra: Any,
) -> str:
    """Create a JWT token for testing purposes."""
    expire_m = expire_minutes or config.jwt_access_expire_minutes
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "permissions": permissions or ["read"],
        "store_id": store_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + expire_m * 60,
    }
    payload.update(extra)
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)
