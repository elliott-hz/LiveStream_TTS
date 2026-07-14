"""
FastAPI HTTP routes for billing-svc.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query

from libs.common.errors import AppError
from libs.common.logging import get_logger

from services.billing_service import BillingService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    global _get_db
    _get_db = get_db_callable


async def _get_svc() -> AsyncIterator[BillingService]:
    if _get_db is None:
        raise RuntimeError("Routes not configured")
    async with _get_db() as session:
        yield BillingService(db=session)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "billing-svc"}


@router.get("/plans")
async def list_plans(
    svc: BillingService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        plans = await svc.list_plans()
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"plans": [{"plan_id": p.plan_id, "name": p.name, "monthly_price_fen": p.monthly_price_fen} for p in plans]}


@router.post("/subscribe")
async def subscribe(
    body: dict[str, Any],
    svc: BillingService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        sub = await svc.subscribe(
            store_id=body.get("store_id", ""),
            plan_id=body.get("plan_id", ""),
            auto_renew=body.get("auto_renew", True),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {
        "subscription_id": sub.subscription_id,
        "store_id": sub.store_id,
        "plan_id": sub.plan_id,
        "status": sub.status,
        "expires_at": sub.expires_at,
    }


@router.get("/usage/{store_id}")
async def get_usage(
    store_id: str,
    svc: BillingService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        data = await svc.get_current_usage(store_id=store_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return data


@router.post("/usage/report")
async def report_usage(
    body: dict[str, Any],
    svc: BillingService = Depends(_get_svc),
) -> dict[str, str]:
    try:
        await svc.report_usage(
            store_id=body.get("store_id", ""),
            metric=body.get("metric", ""),
            value=body.get("value", 0),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"status": "ok"}


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    svc: BillingService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        inv = await svc.get_invoice(invoice_id=invoice_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {"invoice_id": inv.invoice_id, "store_id": inv.store_id, "amount_fen": inv.amount_fen, "status": inv.status}


@router.get("/invoices")
async def list_invoices(
    store_id: str = Query(...),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: BillingService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        invoices, total = await svc.list_invoices(
            store_id=store_id, status=status, page=page, page_size=page_size
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "invoices": [
            {"invoice_id": i.invoice_id, "store_id": i.store_id, "amount_fen": i.amount_fen, "status": i.status}
            for i in invoices
        ],
        "page_info": {"page": page, "page_size": page_size, "total_count": total, "total_pages": total_pages},
    }


def _app_error_status(exc: AppError) -> int:
    code = exc.code.value if hasattr(exc.code, "value") else exc.code
    if 2001 <= code <= 2004:
        return 400
    if 3001 <= code <= 3008:
        return 404
    if 4001 <= code <= 4007:
        return 409
    return 500
