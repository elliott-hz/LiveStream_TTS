"""
FastAPI HTTP routes for voice-svc.

Provides REST-style endpoints mirroring the gRPC API for health checks and external integrations.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError
from libs.common.logging import get_logger

from models.voice import Voice
from .services.voice_service import VoiceService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    """Wire the database session factory into routes."""
    global _get_db
    _get_db = get_db_callable


async def _get_service() -> AsyncIterator[VoiceService]:
    """FastAPI dependency: yield a VoiceService with a request-scoped session."""
    if _get_db is None:
        raise RuntimeError("Routes not configured — call configure_routes first")
    async with _get_db() as session:
        yield VoiceService(db=session)


# ── Health ──


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "voice-svc"}


# ── Voices ──


@router.get("/voices")
async def list_voices(
    store_id: str = Query(..., description="Store ID"),
    gender: str | None = Query(None),
    style: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """List voices with optional filters and pagination."""
    try:
        voices, total = await svc.list_voices(
            store_id=store_id,
            gender=gender,
            style=style,
            page=page,
            page_size=page_size,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "voices": [_voice_dict(v) for v in voices],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


@router.post("/voices", status_code=201)
async def create_voice(
    body: dict[str, Any],
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """Create a new voice."""
    try:
        voice = await svc.create_voice(
            store_id=body.get("store_id", ""),
            name=body.get("name", ""),
            gender=body.get("gender", "male"),
            age_range=body.get("age_range", "25-35"),
            language=body.get("language", "zh-CN"),
            style=body.get("style", "professional"),
            is_public=body.get("is_public", False),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _voice_dict(voice)


@router.get("/voices/{voice_id}")
async def get_voice(
    voice_id: str,
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """Get a single voice by ID."""
    try:
        voice = await svc.get_voice(voice_id=voice_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _voice_dict(voice)


@router.put("/voices/{voice_id}")
async def update_voice(
    voice_id: str,
    body: dict[str, Any],
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """Partially update a voice."""
    try:
        voice = await svc.update_voice(
            voice_id=voice_id,
            name=body.get("name"),
            age_range=body.get("age_range"),
            style=body.get("style"),
            is_public=body.get("is_public"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _voice_dict(voice)


@router.delete("/voices/{voice_id}", status_code=204)
async def delete_voice(
    voice_id: str,
    svc: VoiceService = Depends(_get_service),
) -> None:
    """Delete a voice."""
    try:
        await svc.delete_voice(voice_id=voice_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)


# ── Clone Tasks ──


@router.post("/voices/{voice_id}/clone", status_code=201)
async def start_clone(
    voice_id: str,
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """Start a voice clone task."""
    try:
        task = await svc.start_clone(voice_id=voice_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _clone_task_dict(task)


@router.get("/clone-tasks/{task_id}")
async def get_clone_task(
    task_id: str,
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """Get a clone task by ID."""
    try:
        task = await svc.get_clone_task(task_id=task_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _clone_task_dict(task)


# ── Preview ──


@router.post("/voices/{voice_id}/preview")
async def preview_voice(
    voice_id: str,
    body: dict[str, Any],
    svc: VoiceService = Depends(_get_service),
) -> dict[str, Any]:
    """Preview a voice speaking the given text."""
    try:
        result = await svc.preview_voice(
            voice_id=voice_id,
            text=body.get("text", ""),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return result


# ── Converters ──


def _voice_dict(voice: Voice) -> dict[str, Any]:
    return {
        "voice_id": voice.voice_id,
        "store_id": voice.store_id,
        "name": voice.name,
        "gender": voice.gender,
        "age_range": voice.age_range,
        "language": voice.language,
        "style": voice.style,
        "status": voice.status,
        "is_public": voice.is_public,
        "quality_metrics": voice.quality_metrics or {},
        "created_by": voice.created_by or "",
        "updated_by": voice.updated_by or "",
        "created_at": int(voice.created_at.timestamp() * 1000),
        "updated_at": int(voice.updated_at.timestamp() * 1000),
    }


def _clone_task_dict(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "voice_id": task.voice_id,
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
