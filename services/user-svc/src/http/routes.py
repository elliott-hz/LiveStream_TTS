"""HTTP (FastAPI) routes for the user-svc.

Provides REST endpoints for auth (register, login, refresh) and a
user profile endpoint, plus a health check.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from libs.common.errors import AppError
from libs.common.logging import get_logger
from services.user_svc.src.services.auth_service import AuthService
from services.user_svc.src.services.user_service import UserService

logger = get_logger(__name__)


# ── Request / Response schemas ──


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    password: str = Field(..., min_length=6)
    phone: str | None = None
    store_name: str | None = None


class LoginRequest(BaseModel):
    account: str = Field(..., description="Email or phone")
    password: str = Field(...)


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "user-svc"
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    error: str
    code: int


# ── Router factory ──


def create_router(
    auth_service: AuthService, user_service: UserService
) -> APIRouter:
    """Create the FastAPI router with auth and user endpoints.

    Args:
        auth_service: Auth business logic instance.
        user_service: User CRUD business logic instance.
    """
    router = APIRouter()

    # ── Auth endpoints ──

    @router.post(
        "/api/v1/auth/register",
        response_model=AuthResponse,
        summary="Register a new user account",
    )
    async def register(body: RegisterRequest) -> AuthResponse:
        try:
            result = await auth_service.register(
                username=body.username,
                email=body.email,
                password=body.password,
                phone=body.phone,
                store_name=body.store_name,
            )
            return AuthResponse(**result)
        except AppError as e:
            raise HTTPException(status_code=_app_error_status(e), detail=str(e))

    @router.post(
        "/api/v1/auth/login",
        response_model=AuthResponse,
        summary="Authenticate and receive JWT tokens",
    )
    async def login(body: LoginRequest) -> AuthResponse:
        try:
            result = await auth_service.login(
                account=body.account, password=body.password
            )
            return AuthResponse(**result)
        except AppError as e:
            raise HTTPException(status_code=_app_error_status(e), detail=str(e))

    @router.post(
        "/api/v1/auth/refresh",
        response_model=AuthResponse,
        summary="Refresh an expired access token",
    )
    async def refresh(body: RefreshRequest) -> AuthResponse:
        try:
            result = await auth_service.refresh_token(
                refresh_token=body.refresh_token
            )
            return AuthResponse(**result)
        except AppError as e:
            raise HTTPException(status_code=_app_error_status(e), detail=str(e))

    # ── User endpoints ──

    @router.get(
        "/api/v1/users/me",
        response_model=dict[str, Any],
        summary="Get the currently authenticated user's profile",
    )
    async def get_me(
        authorization: str = Header(...),
    ) -> dict[str, Any]:
        token = _extract_bearer(authorization)
        try:
            payload = auth_service.decode_token(token)
        except AppError as e:
            raise HTTPException(status_code=401, detail=str(e))

        user_dict = await user_service.get_user(user_id=payload["user_id"])
        return user_dict

    # ── Health ──

    @router.get(
        "/api/v1/health",
        response_model=HealthResponse,
        summary="Service health check",
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    return router


# ── Helpers ──


def _extract_bearer(authorization: str) -> str:
    """Extract the Bearer token from an Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format"
        )
    return authorization[len("Bearer "):]


def _app_error_status(error: AppError) -> int:
    """Map an ``AppError`` to an HTTP status code."""
    mapping = {
        1001: 401,  # UNAUTHENTICATED
        1002: 403,  # PERMISSION_DENIED
        1003: 401,  # TOKEN_EXPIRED
        2001: 400,  # INVALID_ARGUMENT
        2002: 400,  # MISSING_REQUIRED_FIELD
        3001: 404,  # NOT_FOUND
        3002: 404,  # USER_NOT_FOUND
        4001: 409,  # DUPLICATE_RESOURCE
        5001: 500,  # INTERNAL_ERROR
    }
    return mapping.get(error.code.value, 500)
