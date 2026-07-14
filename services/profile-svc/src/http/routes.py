"""
FastAPI HTTP routes for profile-svc.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query

from libs.common.errors import AppError
from libs.common.logging import get_logger

from services.profile_service import ProfileService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    global _get_db
    _get_db = get_db_callable


async def _get_svc() -> AsyncIterator[ProfileService]:
    if _get_db is None:
        raise RuntimeError("Routes not configured")
    async with _get_db() as session:
        yield ProfileService(db=session)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "profile-svc"}


@router.get("/profiles/{platform_user_id}")
async def get_profile(
    platform_user_id: str,
    platform: str = Query(..., description="Platform name"),
    svc: ProfileService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.get_profile(
            platform_user_id=platform_user_id,
            platform=platform,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


@router.put("/profiles/{platform_user_id}")
async def update_profile(
    platform_user_id: str,
    body: dict[str, Any],
    svc: ProfileService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.update_profile(
            platform_user_id=platform_user_id,
            platform=body.get("platform", ""),
            nickname=body.get("nickname"),
            tags=body.get("tags"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


@router.post("/events/track")
async def track_event(
    body: dict[str, Any],
    svc: ProfileService = Depends(_get_svc),
) -> dict[str, str]:
    try:
        await svc.track_event(
            platform_user_id=body.get("platform_user_id", ""),
            platform=body.get("platform", ""),
            event_type=body.get("event_type", ""),
            live_room_id=body.get("live_room_id", ""),
            properties=body.get("properties"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"status": "ok"}


@router.get("/segments/{segment_id}")
async def get_segment(
    segment_id: str,
    svc: ProfileService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        segment = await svc.get_segment(segment_id=segment_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {
        "segment_id": segment.segment_id,
        "store_id": segment.store_id,
        "name": segment.name,
        "rule_json": segment.rule_json,
        "audience_size": segment.audience_size,
    }


def _app_error_status(exc: AppError) -> int:
    code = exc.code.value if hasattr(exc.code, "value") else exc.code
    if 2001 <= code <= 2004:
        return 400
    if 3001 <= code <= 3008:
        return 404
    if 4001 <= code <= 4007:
        return 409
    return 500
