"""
gRPC service implementation for ProfileService.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from profile.v1 import profile_pb2 as pb
from profile.v1 import profile_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.profile import Segment
from services.profile_service import ProfileService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, ProfileService]]


_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
}


def _app_error_to_grpc_context(exc: AppError, context: aio.ServicerContext) -> None:
    grpc_code = _ERROR_CODE_TO_GRPC.get(exc.code, grpc.StatusCode.UNKNOWN)
    context.set_code(grpc_code)
    context.set_details(exc.message)
    error_proto = common_pb.Error(code=exc.full_code, message=exc.message, details=exc.details)
    context.set_trailing_metadata(
        ("x-error-code", str(exc.full_code)),
        ("x-error-bin", error_proto.SerializeToString()),
    )


def _profile_to_proto(data: dict) -> pb.AudienceProfile:
    return pb.AudienceProfile(
        profile_id=data.get("profile_id", ""),
        platform_user_id=data.get("platform_user_id", ""),
        platform=data.get("platform", ""),
        nickname=data.get("nickname", ""),
        tags=data.get("tags", []),
        visit_count=data.get("visit_count", 0),
        purchase_count=data.get("purchase_count", 0),
        total_spent_fen=data.get("total_spent_fen", 0),
        interest_categories=data.get("interest_categories", []),
        last_interaction_text=data.get("last_interaction_text", ""),
        last_seen_at=data.get("last_seen_at", 0),
        created_at=data.get("created_at", 0),
    )


def _segment_to_proto(s: Segment) -> pb.Segment:
    return pb.Segment(
        segment_id=s.segment_id,
        store_id=s.store_id,
        name=s.name,
        rule_json=s.rule_json,
        audience_size=s.audience_size,
    )


class ProfileServiceServicer(pb_grpc.ProfileServiceServicer):
    """gRPC servicer for ProfileService."""

    def __init__(self, service_factory: ServiceFactory) -> None:
        self._factory = service_factory

    async def _run(self, handler, request, context: aio.ServicerContext) -> Any:
        try:
            svc = await self._factory()
            return await handler(svc, request)
        except AppError as exc:
            _app_error_to_grpc_context(exc, context)
            return None
        except Exception as exc:
            logger.exception("grpc.handler_error", method=context.method)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return None

    async def GetProfile(
        self, request: pb.GetProfileRequest, context: aio.ServicerContext
    ) -> pb.AudienceProfile:
        async def handler(svc, req):
            data = await svc.get_profile(
                platform_user_id=req.platform_user_id,
                platform=req.platform,
            )
            return _profile_to_proto(data)
        return await self._run(handler, request, context)

    async def UpdateProfile(
        self, request: pb.UpdateProfileRequest, context: aio.ServicerContext
    ) -> pb.AudienceProfile:
        async def handler(svc, req):
            data = await svc.update_profile(
                platform_user_id=req.platform_user_id,
                platform=req.platform,
                nickname=req.nickname if req.HasField("nickname") else None,
                tags=list(req.tags) if req.tags else None,
            )
            return _profile_to_proto(data)
        return await self._run(handler, request, context)

    async def TrackEvent(
        self, request: pb.TrackEventRequest, context: aio.ServicerContext
    ) -> common_pb.Error:
        async def handler(svc, req):
            await svc.track_event(
                platform_user_id=req.platform_user_id,
                platform=req.platform,
                event_type=req.event_type,
                live_room_id=req.live_room_id or "",
                properties=dict(req.properties) if req.properties else None,
            )
            return common_pb.Error(code=0, message="ok")
        return await self._run(handler, request, context)

    async def GetSegment(
        self, request: pb.GetSegmentRequest, context: aio.ServicerContext
    ) -> pb.Segment:
        async def handler(svc, req):
            segment = await svc.get_segment(segment_id=req.segment_id)
            return _segment_to_proto(segment)
        return await self._run(handler, request, context)
