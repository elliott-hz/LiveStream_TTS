"""
gRPC service implementation for AuditService.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from libs.proto.audit.v1 import audit_pb2 as pb
from libs.proto.audit.v1 import audit_pb2_grpc as pb_grpc
from libs.proto.common.v1 import common_pb2 as common_pb

from models.audit import AuditLog
from .services.audit_service import AuditService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, AuditService]]


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


_MAP_VERDICT = {
    "approved": pb.AuditVerdict.AUDIT_VERDICT_APPROVED,
    "rejected": pb.AuditVerdict.AUDIT_VERDICT_REJECTED,
    "manual_review": pb.AuditVerdict.AUDIT_VERDICT_MANUAL_REVIEW,
}
_REV_VERDICT = {v: k for k, v in _MAP_VERDICT.items()}


def _verdict_to_proto(v: str) -> int:
    return _MAP_VERDICT.get(v, pb.AuditVerdict.AUDIT_VERDICT_UNSPECIFIED)


_MAP_SEVERITY = {
    "low": pb.Severity.SEVERITY_LOW,
    "medium": pb.Severity.SEVERITY_MEDIUM,
    "high": pb.Severity.SEVERITY_HIGH,
    "critical": pb.Severity.SEVERITY_CRITICAL,
}
_REV_SEVERITY = {v: k for k, v in _MAP_SEVERITY.items()}


def _severity_to_proto(s: str) -> int:
    return _MAP_SEVERITY.get(s, pb.Severity.SEVERITY_UNSPECIFIED)


_MAP_RISK = {
    "safe": pb.RiskLevel.RISK_LEVEL_SAFE,
    "low": pb.RiskLevel.RISK_LEVEL_LOW,
    "medium": pb.RiskLevel.RISK_LEVEL_MEDIUM,
    "high": pb.RiskLevel.RISK_LEVEL_HIGH,
}
_REV_RISK = {v: k for k, v in _MAP_RISK.items()}


def _risk_level_to_proto(r: str) -> int:
    return _MAP_RISK.get(r, pb.RiskLevel.RISK_LEVEL_UNSPECIFIED)


def _risk_level_from_proto(r: int) -> str:
    return _REV_RISK.get(r, "safe")


def _violation_to_proto(v: dict) -> pb.Violation:
    return pb.Violation(
        category=v.get("category", ""),
        description=v.get("description", ""),
        severity=_severity_to_proto(v.get("severity", "low")),
    )


def _result_to_proto(audit_data: dict) -> pb.AuditResult:
    return pb.AuditResult(
        audit_id=audit_data["audit_id"],
        target_type=audit_data["target_type"],
        target_id=audit_data["target_id"],
        verdict=_verdict_to_proto(audit_data.get("verdict", "approved")),
        reason=audit_data.get("reason", ""),
        violations=[_violation_to_proto(v) for v in audit_data.get("violations", [])],
        audited_at=audit_data.get("audited_at", 0),
        auditor=audit_data.get("auditor", "system"),
    )


def _log_to_proto(log: AuditLog) -> pb.AuditLog:
    results = log.results_json or []
    return pb.AuditLog(
        audit_log_id=log.audit_log_id,
        session_id=log.session_id,
        live_room_id=log.live_room_id,
        results=[_result_to_proto(r) for r in results],
        violation_count=log.violation_count,
        risk_level=_risk_level_to_proto(log.risk_level),
        created_at=int(log.created_at.timestamp() * 1000),
    )


class AuditServiceServicer(pb_grpc.AuditServiceServicer):
    """gRPC servicer for AuditService."""

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

    async def AuditAvatar(
        self, request: pb.AuditAvatarRequest, context: aio.ServicerContext
    ) -> pb.AuditResult:
        async def handler(svc, req):
            data = await svc.audit_avatar(
                avatar_id=req.avatar_id,
                thumbnail=req.thumbnail if req.thumbnail else None,
                celebrity_check=req.celebrity_check or None,
            )
            return _result_to_proto(data)
        return await self._run(handler, request, context)

    async def AuditScript(
        self, request: pb.AuditScriptRequest, context: aio.ServicerContext
    ) -> pb.AuditResult:
        async def handler(svc, req):
            data = await svc.audit_script(
                script_id=req.script_id,
                full_text=req.full_text,
            )
            return _result_to_proto(data)
        return await self._run(handler, request, context)

    async def SubmitScreenshot(
        self, request: pb.SubmitScreenshotRequest, context: aio.ServicerContext
    ) -> pb.AuditResult:
        async def handler(svc, req):
            data = await svc.submit_screenshot(
                live_room_id=req.live_room_id,
                image_data=req.image_data if req.image_data else None,
                timestamp=req.timestamp,
            )
            return _result_to_proto(data)
        return await self._run(handler, request, context)

    async def ReportViolation(
        self, request: pb.ReportViolationRequest, context: aio.ServicerContext
    ) -> pb.AuditResult:
        async def handler(svc, req):
            data = await svc.report_violation(
                live_room_id=req.live_room_id,
                violation_type=req.violation_type,
                description=req.description,
                evidence_url=req.evidence_url or "",
            )
            return _result_to_proto(data)
        return await self._run(handler, request, context)

    async def GetAuditLog(
        self, request: pb.GetAuditLogRequest, context: aio.ServicerContext
    ) -> pb.AuditLog:
        async def handler(svc, req):
            log = await svc.get_audit_log(audit_log_id=req.audit_log_id)
            return _log_to_proto(log)
        return await self._run(handler, request, context)

    async def ListAuditLogs(
        self, request: pb.ListAuditLogsRequest, context: aio.ServicerContext
    ) -> pb.ListAuditLogsResponse:
        async def handler(svc, req):
            risk = _risk_level_from_proto(req.risk_level) if req.HasField("risk_level") else None
            page = req.pagination.page if req.pagination and req.pagination.page else 1
            page_size = req.pagination.page_size if req.pagination and req.pagination.page_size else 20
            logs, total = await svc.list_audit_logs(
                store_id=req.store_id,
                risk_level=risk,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total + page_size - 1) // page_size)
            return pb.ListAuditLogsResponse(
                logs=[_log_to_proto(l) for l in logs],
                page_info=common_pb.PageInfo(
                    page=page, page_size=page_size, total_count=total, total_pages=total_pages
                ),
            )
        return await self._run(handler, request, context)
