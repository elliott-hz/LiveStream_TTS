"""SQLAlchemy async models for the Live Manager service.

Models
------
- LiveRoom: Central entity representing a digital human livestream room.
- Playlist: Ordered playlist of items for a live room (1:1 with LiveRoom).
- LiveSession: Record of a single live broadcast session.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.db import Base


class LiveRoom(Base):
    """A digital human livestream room.

    Each room belongs to a store and tracks its lifecycle from draft
    through ready / live / paused to ended / error.
    """

    __tablename__ = "live_rooms"

    live_room_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    store_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    cover_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )
    avatar_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    voice_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    script_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    stream_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    loop_rule: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    target_platforms: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    playlist = relationship(
        "Playlist", back_populates="live_room", uselist=False, lazy="selectin"
    )
    sessions = relationship(
        "LiveSession", back_populates="live_room", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<LiveRoom {self.title} (id={self.live_room_id}) status={self.status}>"


class Playlist(Base):
    """Ordered playlist for a live room.

    Each live room has at most one playlist containing items that define
    the broadcast sequence (script segments, warmups, breaks, etc.).
    """

    __tablename__ = "playlists"

    playlist_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    live_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("live_rooms.live_room_id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    loop_rule: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    live_room = relationship("LiveRoom", back_populates="playlist")

    def __repr__(self) -> str:
        return f"<Playlist (id={self.playlist_id}) room={self.live_room_id} items={len(self.items)}>"


class LiveSession(Base):
    """A single live broadcast session.

    A new session is created each time a room starts streaming and is
    closed when the stream ends.
    """

    __tablename__ = "live_sessions"

    session_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    live_room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("live_rooms.live_room_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    viewer_peak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_interactions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    emergency_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    live_room = relationship("LiveRoom", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<LiveSession (id={self.session_id}) room={self.live_room_id}>"
