"""
FastAPI HTTP routes for analytics-svc.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query

from libs.common.errors import AppError
from libs.common.logging import get_logger

from .services.analytics_service import AnalyticsService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    global _get_db
    _get_db = get_db_callable


async def _get_svc() -> AsyncIterator[AnalyticsService]:
    if _get_db is None:
        raise RuntimeError("Routes not configured")
    async with _get_db() as session:
        yield AnalyticsService(db=session)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "analytics-svc"}


@router.get("/metrics/live/{live_room_id}")
async def get_live_metrics(
    live_room_id: str,
    svc: AnalyticsService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.get_live_metrics(live_room_id=live_room_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


@router.get("/metrics/realtime/{live_room_id}")
async def get_real_time_metrics(
    live_room_id: str,
    svc: AnalyticsService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.get_real_time_metrics(live_room_id=live_room_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


@router.get("/reports/{session_id}")
async def get_session_report(
    session_id: str,
    svc: AnalyticsService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.get_session_report(session_id=session_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


@router.get("/reports")
async def list_session_reports(
    store_id: str = Query(..., description="Store ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: AnalyticsService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        reports, total = await svc.list_session_reports(
            store_id=store_id, page=page, page_size=page_size
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "reports": [
            {
                "session_id": r.session_id,
                "live_room_id": r.live_room_id,
                "store_id": r.store_id,
                "summary": r.summary_json or {},
                "created_at": int(r.created_at.timestamp() * 1000),
            }
            for r in reports
        ],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


@router.get("/products/{product_id}/performance")
async def get_product_performance(
    product_id: str,
    svc: AnalyticsService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.get_product_performance(product_id=product_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


def _app_error_status(exc: AppError) -> int:
    code = exc.code.value if hasattr(exc.code, "value") else exc.code
    if 2001 <= code <= 2004:
        return 400
    if 3001 <= code <= 3008:
        return 404
    if 4001 <= code <= 4007:
        return 409
    return 500
