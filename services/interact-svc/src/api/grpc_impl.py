"""
gRPC service implementation for InteractionService (interact.v1).

Implements all 7 RPCs:
  StartSession, StopSession, GetSession, ProcessDanmaku,
  RouteChannel, GetModeratorAction

Each method receives a protobuf request and returns the appropriate response,
wrapping business logic errors as gRPC status codes.
"""

from __future__ import annotations

import json
import time
from typing import Any

import grpc

from libs.common.errors import AppError, ErrorCode, Domain
from libs.common.logging import get_logger
from libs.proto.interact.v1 import interact_pb2
from libs.proto.interact.v1 import interact_pb2_grpc

from ..models import (
    Channel,
    ModeratorAction,
    ModeratorActionType,
    Session,
    SessionConfig,
    SessionStats,
    SessionStatus,
    ModeratorConfig as ModeratorConfigModel,
)
from ..services import InteractionService

logger = get_logger(__name__)


class InteractionServiceServicer(interact_pb2_grpc.InteractionServiceServicer):
    """gRPC servicer for InteractionService.

    Wraps the core InteractionService and translates protobuf messages
    to/from domain models.
    """

    def __init__(self, service: InteractionService) -> None:
        self._service = service

    # ── Session RPCs ──

    async def StartSession(
        self,
        request: interact_pb2.StartSessionRequest,
        context: grpc.aio.ServicerContext,
    ) -> interact_pb2.Session:
        """Start a new interaction session."""
        try:
            config = self._to_session_config(request.config)
            session = self._service.start_session(
                live_room_id=request.live_room_id,
                config=config,
            )
            logger.info("grpc.start_session", session_id=session.session_id)
            return self._session_to_proto(session)
        except AppError as e:
            await self._abort(context, e)

    async def StopSession(
        self,
        request: interact_pb2.StopSessionRequest,
        context: grpc.aio.ServicerContext,
    ) -> interact_pb2.common.v1.Error:
        """Stop a running session."""
        try:
            self._service.stop_session(request.session_id)
            return self._ok_response(f"Session {request.session_id} stopped")
        except AppError as e:
            return self._error_response(e)

    async def GetSession(
        self,
        request: interact_pb2.GetSessionRequest,
        context: grpc.aio.ServicerContext,
    ) -> interact_pb2.Session:
        """Get session details."""
        try:
            session = self._service.get_session(request.session_id)
            return self._session_to_proto(session)
        except AppError as e:
            await self._abort(context, e)

    # ── Pipeline RPCs ──

    async def ProcessDanmaku(
        self,
        request: interact_pb2.ProcessDanmakuRequest,
        context: grpc.aio.ServicerContext,
    ) -> interact_pb2.ProcessDanmakuResponse:
        """Process a single danmaku through the full pipeline."""
        try:
            reply = await self._service.process_danmaku(
                session_id=request.session_id,
                danmaku_id=request.danmaku_id,
                text=request.text,
                platform_user_id=request.platform_user_id,
                platform=request.platform,
                timestamp=request.timestamp,
            )
            return interact_pb2.ProcessDanmakuResponse(
                reply_id=reply.reply_id,
                channel=reply.channel,
                reply_text=reply.reply_text,
                emotion=reply.emotion,
                action=reply.action,
                trigger_coupon_ids=reply.coupon_ids,
                pipeline_latency_ms=int(reply.pipeline_latency_ms),
            )
        except AppError as e:
            await self._abort(context, e)

    # ── Channel Router RPCs ──

    async def RouteChannel(
        self,
        request: interact_pb2.RouteChannelRequest,
        context: grpc.aio.ServicerContext,
    ) -> interact_pb2.RouteChannelResponse:
        """Route a message to the appropriate output channel."""
        try:
            tags = json.loads(request.user_profile_tags) if request.user_profile_tags else {}
            result = self._service.route_channel(
                text=request.text,
                intent=request.intent,
                confidence=request.intent_confidence,
                sentiment=request.sentiment,
                user_tags=tags,
            )
            return interact_pb2.RouteChannelResponse(
                channel=result.channel,
                reason=result.reason,
            )
        except AppError as e:
            await self._abort(context, e)

    # ── Moderator RPCs ──

    async def GetModeratorAction(
        self,
        request: interact_pb2.GetModeratorActionRequest,
        context: grpc.aio.ServicerContext,
    ) -> interact_pb2.ModeratorAction:
        """Get an AI moderator action for a trigger event."""
        try:
            context_dict = dict(request.context)
            action = await self._service.get_moderator_action(
                session_id=request.session_id,
                trigger_event=request.trigger_event,
                context=context_dict,
            )
            return self._moderator_action_to_proto(action)
        except AppError as e:
            await self._abort(context, e)

    # ── Proto <-> Model Conversion ──

    def _to_session_config(self, proto_config: interact_pb2.SessionConfig | None) -> SessionConfig:
        """Convert protobuf SessionConfig to domain model."""
        if proto_config is None:
            return SessionConfig()

        mod_cfg = ModeratorConfigModel(
            moderator_account_id=proto_config.moderator_config.moderator_account_id
            if proto_config.HasField("moderator_config") else "mod_official",
            auto_send_comments=proto_config.moderator_config.auto_send_comments
            if proto_config.HasField("moderator_config") else True,
            auto_send_coupons=proto_config.moderator_config.auto_send_coupons
            if proto_config.HasField("moderator_config") else True,
            auto_send_product_card=proto_config.moderator_config.auto_send_product_card
            if proto_config.HasField("moderator_config") else True,
            auto_hide_negative=proto_config.moderator_config.auto_hide_negative
            if proto_config.HasField("moderator_config") else True,
            comment_interval_seconds=proto_config.moderator_config.comment_interval_seconds
            if proto_config.HasField("moderator_config") else 30.0,
        )

        return SessionConfig(
            voice_id=proto_config.voice_id or "default",
            avatar_id=proto_config.avatar_id or "default",
            system_prompt=proto_config.system_prompt,
            banned_words=list(proto_config.banned_words),
            enable_moderator=proto_config.enable_moderator,
            enable_product_card=proto_config.enable_product_card,
            reply_threshold=proto_config.reply_threshold or 0.3,
            moderator_config=mod_cfg,
        )

    def _session_to_proto(self, session: Session) -> interact_pb2.Session:
        """Convert domain Session to protobuf Session."""
        return interact_pb2.Session(
            session_id=session.session_id,
            live_room_id=session.live_room_id,
            store_id=session.store_id,
            config=self._config_to_proto(session.config),
            status=session.status.value,
            stats=self._stats_to_proto(session.stats),
            started_at=session.started_at,
            ended_at=session.ended_at,
        )

    def _config_to_proto(self, config: SessionConfig) -> interact_pb2.SessionConfig:
        return interact_pb2.SessionConfig(
            voice_id=config.voice_id,
            avatar_id=config.avatar_id,
            system_prompt=config.system_prompt,
            banned_words=list(config.banned_words),
            enable_moderator=config.enable_moderator,
            enable_product_card=config.enable_product_card,
            reply_threshold=config.reply_threshold,
            moderator_config=interact_pb2.ModeratorConfig(
                moderator_account_id=config.moderator_config.moderator_account_id,
                auto_send_comments=config.moderator_config.auto_send_comments,
                auto_send_coupons=config.moderator_config.auto_send_coupons,
                auto_send_product_card=config.moderator_config.auto_send_product_card,
                auto_hide_negative=config.moderator_config.auto_hide_negative,
                comment_interval_seconds=config.moderator_config.comment_interval_seconds,
            ),
        )

    def _stats_to_proto(self, stats: SessionStats) -> interact_pb2.SessionStats:
        return interact_pb2.SessionStats(
            total_danmaku=stats.total_danmaku,
            voice_replies=stats.voice_replies,
            text_replies=stats.text_replies,
            moderator_actions=stats.moderator_actions,
            ignored_messages=stats.ignored_messages,
            avg_latency_ms=stats.avg_latency_ms,
        )

    def _moderator_action_to_proto(
        self, action: ModeratorAction
    ) -> interact_pb2.ModeratorAction:
        return interact_pb2.ModeratorAction(
            action_type=action.action_type.value,
            comment_text=action.comment_text,
            coupon_id=action.coupon_id,
            product_id=action.product_id,
            hide_comment_id=action.hide_comment_id,
        )

    def _ok_response(self, message: str) -> interact_pb2.common.v1.Error:
        """Create an empty (success) error response."""
        return interact_pb2.common.v1.Error(code=0, message=message)

    def _error_response(self, error: AppError) -> interact_pb2.common.v1.Error:
        """Convert AppError to protobuf Error."""
        return interact_pb2.common.v1.Error(
            code=error.full_code,
            message=error.message,
            details=error.details,
        )

    async def _abort(self, context: grpc.aio.ServicerContext, error: AppError) -> None:
        """Set gRPC error status and abort."""
        await context.abort(
            code=self._to_grpc_code(error.code),
            details=error.message,
        )

    @staticmethod
    def _to_grpc_code(code: ErrorCode) -> grpc.StatusCode:
        """Map AppError ErrorCode to gRPC status codes."""
        mapping = {
            ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
            ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
            ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
            ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
            ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
            ErrorCode.QUOTA_EXCEEDED: grpc.StatusCode.RESOURCE_EXHAUSTED,
            ErrorCode.LIVE_ROOM_NOT_IN_STATE: grpc.StatusCode.FAILED_PRECONDITION,
            ErrorCode.RESOURCE_IN_USE: grpc.StatusCode.FAILED_PRECONDITION,
        }
        return mapping.get(code, grpc.StatusCode.UNKNOWN)
