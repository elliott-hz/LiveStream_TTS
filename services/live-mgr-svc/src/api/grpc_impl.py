"""gRPC service implementation for the LiveManagerService proto.

Implements all 13 RPCs defined in ``live-mgr/v1/live_mgr.proto``:
  - Live Room CRUD: Create, Get, Update, List
  - State Machine: Start, Pause, Resume, Stop, EmergencyStop
  - Playlist: Create, Update, Get
  - Stream Config: Get, Update
"""

from __future__ import annotations

from typing import Any

import grpc
from google.protobuf.json_format import MessageToDict

from libs.common.errors import AppError, Domain, ErrorCode
from libs.common.logging import get_logger
from libs.proto.common.v1 import common_pb2
from libs.proto.live_mgr.v1 import live_mgr_pb2, live_mgr_pb2_grpc
from services.live_mgr_svc.src.services.live_room_service import LiveRoomService
from services.live_mgr_svc.src.services.playlist_service import PlaylistService
from services.live_mgr_svc.src.state_machine.live_state import (
    LiveStatus,
    live_status_to_proto,
    proto_to_live_status,
)

logger = get_logger(__name__)

# ── Enum mapping helpers ──

_STATUS_TO_PROTO = {
    LiveStatus.DRAFT: live_mgr_pb2.LIVE_ROOM_STATUS_DRAFT,
    LiveStatus.READY: live_mgr_pb2.LIVE_ROOM_STATUS_READY,
    LiveStatus.LIVE: live_mgr_pb2.LIVE_ROOM_STATUS_LIVE,
    LiveStatus.PAUSED: live_mgr_pb2.LIVE_ROOM_STATUS_PAUSED,
    LiveStatus.ENDED: live_mgr_pb2.LIVE_ROOM_STATUS_ENDED,
    LiveStatus.ERROR: live_mgr_pb2.LIVE_ROOM_STATUS_ERROR,
}

_PROTO_TO_STATUS_STR = {
    live_mgr_pb2.LIVE_ROOM_STATUS_DRAFT: "draft",
    live_mgr_pb2.LIVE_ROOM_STATUS_READY: "ready",
    live_mgr_pb2.LIVE_ROOM_STATUS_LIVE: "live",
    live_mgr_pb2.LIVE_ROOM_STATUS_PAUSED: "paused",
    live_mgr_pb2.LIVE_ROOM_STATUS_ENDED: "ended",
    live_mgr_pb2.LIVE_ROOM_STATUS_ERROR: "error",
}


