"""
gRPC service implementation for PlatformSyncService.

Maps each RPC to BindingService or SyncService methods.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from platform_sync.v1 import platform_sync_pb2 as pb
from platform_sync.v1 import platform_sync_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.platform import PlatformStoreBinding, SyncJob
from services.binding_service import BindingService
from services.sync_service import SyncService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, Any]]


_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
    ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
    ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
    ErrorCode.PLATFORM_API_ERROR: grpc.StatusCode.UNAVAILABLE,
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


# ── Proto converters ──


_MAP_PLATFORM = {
    "PLATFORM_UNSPECIFIED": 0,
    "PLATFORM_TAOBAO": 1,
    "PLATFORM_DOUYIN": 2,
    "PLATFORM_JD": 3,
    "PLATFORM_KUAISHOU": 4,
    "PLATFORM_PINDUODUO": 5,
}
_REV_PLATFORM = {v: k.lower() for k, v in _MAP_PLATFORM.items()}


def _platform_from_proto(p: int) -> str:
    return _REV_PLATFORM.get(p, "unspecified")


def _platform_to_proto(p: str) -> int:
    lookup = {v.lower(): k for k, v in _MAP_PLATFORM.items()}
    return lookup.get(p, 0)


_MAP_BINDING_STATUS = {
    "active": pb.BindingStatus.BINDING_STATUS_ACTIVE,
    "expired": pb.BindingStatus.BINDING_STATUS_EXPIRED,
    "revoked": pb.BindingStatus.BINDING_STATUS_REVOKED,
}
_REV_BINDING_STATUS = {v: k for k, v in _MAP_BINDING_STATUS.items()}


def _binding_status_to_proto(s: str) -> int:
    return _MAP_BINDING_STATUS.get(s, pb.BindingStatus.BINDING_STATUS_UNSPECIFIED)


_MAP_JOB_STATUS = {
    "pending": pb.SyncJobStatus.SYNC_JOB_STATUS_PENDING,
    "in_progress": pb.SyncJobStatus.SYNC_JOB_STATUS_IN_PROGRESS,
    "success": pb.SyncJobStatus.SYNC_JOB_STATUS_SUCCESS,
    "failed": pb.SyncJobStatus.SYNC_JOB_STATUS_FAILED,
}
_REV_JOB_STATUS = {v: k for k, v in _MAP_JOB_STATUS.items()}


def _job_status_to_proto(s: str) -> int:
    return _MAP_JOB_STATUS.get(s, pb.SyncJobStatus.SYNC_JOB_STATUS_UNSPECIFIED)


def _job_status_from_proto(s: int) -> str:
    return _REV_JOB_STATUS.get(s, "pending")


def _binding_to_proto(b: PlatformStoreBinding) -> pb.PlatformStoreBinding:
    return pb.PlatformStoreBinding(
        binding_id=b.binding_id,
        store_id=b.store_id,
        platform=_platform_to_proto(b.platform),
        platform_store_id=b.platform_store_id,
        platform_store_name=b.platform_store_name,
        status=_binding_status_to_proto(b.status),
        access_token_encrypted=b.access_token_encrypted,
        token_expires_at=b.token_expires_at,
        bound_at=b.bound_at,
    )


def _sync_job_to_proto(j: SyncJob) -> pb.SyncJob:
    completed_ms = 0
    if j.completed_at:
        completed_ms = int(j.completed_at.timestamp() * 1000)
    return pb.SyncJob(
        job_id=j.job_id,
        product_id=j.product_id,
        platform=_platform_to_proto(j.platform),
        status=_job_status_to_proto(j.status),
        platform_product_id=j.platform_product_id,
        error_message=j.error_message,
        retry_count=j.retry_count,
        created_at=int(j.created_at.timestamp() * 1000),
        completed_at=completed_ms,
    )


# ── Servicer ──


class PlatformSyncServiceServicer(pb_grpc.PlatformSyncServiceServicer):
    """gRPC servicer for PlatformSyncService."""

    def __init__(
        self,
        binding_service_factory: ServiceFactory,
        sync_service_factory: ServiceFactory,
    ) -> None:
        self._binding_factory = binding_service_factory
        self._sync_factory = sync_service_factory

    async def _run(
        self,
        handler,
        request,
        context: aio.ServicerContext,
    ) -> Any:
        try:
            return await handler(request)
        except AppError as exc:
            _app_error_to_grpc_context(exc, context)
            return None
        except Exception as exc:
            logger.exception("grpc.handler_error", method=context.method)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return None

    # ── Store Binding ──

    async def BindPlatformStore(
        self,
        request: pb.BindPlatformStoreRequest,
        context: aio.ServicerContext,
    ) -> pb.PlatformStoreBinding:
        async def handler(req: pb.BindPlatformStoreRequest) -> pb.PlatformStoreBinding:
            svc = await self._binding_factory()
            binding = await svc.bind_store(
                store_id=req.store_id,
                platform=_platform_from_proto(req.platform),
                auth_code=req.auth_code,
            )
            return _binding_to_proto(binding)

        return await self._run(handler, request, context)

    async def UnbindPlatformStore(
        self,
        request: pb.UnbindPlatformStoreRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(req: pb.UnbindPlatformStoreRequest) -> common_pb.Error:
            svc = await self._binding_factory()
            await svc.unbind_store(binding_id=req.binding_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    async def ListBindings(
        self,
        request: pb.ListBindingsRequest,
        context: aio.ServicerContext,
    ) -> pb.ListBindingsResponse:
        async def handler(req: pb.ListBindingsRequest) -> pb.ListBindingsResponse:
            svc = await self._binding_factory()
            bindings = await svc.list_bindings(store_id=req.store_id)
            return pb.ListBindingsResponse(
                bindings=[_binding_to_proto(b) for b in bindings]
            )

        return await self._run(handler, request, context)

    # ── Product Sync ──

    async def SyncProduct(
        self,
        request: pb.SyncProductRequest,
        context: aio.ServicerContext,
    ) -> pb.SyncJob:
        async def handler(req: pb.SyncProductRequest) -> pb.SyncJob:
            svc = await self._sync_factory()
            direction = "push" if req.direction == 1 else "pull"
            job = await svc.sync_product(
                product_id=req.product_id,
                platform=_platform_from_proto(req.target_platform),
                direction=direction,
            )
            return _sync_job_to_proto(job)

        return await self._run(handler, request, context)

    async def BulkSyncProducts(
        self,
        request: pb.BulkSyncProductsRequest,
        context: aio.ServicerContext,
    ) -> pb.BulkSyncResponse:
        async def handler(req: pb.BulkSyncProductsRequest) -> pb.BulkSyncResponse:
            svc = await self._sync_factory()
            platforms = [_platform_from_proto(p) for p in req.target_platforms]
            jobs = await svc.bulk_sync(
                product_ids=list(req.product_ids),
                platforms=platforms,
            )
            return pb.BulkSyncResponse(jobs=[_sync_job_to_proto(j) for j in jobs])

        return await self._run(handler, request, context)

    # ── Job Status ──

    async def GetSyncJob(
        self,
        request: pb.GetSyncJobRequest,
        context: aio.ServicerContext,
    ) -> pb.SyncJob:
        async def handler(req: pb.GetSyncJobRequest) -> pb.SyncJob:
            svc = await self._sync_factory()
            job = await svc.get_sync_job(job_id=req.job_id)
            return _sync_job_to_proto(job)

        return await self._run(handler, request, context)

    async def ListSyncJobs(
        self,
        request: pb.ListSyncJobsRequest,
        context: aio.ServicerContext,
    ) -> pb.ListSyncJobsResponse:
        async def handler(req: pb.ListSyncJobsRequest) -> pb.ListSyncJobsResponse:
            svc = await self._sync_factory()
            status = _job_status_from_proto(req.status) if req.HasField("status") else None
            page = req.pagination.page if req.pagination and req.pagination.page else 1
            page_size = req.pagination.page_size if req.pagination and req.pagination.page_size else 20

            jobs, total_count = await svc.list_sync_jobs(
                store_id=req.store_id or None,
                status=status,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            return pb.ListSyncJobsResponse(
                jobs=[_sync_job_to_proto(j) for j in jobs],
                page_info=common_pb.PageInfo(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    total_pages=total_pages,
                ),
            )

        return await self._run(handler, request, context)
