"""
gRPC service implementation for AvatarService.

Maps each RPC to the corresponding AvatarService method.
Converts DB ORM models <-> proto messages.
Translates AppError exceptions to gRPC status codes.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from avatar.v1 import avatar_pb2 as pb
from avatar.v1 import avatar_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.avatar import Avatar, CloneTask
from services.avatar_service import AvatarService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, AvatarService]]


# ── Exception → gRPC error mapping ──

_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.AVATAR_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
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


def _avatar_to_proto(avatar: Avatar) -> pb.Avatar:
    """Convert an ORM Avatar to a proto Avatar message."""
    audit = common_pb.AuditInfo(
        created_by=avatar.created_by or "",
        updated_by=avatar.updated_by or "",
        timestamps=common_pb.Timestamps(
            created_at=int(avatar.created_at.timestamp() * 1000),
            updated_at=int(avatar.updated_at.timestamp() * 1000),
        ),
    )

    custom_params = pb.AvatarCustomParam()
    if avatar.custom_params:
        custom_params.skin_smooth = avatar.custom_params.get("skin_smooth", 0.0)
        custom_params.face_thin = avatar.custom_params.get("face_thin", 0.0)
        custom_params.eye_size = avatar.custom_params.get("eye_size", 0.0)
        custom_params.lip_thickness = avatar.custom_params.get("lip_thickness", 0.0)

    return pb.Avatar(
        avatar_id=avatar.avatar_id,
        store_id=avatar.store_id,
        name=avatar.name,
        type=_avatar_type_to_proto(avatar.avatar_type),
        status=_avatar_status_to_proto(avatar.status),
        thumbnail_url=avatar.thumbnail_url or "",
        model_path=avatar.model_path or "",
        custom_params=custom_params,
        audit_info=audit,
    )


def _clone_task_to_proto(task: CloneTask) -> pb.CloneTask:
    return pb.CloneTask(
        task_id=task.task_id,
        avatar_id=task.avatar_id,
        status=_clone_status_to_proto(task.status),
        progress_percent=task.progress_percent,
        error_message=task.error_message or "",
        created_at=int(task.created_at.timestamp() * 1000),
        completed_at=int(task.completed_at.timestamp() * 1000) if task.completed_at else 0,
    )


# ── Enum converters ──

_MAP_AVATAR_TYPE = {
    "2d_real": pb.AvatarType.AVATAR_TYPE_2D_REAL,
    "3d_cartoon": pb.AvatarType.AVATAR_TYPE_3D_CARTOON,
    "2d_cartoon": pb.AvatarType.AVATAR_TYPE_2D_CARTOON,
}
_REV_AVATAR_TYPE = {v: k for k, v in _MAP_AVATAR_TYPE.items()}


def _avatar_type_to_proto(t: str) -> pb.AvatarType:
    return _MAP_AVATAR_TYPE.get(t, pb.AvatarType.AVATAR_TYPE_UNSPECIFIED)


def _avatar_type_from_proto(t: pb.AvatarType) -> str:
    return _REV_AVATAR_TYPE.get(t, "2d_real")


_MAP_AVATAR_STATUS = {
    "active": pb.AvatarStatus.AVATAR_STATUS_ACTIVE,
    "cloning": pb.AvatarStatus.AVATAR_STATUS_CLONING,
    "pending_audit": pb.AvatarStatus.AVATAR_STATUS_PENDING_AUDIT,
    "rejected": pb.AvatarStatus.AVATAR_STATUS_REJECTED,
}
_REV_AVATAR_STATUS = {v: k for k, v in _MAP_AVATAR_STATUS.items()}


def _avatar_status_to_proto(s: str) -> pb.AvatarStatus:
    return _MAP_AVATAR_STATUS.get(s, pb.AvatarStatus.AVATAR_STATUS_UNSPECIFIED)


def _avatar_status_from_proto(s: pb.AvatarStatus) -> str:
    return _REV_AVATAR_STATUS.get(s, "active")


_MAP_CLONE_STATUS = {
    "uploading": pb.CloneStatus.CLONE_STATUS_UPLOADING,
    "processing": pb.CloneStatus.CLONE_STATUS_PROCESSING,
    "training": pb.CloneStatus.CLONE_STATUS_TRAINING,
    "success": pb.CloneStatus.CLONE_STATUS_SUCCESS,
    "failed": pb.CloneStatus.CLONE_STATUS_FAILED,
}
_REV_CLONE_STATUS = {v: k for k, v in _MAP_CLONE_STATUS.items()}


def _clone_status_to_proto(s: str) -> pb.CloneStatus:
    return _MAP_CLONE_STATUS.get(s, pb.CloneStatus.CLONE_STATUS_UNSPECIFIED)


def _clone_status_from_proto(s: pb.CloneStatus) -> str:
    return _REV_CLONE_STATUS.get(s, "uploading")


# ── Servicer ──


class AvatarServiceServicer(pb_grpc.AvatarServiceServicer):
    """gRPC servicer that delegates to AvatarService for business logic."""

    def __init__(self, avatar_service_factory: ServiceFactory) -> None:
        self._svc_factory = avatar_service_factory

    async def _svc(self) -> AvatarService:
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

    # ── Avatar CRUD ──

    async def CreateAvatar(
        self,
        request: pb.CreateAvatarRequest,
        context: aio.ServicerContext,
    ) -> pb.Avatar:
        async def handler(svc: AvatarService, req: pb.CreateAvatarRequest) -> pb.Avatar:
            avatar = await svc.create_avatar(
                store_id=req.store_id,
                name=req.name,
                avatar_type=_avatar_type_from_proto(req.type),
            )
            return _avatar_to_proto(avatar)

        return await self._run(handler, request, context)

    async def GetAvatar(
        self,
        request: pb.GetAvatarRequest,
        context: aio.ServicerContext,
    ) -> pb.Avatar:
        async def handler(svc: AvatarService, req: pb.GetAvatarRequest) -> pb.Avatar:
            avatar = await svc.get_avatar(avatar_id=req.avatar_id)
            return _avatar_to_proto(avatar)

        return await self._run(handler, request, context)

    async def UpdateAvatar(
        self,
        request: pb.UpdateAvatarRequest,
        context: aio.ServicerContext,
    ) -> pb.Avatar:
        async def handler(svc: AvatarService, req: pb.UpdateAvatarRequest) -> pb.Avatar:
            kwargs: dict[str, Any] = {}
            if req.HasField("name"):
                kwargs["name"] = req.name
            if req.HasField("custom_params"):
                cp = req.custom_params
                kwargs["custom_params"] = {
                    "skin_smooth": cp.skin_smooth,
                    "face_thin": cp.face_thin,
                    "eye_size": cp.eye_size,
                    "lip_thickness": cp.lip_thickness,
                }
            avatar = await svc.update_avatar(avatar_id=req.avatar_id, **kwargs)
            return _avatar_to_proto(avatar)

        return await self._run(handler, request, context)

    async def DeleteAvatar(
        self,
        request: pb.DeleteAvatarRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(svc: AvatarService, req: pb.DeleteAvatarRequest) -> common_pb.Error:
            await svc.delete_avatar(avatar_id=req.avatar_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    async def ListAvatars(
        self,
        request: pb.ListAvatarsRequest,
        context: aio.ServicerContext,
    ) -> pb.ListAvatarsResponse:
        async def handler(
            svc: AvatarService,
            req: pb.ListAvatarsRequest,
        ) -> pb.ListAvatarsResponse:
            pagination = req.pagination
            page = pagination.page if pagination and pagination.page else 1
            page_size = pagination.page_size if pagination and pagination.page_size else 20

            type_str = _avatar_type_from_proto(req.type) if req.HasField("type") else None

            avatars, total_count = await svc.list_avatars(
                store_id=req.store_id,
                avatar_type=type_str,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            return pb.ListAvatarsResponse(
                avatars=[_avatar_to_proto(a) for a in avatars],
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
        request: pb.StartCloneRequest,
        context: aio.ServicerContext,
    ) -> pb.CloneTask:
        async def handler(
            svc: AvatarService,
            req: pb.StartCloneRequest,
        ) -> pb.CloneTask:
            task = await svc.start_clone(
                avatar_id=req.avatar_id,
                video_data=req.video_data or None,
                duration_seconds=req.duration_seconds,
            )
            return _clone_task_to_proto(task)

        return await self._run(handler, request, context)

    async def GetCloneTask(
        self,
        request: pb.GetCloneTaskRequest,
        context: aio.ServicerContext,
    ) -> pb.CloneTask:
        async def handler(
            svc: AvatarService,
            req: pb.GetCloneTaskRequest,
        ) -> pb.CloneTask:
            task = await svc.get_clone_task(task_id=req.task_id)
            return _clone_task_to_proto(task)

        return await self._run(handler, request, context)
