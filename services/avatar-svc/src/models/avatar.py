"""
SQLAlchemy 2.0 ORM models for Avatar management.

Avatar model stores digital human avatar metadata and clone task records.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Float, func
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


class Avatar(Base):
    """Digital Human Avatar master record."""

    __tablename__ = "avatars"

    avatar_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    avatar_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="2d_real"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    custom_params: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="AvatarCustomParam: skin_smooth, face_thin, eye_size, lip_thickness",
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
        return f"<Avatar {self.avatar_id} '{self.name}'>"


class CloneTask(Base):
    """Avatar clone task record."""

    __tablename__ = "avatar_clone_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    avatar_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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
        return f"<CloneTask {self.task_id} status={self.status}>"
