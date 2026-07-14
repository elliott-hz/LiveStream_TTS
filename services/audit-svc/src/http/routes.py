"""
FastAPI HTTP routes for audit-svc.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query

from libs.common.errors import AppError
from libs.common.logging import get_logger

from services.audit_service import AuditService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    global _get_db
    _get_db = get_db_callable


async def _get_svc() -> AsyncIterator[AuditService]:
    if _get_db is None:
        raise RuntimeError("Routes not configured")
    async with _get_db() as session:
        yield AuditService(db=session)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "audit-svc"}


@router.post("/audit/avatar")
async def audit_avatar(
    body: dict[str, Any],
    svc: AuditService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        result = await svc.audit_avatar(
            avatar_id=body.get("avatar_id", ""),
            celebrity_check=body.get("celebrity_check"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return result


@router.post("/audit/script")
async def audit_script(
    body: dict[str, Any],
    svc: AuditService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        result = await svc.audit_script(
            script_id=body.get("script_id", ""),
            full_text=body.get("full_text", ""),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return result


@router.post("/screenshot")
async def submit_screenshot(
    body: dict[str, Any],
    svc: AuditService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        result = await svc.submit_screenshot(
            live_room_id=body.get("live_room_id", ""),
            timestamp=body.get("timestamp", 0),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return result


@router.post("/violation/report")
async def report_violation(
    body: dict[str, Any],
    svc: AuditService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        result = await svc.report_violation(
            live_room_id=body.get("live_room_id", ""),
            violation_type=body.get("violation_type", ""),
            description=body.get("description", ""),
            evidence_url=body.get("evidence_url", ""),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return result


@router.get("/logs/{audit_log_id}")
async def get_audit_log(
    audit_log_id: str,
    svc: AuditService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        log = await svc.get_audit_log(audit_log_id=audit_log_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return {
        "audit_log_id": log.audit_log_id,
        "session_id": log.session_id,
        "live_room_id": log.live_room_id,
        "violation_count": log.violation_count,
        "risk_level": log.risk_level,
    }


@router.get("/logs")
async def list_audit_logs(
    store_id: str = Query(...),
    risk_level: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: AuditService = Depends(_get_svc),
) -> dict[str, Any]:
    try:
        logs, total = await svc.list_audit_logs(
            store_id=store_id, risk_level=risk_level, page=page, page_size=page_size
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "logs": [
            {
                "audit_log_id": l.audit_log_id,
                "session_id": l.session_id,
                "live_room_id": l.live_room_id,
                "violation_count": l.violation_count,
                "risk_level": l.risk_level,
            }
            for l in logs
        ],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
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
