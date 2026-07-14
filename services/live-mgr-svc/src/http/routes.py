"""HTTP (FastAPI) routes for the live-mgr-svc.

Provides REST endpoints for live room CRUD, state machine transitions,
and a health check.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from libs.common.errors import AppError
from libs.common.logging import get_logger
from services.live_mgr_svc.src.services.live_room_service import LiveRoomService
from services.live_mgr_svc.src.services.playlist_service import PlaylistService

logger = get_logger(__name__)


# ── Request / Response schemas ──


class CreateLiveRoomRequest(BaseModel):
    store_id: str = Field(..., description="Store / merchant ID")
    title: str = Field(..., min_length=1, max_length=200, description="Live room title")
    avatar_id: str | None = None
    voice_id: str | None = None
    target_platforms: list[str] = Field(default_factory=list)


class UpdateLiveRoomRequest(BaseModel):
    title: str | None = None
    cover_url: str | None = None
    avatar_id: str | None = None
    voice_id: str | None = None


class LiveRoomResponse(BaseModel):
    live_room_id: str
    store_id: str
    title: str
    cover_url: str
    status: str
    avatar_id: str
    voice_id: str
    script_id: str
    stream_config: dict[str, Any] = {}
    loop_rule: dict[str, Any] = {}
    target_platforms: list[str] = []
    created_by: str = ""
    updated_by: str = ""
    created_at: int = 0
    updated_at: int = 0


class ListLiveRoomsResponse(BaseModel):
    live_rooms: list[LiveRoomResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "live-mgr-svc"
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    error: str
    code: int


class StopRequest(BaseModel):
    reason: str = ""


# ── Router factory ──


def create_router(
    live_room_service: LiveRoomService,
    playlist_service: PlaylistService,
) -> APIRouter:
    """Create the FastAPI router with live room endpoints.

    Args:
        live_room_service: LiveRoom CRUD and state machine instance.
        playlist_service: Playlist CRUD instance.
    """
    router = APIRouter()

    # ── Health ──

    @router.get(
        "/api/v1/health",
        response_model=HealthResponse,
        summary="Service health check",
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    # ── Live Room CRUD ──

    @router.post(
        "/api/v1/live-rooms",
        response_model=LiveRoomResponse,
        status_code=201,
        summary="Create a new live room",
    )
    async def create_live_room(body: CreateLiveRoomRequest) -> LiveRoomResponse:
        try:
            data = body.model_dump()
            result = await live_room_service.create_live_room(data)
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.get(
        "/api/v1/live-rooms",
        response_model=ListLiveRoomsResponse,
        summary="List live rooms",
    )
    async def list_live_rooms(
        store_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ListLiveRoomsResponse:
        try:
            result = await live_room_service.list_live_rooms(
                store_id=store_id,
                status=status,
                page=page,
                page_size=page_size,
            )
            return ListLiveRoomsResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.get(
        "/api/v1/live-rooms/{live_room_id}",
        response_model=LiveRoomResponse,
        summary="Get a live room by ID",
    )
    async def get_live_room(live_room_id: str) -> LiveRoomResponse:
        try:
            result = await live_room_service.get_live_room(live_room_id)
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.put(
        "/api/v1/live-rooms/{live_room_id}",
        response_model=LiveRoomResponse,
        summary="Update a live room",
    )
    async def update_live_room(
        live_room_id: str, body: UpdateLiveRoomRequest
    ) -> LiveRoomResponse:
        try:
            updates = body.model_dump(exclude_unset=True)
            result = await live_room_service.update_live_room(
                live_room_id=live_room_id, updates=updates
            )
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    # ── State Machine Transitions ──

    @router.post(
        "/api/v1/live-rooms/{live_room_id}/start",
        response_model=LiveRoomResponse,
        summary="Start a live broadcast",
    )
    async def start_live(live_room_id: str) -> LiveRoomResponse:
        try:
            result = await live_room_service.start_live(live_room_id)
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.post(
        "/api/v1/live-rooms/{live_room_id}/pause",
        response_model=LiveRoomResponse,
        summary="Pause a live broadcast",
    )
    async def pause_live(live_room_id: str) -> LiveRoomResponse:
        try:
            result = await live_room_service.pause_live(live_room_id)
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.post(
        "/api/v1/live-rooms/{live_room_id}/resume",
        response_model=LiveRoomResponse,
        summary="Resume a paused live broadcast",
    )
    async def resume_live(live_room_id: str) -> LiveRoomResponse:
        try:
            result = await live_room_service.resume_live(live_room_id)
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.post(
        "/api/v1/live-rooms/{live_room_id}/stop",
        response_model=LiveRoomResponse,
        summary="Stop a live broadcast",
    )
    async def stop_live(live_room_id: str) -> LiveRoomResponse:
        try:
            result = await live_room_service.stop_live(live_room_id)
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    @router.post(
        "/api/v1/live-rooms/{live_room_id}/emergency-stop",
        response_model=LiveRoomResponse,
        summary="Emergency stop a live broadcast",
    )
    async def emergency_stop(
        live_room_id: str, body: StopRequest = StopRequest()
    ) -> LiveRoomResponse:
        try:
            result = await live_room_service.emergency_stop(
                live_room_id=live_room_id, reason=body.reason
            )
            return LiveRoomResponse(**result)
        except AppError as e:
            raise HTTPException(
                status_code=_app_error_status(e), detail=str(e)
            )

    return router


# ── Helpers ──


def _app_error_status(error: AppError) -> int:
    """Map an ``AppError`` to an HTTP status code."""
    mapping = {
        1001: 401,  # UNAUTHENTICATED
        1002: 403,  # PERMISSION_DENIED
        1003: 401,  # TOKEN_EXPIRED
        2001: 400,  # INVALID_ARGUMENT
        2002: 400,  # MISSING_REQUIRED_FIELD
        3001: 404,  # NOT_FOUND
        3005: 404,  # LIVE_ROOM_NOT_FOUND
        4001: 409,  # DUPLICATE_RESOURCE
        4002: 409,  # RESOURCE_IN_USE
        4005: 409,  # LIVE_ROOM_NOT_IN_STATE
        5001: 500,  # INTERNAL_ERROR
    }
    return mapping.get(error.code.value, 500)