class LiveManagerServicer(live_mgr_pb2_grpc.LiveManagerServiceServicer):
    """gRPC servicer for the LiveManagerService.

    Wraps :class:`LiveRoomService` and :class:`PlaylistService` to translate
    between protobuf messages and domain logic.
    """

    def __init__(
        self,
        live_room_service: LiveRoomService,
        playlist_service: PlaylistService,
    ) -> None:
        self._room_svc = live_room_service
        self._playlist_svc = playlist_service

    # ── Live Room CRUD ──

    async def CreateLiveRoom(
        self,
        request: live_mgr_pb2.CreateLiveRoomRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            data = {
                "store_id": request.store_id,
                "title": request.title,
                "avatar_id": request.avatar_id or None,
                "voice_id": request.voice_id or None,
                "target_platforms": list(request.target_platforms),
            }
            room_dict = await self._room_svc.create_live_room(data)
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def GetLiveRoom(
        self,
        request: live_mgr_pb2.GetLiveRoomRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            room_dict = await self._room_svc.get_live_room(request.live_room_id)
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def UpdateLiveRoom(
        self,
        request: live_mgr_pb2.UpdateLiveRoomRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            updates: dict[str, Any] = {}
            if request.HasField("title"):
                updates["title"] = request.title
            if request.HasField("cover_url"):
                updates["cover_url"] = request.cover_url
            if request.HasField("avatar_id"):
                updates["avatar_id"] = request.avatar_id
            if request.HasField("voice_id"):
                updates["voice_id"] = request.voice_id

            room_dict = await self._room_svc.update_live_room(
                live_room_id=request.live_room_id,
                updates=updates,
            )
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def ListLiveRooms(
        self,
        request: live_mgr_pb2.ListLiveRoomsRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.ListLiveRoomsResponse:
        try:
            status_filter = None
            if request.HasField("status"):
                status_filter = _PROTO_TO_STATUS_STR.get(request.status)

            page = 1
            page_size = 20
            if request.HasField("pagination"):
                page = request.pagination.page or 1
                page_size = request.pagination.page_size or 20

            result = await self._room_svc.list_live_rooms(
                store_id=request.store_id or None,
                status=status_filter,
                page=page,
                page_size=page_size,
            )

            return live_mgr_pb2.ListLiveRoomsResponse(
                live_rooms=[
                    _dict_to_live_room_proto(r) for r in result["live_rooms"]
                ],
                page_info=common_pb2.PageInfo(
                    page=result["page"],
                    page_size=result["page_size"],
                    total_count=result["total_count"],
                    total_pages=result["total_pages"],
                ),
            )
        except AppError as e:
            await _abort_with_error(context, e)

    # ── State Machine ──

    async def StartLive(
        self,
        request: live_mgr_pb2.StartLiveRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            room_dict = await self._room_svc.start_live(request.live_room_id)
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def PauseLive(
        self,
        request: live_mgr_pb2.PauseLiveRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            room_dict = await self._room_svc.pause_live(request.live_room_id)
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def ResumeLive(
        self,
        request: live_mgr_pb2.ResumeLiveRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            room_dict = await self._room_svc.resume_live(request.live_room_id)
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def StopLive(
        self,
        request: live_mgr_pb2.StopLiveRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            room_dict = await self._room_svc.stop_live(request.live_room_id)
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def EmergencyStop(
        self,
        request: live_mgr_pb2.EmergencyStopRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.LiveRoom:
        try:
            room_dict = await self._room_svc.emergency_stop(
                live_room_id=request.live_room_id,
                reason=request.reason,
            )
            return _dict_to_live_room_proto(room_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    # ── Playlist ──

    async def CreatePlaylist(
        self,
        request: live_mgr_pb2.CreatePlaylistRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.Playlist:
        try:
            data: dict[str, Any] = {
                "live_room_id": request.live_room_id,
                "items": [_item_proto_to_dict(item) for item in request.items],
            }
            if request.HasField("loop_rule"):
                data["loop_rule"] = _loop_rule_proto_to_dict(request.loop_rule)

            playlist_dict = await self._playlist_svc.create_playlist(data)
            return _dict_to_playlist_proto(playlist_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def UpdatePlaylist(
        self,
        request: live_mgr_pb2.UpdatePlaylistRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.Playlist:
        try:
            data: dict[str, Any] = {}
            if request.items:
                data["items"] = [_item_proto_to_dict(item) for item in request.items]
            if request.HasField("loop_rule"):
                data["loop_rule"] = _loop_rule_proto_to_dict(request.loop_rule)

            playlist_dict = await self._playlist_svc.update_playlist(
                playlist_id=request.playlist_id,
                data=data,
            )
            return _dict_to_playlist_proto(playlist_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def GetPlaylist(
        self,
        request: live_mgr_pb2.GetPlaylistRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.Playlist:
        try:
            playlist_dict = await self._playlist_svc.get_playlist(
                playlist_id=request.playlist_id,
            )
            return _dict_to_playlist_proto(playlist_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    # ── Stream Config ──

    async def GetStreamConfig(
        self,
        request: live_mgr_pb2.GetStreamConfigRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.StreamConfig:
        try:
            config_dict = await self._room_svc.get_stream_config(
                live_room_id=request.live_room_id,
            )
            return _dict_to_stream_config_proto(config_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def UpdateStreamConfig(
        self,
        request: live_mgr_pb2.UpdateStreamConfigRequest,
        context: grpc.aio.ServicerContext,
    ) -> live_mgr_pb2.StreamConfig:
        try:
            config_dict = _stream_config_proto_to_dict(request.stream_config)
            result_dict = await self._room_svc.update_stream_config(
                live_room_id=request.live_room_id,
                config=config_dict,
            )
            return _dict_to_stream_config_proto(result_dict)
        except AppError as e:
            await _abort_with_error(context, e)


# ── Error handling ──


async def _abort_with_error(context: grpc.aio.ServicerContext, error: AppError) -> None:
    """Abort a gRPC call with the given ``AppError`` mapped to a gRPC status."""
    logger.warning(
        "grpc.abort",
        code=error.full_code,
        message=error.message,
    )
    status_code = _error_to_grpc_status(error.code)
    await context.abort(
        code=status_code,
        details=f"[{error.full_code}] {error.message}",
    )


def _error_to_grpc_status(code: ErrorCode) -> grpc.StatusCode:
    """Map an ``ErrorCode`` to a gRPC ``StatusCode``."""
    mapping: dict[ErrorCode, grpc.StatusCode] = {
        ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
        ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
        ErrorCode.TOKEN_EXPIRED: grpc.StatusCode.UNAUTHENTICATED,
        ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
        ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
        ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        ErrorCode.LIVE_ROOM_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
        ErrorCode.RESOURCE_IN_USE: grpc.StatusCode.FAILED_PRECONDITION,
        ErrorCode.LIVE_ROOM_NOT_IN_STATE: grpc.StatusCode.FAILED_PRECONDITION,
        ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
        ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
    }
    return mapping.get(code, grpc.StatusCode.UNKNOWN)


# ── Proto ↔ dict conversion helpers ──


def _dict_to_live_room_proto(room: dict[str, Any]) -> live_mgr_pb2.LiveRoom:
    """Convert a room dict from the service layer to a proto ``LiveRoom`` message."""
    status_str = room.get("status", "draft")
    status_enum = _STATUS_TO_PROTO.get(
        LiveStatus(status_str), live_mgr_pb2.LIVE_ROOM_STATUS_DRAFT
    )

    return live_mgr_pb2.LiveRoom(
        live_room_id=room.get("live_room_id", ""),
        store_id=room.get("store_id", ""),
        title=room.get("title", ""),
        cover_url=room.get("cover_url", ""),
        status=status_enum,
        avatar_id=room.get("avatar_id", ""),
        voice_id=room.get("voice_id", ""),
        script_id=room.get("script_id", ""),
        audit_info=common_pb2.AuditInfo(
            created_by=room.get("created_by", ""),
            updated_by=room.get("updated_by", ""),
            timestamps=common_pb2.Timestamps(
                created_at=room.get("created_at", 0),
                updated_at=room.get("updated_at", 0),
            ),
        ),
    )


def _dict_to_playlist_proto(playlist: dict[str, Any]) -> live_mgr_pb2.Playlist:
    """Convert a playlist dict to a proto ``Playlist`` message."""
    return live_mgr_pb2.Playlist(
        playlist_id=playlist.get("playlist_id", ""),
        live_room_id=playlist.get("live_room_id", ""),
        items=[_dict_to_item_proto(item) for item in playlist.get("items", [])],
        loop_rule=_dict_to_loop_rule_proto(playlist.get("loop_rule", {})),
        created_at=playlist.get("created_at", 0),
        updated_at=playlist.get("updated_at", 0),
    )


def _dict_to_item_proto(item: dict[str, Any]) -> live_mgr_pb2.PlaylistItem:
    """Convert an item dict to a proto ``PlaylistItem`` message."""
    return live_mgr_pb2.PlaylistItem(
        item_id=item.get("item_id", ""),
        order=item.get("order", 0),
        script_section_id=item.get("script_section_id", ""),
        product_id=item.get("product_id", ""),
        duration_ms=item.get("duration_ms", 0),
        type=_item_type_str_to_proto(item.get("type", "")),
    )


def _item_proto_to_dict(item: live_mgr_pb2.PlaylistItem) -> dict[str, Any]:
    """Convert a proto ``PlaylistItem`` to a dict."""
    return {
        "item_id": item.item_id or "",
        "order": item.order,
        "script_section_id": item.script_section_id or "",
        "product_id": item.product_id or "",
        "duration_ms": item.duration_ms,
        "type": _item_type_proto_to_str(item.type),
    }


_ITEM_TYPE_MAP = {
    live_mgr_pb2.ITEM_TYPE_SCRIPT_SEGMENT: "script_segment",
    live_mgr_pb2.ITEM_TYPE_WARMUP: "warmup",
    live_mgr_pb2.ITEM_TYPE_BREAK: "break",
    live_mgr_pb2.ITEM_TYPE_INTERACTIVE_REPLY: "interactive_reply",
}

_ITEM_TYPE_REVERSE_MAP = {v: k for k, v in _ITEM_TYPE_MAP.items()}


def _item_type_str_to_proto(type_str: str) -> int:
    return _ITEM_TYPE_REVERSE_MAP.get(type_str, live_mgr_pb2.ITEM_TYPE_UNSPECIFIED)


def _item_type_proto_to_str(type_enum: int) -> str:
    return _ITEM_TYPE_MAP.get(type_enum, "")


def _dict_to_loop_rule_proto(rule: dict[str, Any]) -> live_mgr_pb2.LoopRule:
    """Convert a loop rule dict to a proto ``LoopRule`` message."""
    if not rule:
        return live_mgr_pb2.LoopRule()
    return live_mgr_pb2.LoopRule(
        mode=_loop_mode_str_to_proto(rule.get("mode", "")),
        weights=rule.get("weights", {}),
        schedule_json=rule.get("schedule_json", ""),
    )


def _loop_rule_proto_to_dict(rule: live_mgr_pb2.LoopRule) -> dict[str, Any]:
    """Convert a proto ``LoopRule`` to a dict."""
    return {
        "mode": _loop_mode_proto_to_str(rule.mode),
        "weights": dict(rule.weights),
        "schedule_json": rule.schedule_json or "",
    }


_LOOP_MODE_MAP = {
    live_mgr_pb2.LOOP_MODE_ROUND_ROBIN: "round_robin",
    live_mgr_pb2.LOOP_MODE_WEIGHTED: "weighted",
    live_mgr_pb2.LOOP_MODE_SCHEDULED: "scheduled",
    live_mgr_pb2.LOOP_MODE_SMART: "smart",
}

_LOOP_MODE_REVERSE_MAP = {v: k for k, v in _LOOP_MODE_MAP.items()}


def _loop_mode_str_to_proto(mode_str: str) -> int:
    return _LOOP_MODE_REVERSE_MAP.get(mode_str, live_mgr_pb2.LOOP_MODE_UNSPECIFIED)


def _loop_mode_proto_to_str(mode_enum: int) -> str:
    return _LOOP_MODE_MAP.get(mode_enum, "")


def _dict_to_stream_config_proto(config: dict[str, Any]) -> live_mgr_pb2.StreamConfig:
    """Convert a stream config dict to a proto ``StreamConfig`` message."""
    return live_mgr_pb2.StreamConfig(
        rtmp_url=config.get("rtmp_url", ""),
        stream_key=config.get("stream_key", ""),
        video_profile=_video_profile_str_to_proto(config.get("video_profile", "")),
        width=config.get("width", 1920),
        height=config.get("height", 1080),
        fps=config.get("fps", 30),
        video_bitrate_kbps=config.get("video_bitrate_kbps", 4000),
        audio_bitrate_kbps=config.get("audio_bitrate_kbps", 128),
    )


def _stream_config_proto_to_dict(config: live_mgr_pb2.StreamConfig) -> dict[str, Any]:
    """Convert a proto ``StreamConfig`` to a dict."""
    return {
        "rtmp_url": config.rtmp_url or "",
        "stream_key": config.stream_key or "",
        "video_profile": _video_profile_proto_to_str(config.video_profile),
        "width": config.width or 1920,
        "height": config.height or 1080,
        "fps": config.fps or 30,
        "video_bitrate_kbps": config.video_bitrate_kbps or 4000,
        "audio_bitrate_kbps": config.audio_bitrate_kbps or 128,
    }


_VIDEO_PROFILE_MAP = {
    live_mgr_pb2.VIDEO_PROFILE_BASELINE: "baseline",
    live_mgr_pb2.VIDEO_PROFILE_MAIN: "main",
    live_mgr_pb2.VIDEO_PROFILE_HIGH: "high",
}

_VIDEO_PROFILE_REVERSE_MAP = {v: k for k, v in _VIDEO_PROFILE_MAP.items()}


def _video_profile_str_to_proto(profile_str: str) -> int:
    return _VIDEO_PROFILE_REVERSE_MAP.get(profile_str, live_mgr_pb2.VIDEO_PROFILE_UNSPECIFIED)


def _video_profile_proto_to_str(profile_enum: int) -> str:
    return _VIDEO_PROFILE_MAP.get(profile_enum, "")
