"""
SQLAlchemy ORM models for compliance audit.

Stores audit results, violation logs, and session-level audit logs.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy.dialects.postgresql import JSON as _JSONType
except ImportError:
    from sqlalchemy import JSON as _JSONType

from libs.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.utcnow()


class AuditResult(Base):
    """Individual audit check result (avatar, script, screenshot, etc.)."""

    __tablename__ = "audit_results"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="avatar / script / screenshot / violation"
    )
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(
        String(32), nullable=False, default="approved",
        comment="approved / rejected / manual_review"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    violations_json: Mapped[list[Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="List of Violation dicts"
    )
    auditor: Mapped[str] = mapped_column(
        String(64), nullable=False, default="system",
        comment="system or human reviewer ID"
    )
    audited_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditResult {self.audit_id} {self.target_type} {self.verdict}>"


class AuditLog(Base):
    """Aggregated audit log for a live session."""

    __tablename__ = "audit_logs"

    audit_log_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    live_room_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    results_json: Mapped[list[Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="List of AuditResult dicts"
    )
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(
        String(32), nullable=False, default="safe",
        comment="safe / low / medium / high"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.audit_log_id} room={self.live_room_id} risk={self.risk_level}>"
