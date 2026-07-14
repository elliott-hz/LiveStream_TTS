"""
FastAPI dependencies for route handlers.

Provides the get_current_user dependency that extracts the authenticated
user from request.state (set by auth middleware).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from ..middleware.auth import UserInfo


async def get_current_user(request: Request) -> UserInfo:
    """Dependency: extract the authenticated user from the request.

    The AuthMiddleware should have already validated the JWT and
    attached the UserInfo to request.state.user. This dependency
    simply retrieves it and raises 401 if missing.

    Usage:
        @router.get("/api/v1/users/me")
        async def me(user=Depends(get_current_user)):
            return {"user_id": user.user_id}
    """
    user: UserInfo | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
