"""
SQLAlchemy ORM models for platform sync.

Stores store-to-platform bindings and sync job records.
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


class PlatformStoreBinding(Base):
    """A store's OAuth binding to a third-party platform."""

    __tablename__ = "platform_store_bindings"

    binding_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_store_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform_store_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_expires_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bound_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<PlatformStoreBinding {self.binding_id} {self.platform}>"


class SyncJob(Base):
    """A job that syncs a product to/from a platform."""

    __tablename__ = "sync_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="push")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SyncJob {self.job_id} product={self.product_id} status={self.status}>"
