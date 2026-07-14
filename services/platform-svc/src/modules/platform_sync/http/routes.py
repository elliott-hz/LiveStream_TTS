"""
FastAPI HTTP routes for platform-sync-svc.

Provides REST-style endpoints for sync jobs and store bindings.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError
from libs.common.logging import get_logger

from models.platform import PlatformStoreBinding, SyncJob
from .services.binding_service import BindingService
from .services.sync_service import SyncService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    global _get_db
    _get_db = get_db_callable


async def _get_binding_svc() -> AsyncIterator[BindingService]:
    if _get_db is None:
        raise RuntimeError("Routes not configured")
    async with _get_db() as session:
        yield BindingService(db=session)


async def _get_sync_svc() -> AsyncIterator[SyncService]:
    if _get_db is None:
        raise RuntimeError("Routes not configured")
    async with _get_db() as session:
        yield SyncService(db=session)


# ── Health ──


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "platform-sync-svc"}


# ── Store Bindings ──


@router.post("/bindings")
async def bind_platform_store(
    body: dict[str, Any],
    svc: BindingService = Depends(_get_binding_svc),
) -> dict[str, Any]:
    try:
        binding = await svc.bind_store(
            store_id=body.get("store_id", ""),
            platform=body.get("platform", ""),
            auth_code=body.get("auth_code", ""),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _binding_dict(binding)


@router.delete("/bindings/{binding_id}")
async def unbind_platform_store(
    binding_id: str,
    svc: BindingService = Depends(_get_binding_svc),
) -> dict[str, str]:
    try:
        await svc.unbind_store(binding_id=binding_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"status": "revoked"}


@router.get("/bindings")
async def list_bindings(
    store_id: str = Query(..., description="Store ID"),
    svc: BindingService = Depends(_get_binding_svc),
) -> dict[str, Any]:
    try:
        bindings = await svc.list_bindings(store_id=store_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"bindings": [_binding_dict(b) for b in bindings]}


# ── Sync Jobs ──


@router.post("/sync")
async def sync_product(
    body: dict[str, Any],
    svc: SyncService = Depends(_get_sync_svc),
) -> dict[str, Any]:
    try:
        job = await svc.sync_product(
            product_id=body.get("product_id", ""),
            platform=body.get("platform", ""),
            direction=body.get("direction", "push"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _sync_job_dict(job)


@router.post("/sync/bulk")
async def bulk_sync(
    body: dict[str, Any],
    svc: SyncService = Depends(_get_sync_svc),
) -> dict[str, Any]:
    try:
        jobs = await svc.bulk_sync(
            product_ids=body.get("product_ids", []),
            platforms=body.get("platforms", []),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"jobs": [_sync_job_dict(j) for j in jobs]}


@router.get("/sync/{job_id}")
async def get_sync_job(
    job_id: str,
    svc: SyncService = Depends(_get_sync_svc),
) -> dict[str, Any]:
    try:
        job = await svc.get_sync_job(job_id=job_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _sync_job_dict(job)


@router.get("/sync")
async def list_sync_jobs(
    store_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: SyncService = Depends(_get_sync_svc),
) -> dict[str, Any]:
    try:
        jobs, total = await svc.list_sync_jobs(
            store_id=store_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "jobs": [_sync_job_dict(j) for j in jobs],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


# ── Converters ──


def _binding_dict(b: PlatformStoreBinding) -> dict[str, Any]:
    return {
        "binding_id": b.binding_id,
        "store_id": b.store_id,
        "platform": b.platform,
        "platform_store_id": b.platform_store_id,
        "platform_store_name": b.platform_store_name,
        "status": b.status,
        "bound_at": b.bound_at,
    }


def _sync_job_dict(j: SyncJob) -> dict[str, Any]:
    return {
        "job_id": j.job_id,
        "product_id": j.product_id,
        "platform": j.platform,
        "direction": j.direction,
        "status": j.status,
        "platform_product_id": j.platform_product_id,
        "error_message": j.error_message,
        "retry_count": j.retry_count,
        "created_at": int(j.created_at.timestamp() * 1000),
        "completed_at": int(j.completed_at.timestamp() * 1000) if j.completed_at else 0,
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
