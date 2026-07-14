"""
SQLAlchemy ORM models for user profiles and audience segmentation.
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


class AudienceProfile(Base):
    """Audience member profile — behavior tracking and interest modeling."""

    __tablename__ = "audience_profiles"

    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    platform_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    nickname: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    tags: Mapped[list[str] | None] = mapped_column(
        _JSONType, nullable=True, comment="User tags"
    )
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_spent_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interest_categories: Mapped[list[str] | None] = mapped_column(
        _JSONType, nullable=True, comment="Interest categories"
    )
    last_interaction_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_seen_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    __table_args__ = (
        # Unique constraint on (platform_user_id, platform)
        None,
    )

    def __repr__(self) -> str:
        return f"<AudienceProfile {self.profile_id} platform={self.platform}>"


class Segment(Base):
    """Audience segment definition."""

    __tablename__ = "segments"

    segment_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    audience_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Segment {self.segment_id} '{self.name}' size={self.audience_size}>"


class BehaviorEvent(Base):
    """Raw behavior event for tracking."""

    __tablename__ = "behavior_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    platform_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    live_room_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    properties_json: Mapped[dict[str, str] | None] = mapped_column(
        _JSONType, nullable=True, comment="Event properties"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<BehaviorEvent {self.event_type} user={self.platform_user_id}>"
