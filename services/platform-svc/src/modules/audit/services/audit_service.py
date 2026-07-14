"""
Audit service — compliance review, content moderation, 3-tier risk control.

Provides pre-flight checks (avatar/script), live monitoring (screenshots),
and post-session archiving.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import not_found, invalid_arg
from libs.common.logging import get_logger

from models.audit import AuditResult, AuditLog

logger = get_logger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

VALID_VERDICTS = {"approved", "rejected", "manual_review"}
VALID_RISK_LEVELS = {"safe", "low", "medium", "high"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


class AuditService:
    """3-tier audit controls: pre-flight, live monitoring, post-session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Pre-flight Checks ──

    async def audit_avatar(
        self,
        avatar_id: str,
        thumbnail: bytes | None = None,
        celebrity_check: str | None = None,
    ) -> dict[str, Any]:
        """Pre-flight audit of an avatar (mock)."""
        if not avatar_id:
            raise invalid_arg("avatar_id", "must not be empty")

        violations: list[dict] = []
        verdict = "approved"
        reason = ""

        if celebrity_check and celebrity_check.lower() in ("jackie chan", "jay chou", "li na"):
            violations.append({
                "category": "celebrity_ip",
                "description": f"Detected celebrity likeness: {celebrity_check}",
                "severity": "high",
            })
            verdict = "manual_review"
            reason = "Celebrity likeness requires manual review"

        audit = AuditResult(
            target_type="avatar",
            target_id=avatar_id,
            verdict=verdict,
            reason=reason,
            violations_json=violations,
            auditor="system",
            audited_at=int(datetime.utcnow().timestamp()),
        )
        self.db.add(audit)
        await self.db.flush()
        await self.db.refresh(audit)
        logger.info("audit.avatar_complete", avatar_id=avatar_id, verdict=verdict)
        return _audit_result_to_dict(audit)

    async def audit_script(self, script_id: str, full_text: str) -> dict[str, Any]:
        """Pre-flight audit of a live script (mock content moderation)."""
        if not script_id:
            raise invalid_arg("script_id", "must not be empty")
        if not full_text:
            raise invalid_arg("full_text", "must not be empty")

        violations: list[dict] = []
        verdict = "approved"
        reason = ""

        banned_keywords = ["赌博", "色情", "虚假宣传"]
        for kw in banned_keywords:
            if kw in full_text:
                violations.append({
                    "category": "banned_content",
                    "description": f"Found banned keyword: {kw}",
                    "severity": "critical",
                })

        if violations:
            verdict = "rejected"
            reason = f"Found {len(violations)} banned content violations"
        elif len(full_text) > 5000:
            # Add minor warning for long scripts
            violations.append({
                "category": "length_warning",
                "description": "Script exceeds recommended length",
                "severity": "low",
            })

        audit = AuditResult(
            target_type="script",
            target_id=script_id,
            verdict=verdict,
            reason=reason,
            violations_json=violations,
            auditor="system",
            audited_at=int(datetime.utcnow().timestamp()),
        )
        self.db.add(audit)
        await self.db.flush()
        await self.db.refresh(audit)
        logger.info("audit.script_complete", script_id=script_id, verdict=verdict)
        return _audit_result_to_dict(audit)

    # ── Live Monitoring ──

    async def submit_screenshot(
        self,
        live_room_id: str,
        image_data: bytes | None = None,
        timestamp: int = 0,
    ) -> dict[str, Any]:
        """Submit a live screenshot for moderation (mock)."""
        if not live_room_id:
            raise invalid_arg("live_room_id", "must not be empty")

        # Mock: always approve
        audit = AuditResult(
            target_type="screenshot",
            target_id=f"{live_room_id}_{timestamp}",
            verdict="approved",
            reason="No violations detected",
            violations_json=[],
            auditor="system",
            audited_at=int(datetime.utcnow().timestamp()),
        )
        self.db.add(audit)
        await self.db.flush()
        await self.db.refresh(audit)
        return _audit_result_to_dict(audit)

    async def report_violation(
        self,
        live_room_id: str,
        violation_type: str,
        description: str,
        evidence_url: str = "",
    ) -> dict[str, Any]:
        """Report a live violation (mock - creates audit result with violation)."""
        if not live_room_id:
            raise invalid_arg("live_room_id", "must not be empty")
        if not violation_type:
            raise invalid_arg("violation_type", "must not be empty")

        violations = [
            {
                "category": violation_type,
                "description": description or "Reported violation",
                "severity": "medium",
            }
        ]
        audit = AuditResult(
            target_type="violation",
            target_id=live_room_id,
            verdict="manual_review",
            reason=f"Reported: {violation_type}",
            violations_json=violations,
            auditor="system",
            audited_at=int(datetime.utcnow().timestamp()),
        )
        self.db.add(audit)
        await self.db.flush()
        await self.db.refresh(audit)
        logger.info("audit.violation_reported", room=live_room_id, type=violation_type)
        return _audit_result_to_dict(audit)

    # ── Post-session Archive ──

    async def get_audit_log(self, audit_log_id: str) -> AuditLog:
        """Get an audit log by ID."""
        stmt = select(AuditLog).where(AuditLog.audit_log_id == audit_log_id)
        result = await self.db.execute(stmt)
        log = result.scalars().one_or_none()
        if not log:
            raise not_found("AuditLog", audit_log_id)
        return log

    async def list_audit_logs(
        self,
        store_id: str,
        risk_level: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs for a store."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [AuditLog.store_id == store_id]
        if risk_level:
            conditions.append(AuditLog.risk_level == risk_level)

        count_stmt = select(func.count()).select_from(AuditLog).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(AuditLog)
            .where(*conditions)
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())
        return logs, total_count


def _audit_result_to_dict(a: AuditResult) -> dict[str, Any]:
    """Convert AuditResult ORM to dict."""
    return {
        "audit_id": a.audit_id,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "verdict": a.verdict,
        "reason": a.reason,
        "violations": a.violations_json or [],
        "audited_at": a.audited_at,
        "auditor": a.auditor,
    }
