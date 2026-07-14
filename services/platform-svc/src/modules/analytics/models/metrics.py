"""
SQLAlchemy ORM models for analytics.

Stores live metrics, session reports, and product performance data.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, func
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


class LiveMetrics(Base):
    """Snapshots of live room metrics."""

    __tablename__ = "live_metrics"

    metric_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    live_room_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    viewer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peak_viewer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    danmaku_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interaction_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    product_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gmv_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<LiveMetrics {self.live_room_id} viewers={self.viewer_count}>"


class SessionReport(Base):
    """Summarized session report for a completed live stream."""

    __tablename__ = "session_reports"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    live_room_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="LiveMetrics summary as JSON"
    )
    viewer_timeline: Mapped[list[Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="Time-series viewer data"
    )
    danmaku_timeline: Mapped[list[Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="Time-series danmaku data"
    )
    gmv_timeline: Mapped[list[Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="Time-series GMV data"
    )
    funnel_json: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONType, nullable=True, comment="Funnel metrics"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<SessionReport {self.session_id} room={self.live_room_id}>"


class ProductPerformance(Base):
    """Aggregated performance data for a product."""

    __tablename__ = "product_performance"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_appearances: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    click_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_gmv_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_attention_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<ProductPerformance {self.product_id} orders={self.total_orders}>"
