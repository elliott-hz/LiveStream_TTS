"""
FastAPI HTTP routes for avatar-svc.

Provides REST-style endpoints mirroring the gRPC API for health checks and external integrations.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError
from libs.common.logging import get_logger

from models.avatar import Avatar
from services.avatar_service import AvatarService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    """Wire the database session factory into routes."""
    global _get_db
    _get_db = get_db_callable


async def _get_service() -> AsyncIterator[AvatarService]:
    """FastAPI dependency: yield an AvatarService with a request-scoped session."""
    if _get_db is None:
        raise RuntimeError("Routes not configured — call configure_routes first")
    async with _get_db() as session:
        yield AvatarService(db=session)


# ── Health ──


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "avatar-svc"}


# ── Avatars ──


@router.get("/avatars")
async def list_avatars(
    store_id: str = Query(..., description="Store ID"),
    avatar_type: str | None = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: AvatarService = Depends(_get_service),
) -> dict[str, Any]:
    """List avatars with optional filters and pagination."""
    try:
        avatars, total = await svc.list_avatars(
            store_id=store_id,
            avatar_type=avatar_type,
            page=page,
            page_size=page_size,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "avatars": [_avatar_dict(a) for a in avatars],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


@router.post("/avatars", status_code=201)
async def create_avatar(
    body: dict[str, Any],
    svc: AvatarService = Depends(_get_service),
) -> dict[str, Any]:
    """Create a new avatar."""
    try:
        avatar = await svc.create_avatar(
            store_id=body.get("store_id", ""),
            name=body.get("name", ""),
            avatar_type=body.get("type", "2d_real"),
            custom_params=body.get("custom_params"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _avatar_dict(avatar)


@router.get("/avatars/{avatar_id}")
async def get_avatar(
    avatar_id: str,
    svc: AvatarService = Depends(_get_service),
) -> dict[str, Any]:
    """Get a single avatar by ID."""
    try:
        avatar = await svc.get_avatar(avatar_id=avatar_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _avatar_dict(avatar)


@router.put("/avatars/{avatar_id}")
async def update_avatar(
    avatar_id: str,
    body: dict[str, Any],
    svc: AvatarService = Depends(_get_service),
) -> dict[str, Any]:
    """Partially update an avatar."""
    try:
        avatar = await svc.update_avatar(
            avatar_id=avatar_id,
            name=body.get("name"),
            custom_params=body.get("custom_params"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _avatar_dict(avatar)


@router.delete("/avatars/{avatar_id}", status_code=204)
async def delete_avatar(
    avatar_id: str,
    svc: AvatarService = Depends(_get_service),
) -> None:
    """Delete an avatar."""
    try:
        await svc.delete_avatar(avatar_id=avatar_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)


# ── Clone Tasks ──


@router.post("/avatars/{avatar_id}/clone", status_code=201)
async def start_clone(
    avatar_id: str,
    svc: AvatarService = Depends(_get_service),
) -> dict[str, Any]:
    """Start an avatar clone task."""
    try:
        task = await svc.start_clone(avatar_id=avatar_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _clone_task_dict(task)


@router.get("/clone-tasks/{task_id}")
async def get_clone_task(
    task_id: str,
    svc: AvatarService = Depends(_get_service),
) -> dict[str, Any]:
    """Get a clone task by ID."""
    try:
        task = await svc.get_clone_task(task_id=task_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _clone_task_dict(task)


# ── Converters ──


def _avatar_dict(avatar: Avatar) -> dict[str, Any]:
    return {
        "avatar_id": avatar.avatar_id,
        "store_id": avatar.store_id,
        "name": avatar.name,
        "type": avatar.avatar_type,
        "status": avatar.status,
        "thumbnail_url": avatar.thumbnail_url or "",
        "model_path": avatar.model_path or "",
        "custom_params": avatar.custom_params or {},
        "created_by": avatar.created_by or "",
        "updated_by": avatar.updated_by or "",
        "created_at": int(avatar.created_at.timestamp() * 1000),
        "updated_at": int(avatar.updated_at.timestamp() * 1000),
    }


def _clone_task_dict(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "avatar_id": task.avatar_id,
        "status": task.status,
        "progress_percent": task.progress_percent,
        "error_message": task.error_message or "",
        "created_at": int(task.created_at.timestamp() * 1000),
        "completed_at": int(task.completed_at.timestamp() * 1000) if task.completed_at else None,
    }


def _app_error_status(exc: AppError) -> int:
    code = exc.code.value if hasattr(exc.code, "value") else exc.code
    if 1001 <= code <= 1004:
        return 401 if code == 1001 else 403
    if 2001 <= code <= 2004:
        return 400
    if 3001 <= code <= 3008:
        return 404
    if 4001 <= code <= 4007:
        return 409
    return 500
