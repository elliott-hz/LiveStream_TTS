"""
SQLAlchemy 2.0 ORM models for Voice/Timbre management.

Voice model stores voice metadata and clone task records.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Boolean, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from libs.db import Base

try:
    from sqlalchemy.dialects.postgresql import JSON as _JSONType
except ImportError:
    from sqlalchemy import JSON as _JSONType  # type: ignore[assignment]


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.utcnow()


class Voice(Base):
    """Voice/Timbre master record."""

    __tablename__ = "voices"

    voice_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="male")
    age_range: Mapped[str] = mapped_column(String(32), nullable=False, default="25-35")
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    style: Mapped[str] = mapped_column(
        String(32), nullable=False, default="professional"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_metrics: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="PaintingQualityMetrics: mos_score, similarity_score, evaluated_at",
    )
    prompt_audio_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="Uploaded prompt audio file URL",
    )
    preview_audio_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="Generated preview audio URL",
    )
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return f"<Voice {self.voice_id} '{self.name}'>"


class VoiceCloneTask(Base):
    """Voice clone task record."""

    __tablename__ = "voice_clone_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    voice_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploading"
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:
        return f"<VoiceCloneTask {self.task_id} status={self.status}>"
