"""
gRPC service implementation for VoiceService.

Maps each RPC to the corresponding VoiceService method.
Converts DB ORM models <-> proto messages.
Translates AppError exceptions to gRPC status codes.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.voice import Voice, VoiceCloneTask
from services.voice_service import VoiceService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, VoiceService]]


# ── Exception → gRPC error mapping ──

_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.VOICE_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
    ErrorCode.RESOURCE_IN_USE: grpc.StatusCode.FAILED_PRECONDITION,
    ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
    ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
}


def _app_error_to_grpc_context(exc: AppError, context: aio.ServicerContext) -> None:
    grpc_code = _ERROR_CODE_TO_GRPC.get(exc.code, grpc.StatusCode.UNKNOWN)
    context.set_code(grpc_code)
    context.set_details(exc.message)
    error_proto = common_pb.Error(
        code=exc.full_code,
        message=exc.message,
        details=exc.details,
    )
    context.set_trailing_metadata(
        ("x-error-code", str(exc.full_code)),
        ("x-error-bin", error_proto.SerializeToString()),
    )


# ── Proto ↔ ORM converters ──


def _voice_to_proto(voice: Voice) -> pb.Voice:
    """Convert an ORM Voice to a proto Voice message."""
    audit = common_pb.AuditInfo(
        created_by=voice.created_by or "",
        updated_by=voice.updated_by or "",
        timestamps=common_pb.Timestamps(
            created_at=int(voice.created_at.timestamp() * 1000),
            updated_at=int(voice.updated_at.timestamp() * 1000),
        ),
    )

    quality = pb.PaintingQualityMetrics()
    if voice.quality_metrics:
        quality.mos_score = voice.quality_metrics.get("mos_score", 0.0)
        quality.similarity_score = voice.quality_metrics.get("similarity_score", 0.0)
        quality.evaluated_at = voice.quality_metrics.get("evaluated_at", 0)

    return pb.Voice(
        voice_id=voice.voice_id,
        store_id=voice.store_id,
        name=voice.name,
        gender=_gender_to_proto(voice.gender),
        age_range=voice.age_range,
        language=voice.language,
        style=_style_to_proto(voice.style),
        status=_voice_status_to_proto(voice.status),
        is_public=voice.is_public,
        quality=quality,
        audit_info=audit,
    )


def _clone_task_to_proto(task: VoiceCloneTask) -> pb.VoiceCloneTask:
    return pb.VoiceCloneTask(
        task_id=task.task_id,
        voice_id=task.voice_id,
        status=_clone_status_to_proto(task.status),
        progress_percent=task.progress_percent,
        error_message=task.error_message or "",
        created_at=int(task.created_at.timestamp() * 1000),
        completed_at=int(task.completed_at.timestamp() * 1000) if task.completed_at else 0,
    )


# ── Enum converters ──

_MAP_GENDER = {
    "male": pb.Gender.GENDER_MALE,
    "female": pb.Gender.GENDER_FEMALE,
}
_REV_GENDER = {v: k for k, v in _MAP_GENDER.items()}


def _gender_to_proto(g: str) -> pb.Gender:
    return _MAP_GENDER.get(g, pb.Gender.GENDER_UNSPECIFIED)


def _gender_from_proto(g: pb.Gender) -> str:
    return _REV_GENDER.get(g, "male")


_MAP_STYLE = {
    "passionate": pb.VoiceStyle.VOICE_STYLE_PASSIONATE,
    "professional": pb.VoiceStyle.VOICE_STYLE_PROFESSIONAL,
    "gentle": pb.VoiceStyle.VOICE_STYLE_GENTLE,
    "lively": pb.VoiceStyle.VOICE_STYLE_LIVELY,
}
_REV_STYLE = {v: k for k, v in _MAP_STYLE.items()}


def _style_to_proto(s: str) -> pb.VoiceStyle:
    return _MAP_STYLE.get(s, pb.VoiceStyle.VOICE_STYLE_UNSPECIFIED)


def _style_from_proto(s: pb.VoiceStyle) -> str:
    return _REV_STYLE.get(s, "professional")


_MAP_VOICE_STATUS = {
    "active": pb.VoiceStatus.VOICE_STATUS_ACTIVE,
    "cloning": pb.VoiceStatus.VOICE_STATUS_CLONING,
    "failed": pb.VoiceStatus.VOICE_STATUS_FAILED,
}
_REV_VOICE_STATUS = {v: k for k, v in _MAP_VOICE_STATUS.items()}


def _voice_status_to_proto(s: str) -> pb.VoiceStatus:
    return _MAP_VOICE_STATUS.get(s, pb.VoiceStatus.VOICE_STATUS_UNSPECIFIED)


def _voice_status_from_proto(s: pb.VoiceStatus) -> str:
    return _REV_VOICE_STATUS.get(s, "active")


_MAP_CLONE_STATUS = {
    "uploading": pb.CloneStatus.CLONE_STATUS_UPLOADING,
    "processing": pb.CloneStatus.CLONE_STATUS_PROCESSING,
    "success": pb.CloneStatus.CLONE_STATUS_SUCCESS,
    "failed": pb.CloneStatus.CLONE_STATUS_FAILED,
}
_REV_CLONE_STATUS = {v: k for k, v in _MAP_CLONE_STATUS.items()}


def _clone_status_to_proto(s: str) -> pb.CloneStatus:
    return _MAP_CLONE_STATUS.get(s, pb.CloneStatus.CLONE_STATUS_UNSPECIFIED)


def _clone_status_from_proto(s: pb.CloneStatus) -> str:
    return _REV_CLONE_STATUS.get(s, "uploading")


# ── Servicer ──


class VoiceServiceServicer(pb_grpc.VoiceServiceServicer):
    """gRPC servicer that delegates to VoiceService for business logic."""

    def __init__(self, voice_service_factory: ServiceFactory) -> None:
        self._svc_factory = voice_service_factory

    async def _svc(self) -> VoiceService:
        return await self._svc_factory()

    async def _run(
        self,
        handler,
        request,
        context: aio.ServicerContext,
    ) -> Any:
        try:
            svc = await self._svc()
            return await handler(svc, request)
        except AppError as exc:
            _app_error_to_grpc_context(exc, context)
            return None
        except Exception as exc:
            logger.exception("grpc.handler_error", method=context.method)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return None

    # ── Voice CRUD ──

    async def CreateVoice(
        self,
        request: pb.CreateVoiceRequest,
        context: aio.ServicerContext,
    ) -> pb.Voice:
        async def handler(svc: VoiceService, req: pb.CreateVoiceRequest) -> pb.Voice:
            voice = await svc.create_voice(
                store_id=req.store_id,
                name=req.name,
                gender=_gender_from_proto(req.gender),
                age_range=req.age_range,
                language=req.language,
                style=_style_from_proto(req.style),
                prompt_audio=req.prompt_audio or None,
                prompt_transcript=req.prompt_transcript or None,
            )
            return _voice_to_proto(voice)

        return await self._run(handler, request, context)

    async def GetVoice(
        self,
        request: pb.GetVoiceRequest,
        context: aio.ServicerContext,
    ) -> pb.Voice:
        async def handler(svc: VoiceService, req: pb.GetVoiceRequest) -> pb.Voice:
            voice = await svc.get_voice(voice_id=req.voice_id)
            return _voice_to_proto(voice)

        return await self._run(handler, request, context)

    async def UpdateVoice(
        self,
        request: pb.UpdateVoiceRequest,
        context: aio.ServicerContext,
    ) -> pb.Voice:
        async def handler(svc: VoiceService, req: pb.UpdateVoiceRequest) -> pb.Voice:
            kwargs: dict[str, Any] = {}
            if req.HasField("name"):
                kwargs["name"] = req.name
            voice = await svc.update_voice(voice_id=req.voice_id, **kwargs)
            return _voice_to_proto(voice)

        return await self._run(handler, request, context)

    async def DeleteVoice(
        self,
        request: pb.DeleteVoiceRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(svc: VoiceService, req: pb.DeleteVoiceRequest) -> common_pb.Error:
            await svc.delete_voice(voice_id=req.voice_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    async def ListVoices(
        self,
        request: pb.ListVoicesRequest,
        context: aio.ServicerContext,
    ) -> pb.ListVoicesResponse:
        async def handler(
            svc: VoiceService,
            req: pb.ListVoicesRequest,
        ) -> pb.ListVoicesResponse:
            pagination = req.pagination
            page = pagination.page if pagination and pagination.page else 1
            page_size = pagination.page_size if pagination and pagination.page_size else 20

            gender_str = _gender_from_proto(req.gender) if req.HasField("gender") else None
            style_str = _style_from_proto(req.style) if req.HasField("style") else None

            voices, total_count = await svc.list_voices(
                store_id=req.store_id,
                gender=gender_str,
                style=style_str,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            return pb.ListVoicesResponse(
                voices=[_voice_to_proto(v) for v in voices],
                page_info=common_pb.PageInfo(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    total_pages=total_pages,
                ),
            )

        return await self._run(handler, request, context)

    # ── Clone ──

    async def StartClone(
        self,
        request: pb.StartVoiceCloneRequest,
        context: aio.ServicerContext,
    ) -> pb.VoiceCloneTask:
        async def handler(
            svc: VoiceService,
            req: pb.StartVoiceCloneRequest,
        ) -> pb.VoiceCloneTask:
            task = await svc.start_clone(
                voice_id=req.voice_id,
                prompt_audio=req.prompt_audio or None,
                prompt_transcript=req.prompt_transcript or None,
            )
            return _clone_task_to_proto(task)

        return await self._run(handler, request, context)

    async def GetCloneTask(
        self,
        request: pb.GetVoiceCloneTaskRequest,
        context: aio.ServicerContext,
    ) -> pb.VoiceCloneTask:
        async def handler(
            svc: VoiceService,
            req: pb.GetVoiceCloneTaskRequest,
        ) -> pb.VoiceCloneTask:
            task = await svc.get_clone_task(task_id=req.task_id)
            return _clone_task_to_proto(task)

        return await self._run(handler, request, context)

    # ── Preview ──

    async def PreviewVoice(
        self,
        request: pb.PreviewVoiceRequest,
        context: aio.ServicerContext,
    ) -> pb.PreviewVoiceResponse:
        async def handler(
            svc: VoiceService,
            req: pb.PreviewVoiceRequest,
        ) -> pb.PreviewVoiceResponse:
            result = await svc.preview_voice(
                voice_id=req.voice_id,
                text=req.text,
            )
            return pb.PreviewVoiceResponse(
                preview_url=result["preview_url"],
                duration_ms=result["duration_ms"],
            )

        return await self._run(handler, request, context)
