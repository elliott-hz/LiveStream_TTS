"""
HTTP routes for the interaction service.

Endpoints:
  GET  /api/v1/health                   — Health check
  POST /api/v1/interact/sessions        — Start a session
  POST /api/v1/interact/danmaku         — Process a danmaku
  GET  /api/v1/interact/sessions/{id}   — Get session by ID
  POST /api/v1/interact/sessions/{id}/stop — Stop a session
  POST /api/v1/interact/route           — Route a message
  POST /api/v1/interact/moderator       — Get moderator action
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger
from libs.proto.nlp.v1 import nlp_pb2
from libs.proto.interact.v1 import interact_pb2

from ..models import SessionConfig
from ..services import InteractionService

logger = get_logger(__name__)

router = APIRouter(tags=["interact"])

# Injected by the application factory
_service: InteractionService | None = None


def init_routes(service: InteractionService) -> None:
    """Inject the service instance into the routes module."""
    global _service
    _service = service


def _get_service() -> InteractionService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _service


# ── Health ──


@router.get("/api/v1/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    service = _get_service()
    return {
        "status": "ok",
        "service": "interact-svc",
        "active_sessions": len(service.list_active_sessions()),
    }


# ── Sessions ──


@router.post("/api/v1/interact/sessions")
async def start_session(
    live_room_id: str,
    voice_id: str = "default",
    system_prompt: str = "",
    reply_threshold: float = 0.3,
    enable_moderator: bool = True,
) -> dict[str, Any]:
    """Start a new interaction session."""
    try:
        config = SessionConfig(
            voice_id=voice_id,
            system_prompt=system_prompt,
            reply_threshold=reply_threshold,
            enable_moderator=enable_moderator,
        )
        session = _get_service().start_session(live_room_id=live_room_id, config=config)
        return {
            "session_id": session.session_id,
            "live_room_id": session.live_room_id,
            "status": session.status.name,
            "started_at": session.started_at,
        }
    except AppError as e:
        raise HTTPException(status_code=_http_status(e.code), detail=e.message)


@router.get("/api/v1/interact/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get session details by ID."""
    try:
        session = _get_service().get_session(session_id)
        return {
            "session_id": session.session_id,
            "live_room_id": session.live_room_id,
            "store_id": session.store_id,
            "status": session.status.name,
            "stats": {
                "total_danmaku": session.stats.total_danmaku,
                "voice_replies": session.stats.voice_replies,
                "text_replies": session.stats.text_replies,
                "moderator_actions": session.stats.moderator_actions,
                "ignored_messages": session.stats.ignored_messages,
                "avg_latency_ms": round(session.stats.avg_latency_ms, 2),
            },
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        }
    except AppError as e:
        raise HTTPException(status_code=_http_status(e.code), detail=e.message)


@router.post("/api/v1/interact/sessions/{session_id}/stop")
async def stop_session(session_id: str) -> dict[str, str]:
    """Stop an active session."""
    try:
        _get_service().stop_session(session_id)
        return {"status": "stopped", "session_id": session_id}
    except AppError as e:
        raise HTTPException(status_code=_http_status(e.code), detail=e.message)


# ── Danmaku ──


@router.post("/api/v1/interact/danmaku")
async def process_danmaku(
    session_id: str,
    danmaku_id: str = "",
    text: str = "",
    platform_user_id: str = "",
    platform: str = "",
) -> dict[str, Any]:
    """Process a danmaku through the full interaction pipeline."""
    try:
        reply = await _get_service().process_danmaku(
            session_id=session_id,
            danmaku_id=danmaku_id,
            text=text,
            platform_user_id=platform_user_id,
            platform=platform,
        )
        return {
            "reply_id": reply.reply_id,
            "channel": interact_pb2.Channel.Name(reply.channel) if reply.channel else "IGNORE",
            "reply_text": reply.reply_text,
            "emotion": reply.emotion,
            "action": reply.action,
            "latency_ms": round(reply.pipeline_latency_ms, 2),
        }
    except AppError as e:
        raise HTTPException(status_code=_http_status(e.code), detail=e.message)


# ── Route ──


@router.post("/api/v1/interact/route")
async def route_channel(
    text: str = "",
    intent: str = "OTHER",
    confidence: float = 0.0,
    sentiment: str = "NEUTRAL",
    is_vip: bool = False,
    is_new: bool = False,
) -> dict[str, Any]:
    """Route a message to the appropriate output channel."""
    try:
        intent_val = getattr(nlp_pb2, f"INTENT_CATEGORY_{intent.upper()}", nlp_pb2.INTENT_CATEGORY_OTHER)
        sentiment_val = getattr(nlp_pb2, f"SENTIMENT_{sentiment.upper()}", nlp_pb2.SENTIMENT_NEUTRAL)

        user_tags = {"is_vip": is_vip, "is_new": is_new}
        result = _get_service().route_channel(
            text=text,
            intent=intent_val,
            confidence=confidence,
            sentiment=sentiment_val,
            user_tags=user_tags,
        )
        return {
            "channel": interact_pb2.Channel.Name(result.channel) if result.channel else "IGNORE",
            "channel_value": result.channel,
            "reason": result.reason,
        }
    except AppError as e:
        raise HTTPException(status_code=_http_status(e.code), detail=e.message)


# ── Moderator ──


@router.post("/api/v1/interact/moderator")
async def get_moderator_action(
    session_id: str,
    trigger_event: str = "interval",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get an AI moderator action for a trigger event."""
    try:
        action = await _get_service().get_moderator_action(
            session_id=session_id,
            trigger_event=trigger_event,
            context=context or {},
        )
        return {
            "action_type": interact_pb2.ModeratorActionType.Name(action.action_type) if action.action_type else "NO_ACTION",
            "comment_text": action.comment_text,
            "coupon_id": action.coupon_id,
            "product_id": action.product_id,
            "hide_comment_id": action.hide_comment_id,
        }
    except AppError as e:
        raise HTTPException(status_code=_http_status(e.code), detail=e.message)


# ── Helpers ──


def _http_status(code: ErrorCode) -> int:
    """Map AppError ErrorCode to HTTP status codes."""
    mapping = {
        ErrorCode.INVALID_ARGUMENT: 400,
        ErrorCode.MISSING_REQUIRED_FIELD: 400,
        ErrorCode.VALUE_OUT_OF_RANGE: 400,
        ErrorCode.INVALID_FORMAT: 400,
        ErrorCode.UNAUTHENTICATED: 401,
        ErrorCode.PERMISSION_DENIED: 403,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.DUPLICATE_RESOURCE: 409,
        ErrorCode.QUOTA_EXCEEDED: 429,
        ErrorCode.LIVE_ROOM_NOT_IN_STATE: 409,
        ErrorCode.RESOURCE_IN_USE: 409,
    }
    return mapping.get(code, 500)
