"""
Analytics service — aggregates metrics from mock data.

Provides live metrics, session reports, and product performance.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import not_found, invalid_arg
from libs.common.logging import get_logger

from models.metrics import LiveMetrics, SessionReport, ProductPerformance

logger = get_logger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class AnalyticsService:
    """Aggregate and return analytics data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_live_metrics(self, live_room_id: str) -> dict[str, Any]:
        """Get current live metrics for a room (mock data)."""
        if not live_room_id:
            raise invalid_arg("live_room_id", "must not be empty")

        # Try DB first, fall back to mock
        stmt = (
            select(LiveMetrics)
            .where(LiveMetrics.live_room_id == live_room_id)
            .order_by(desc(LiveMetrics.recorded_at))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        metrics = result.scalars().first()
        if metrics:
            return {
                "live_room_id": metrics.live_room_id,
                "viewer_count": metrics.viewer_count,
                "peak_viewer_count": metrics.peak_viewer_count,
                "danmaku_count": metrics.danmaku_count,
                "interaction_count": metrics.interaction_count,
                "interaction_rate": metrics.interaction_rate,
                "product_clicks": metrics.product_clicks,
                "orders": metrics.orders,
                "gmv_fen": metrics.gmv_fen,
                "duration_seconds": metrics.duration_seconds,
            }

        # Mock data
        return {
            "live_room_id": live_room_id,
            "viewer_count": 1523,
            "peak_viewer_count": 2100,
            "danmaku_count": 342,
            "interaction_count": 89,
            "interaction_rate": 5.8,
            "product_clicks": 456,
            "orders": 67,
            "gmv_fen": 1289000,
            "duration_seconds": 5400,
        }

    async def get_real_time_metrics(self, live_room_id: str) -> dict[str, Any]:
        """Get real-time metrics (mock data)."""
        if not live_room_id:
            raise invalid_arg("live_room_id", "must not be empty")
        return {
            "live_room_id": live_room_id,
            "current_viewers": 1234,
            "danmaku_per_minute": 45,
            "orders_last_5min": 12,
            "gmv_last_5min_fen": 234500,
            "avg_watch_seconds": 187.5,
            "top_products": [
                {"product_id": "p_001", "title": "爆款商品A", "clicks": 120, "orders": 18},
                {"product_id": "p_002", "title": "新品B", "clicks": 89, "orders": 7},
            ],
        }

    async def get_session_report(self, session_id: str) -> dict[str, Any] | None:
        """Get a session report by ID."""
        stmt = select(SessionReport).where(SessionReport.session_id == session_id)
        result = await self.db.execute(stmt)
        report = result.scalars().one_or_none()
        if not report:
            raise not_found("SessionReport", session_id)

        return {
            "session_id": report.session_id,
            "live_room_id": report.live_room_id,
            "summary": report.summary_json or {},
            "viewer_timeline": report.viewer_timeline or [],
            "danmaku_timeline": report.danmaku_timeline or [],
            "gmv_timeline": report.gmv_timeline or [],
            "funnel": report.funnel_json or {},
        }

    async def list_session_reports(
        self,
        store_id: str,
        start_date: int | None = None,
        end_date: int | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[SessionReport], int]:
        """List session reports for a store with pagination."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [SessionReport.store_id == store_id]

        count_stmt = select(func.count()).select_from(SessionReport).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(SessionReport)
            .where(*conditions)
            .order_by(desc(SessionReport.created_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        reports = list(result.scalars().all())
        return reports, total_count

    async def get_product_performance(self, product_id: str) -> dict[str, Any]:
        """Get product performance data (mock + DB)."""
        if not product_id:
            raise invalid_arg("product_id", "must not be empty")

        stmt = select(ProductPerformance).where(
            ProductPerformance.product_id == product_id
        )
        result = await self.db.execute(stmt)
        pp = result.scalars().one_or_none()
        if pp:
            return {
                "product_id": pp.product_id,
                "total_appearances": pp.total_appearances,
                "total_clicks": pp.total_clicks,
                "click_rate": pp.click_rate,
                "total_orders": pp.total_orders,
                "total_gmv_fen": pp.total_gmv_fen,
                "avg_attention_seconds": pp.avg_attention_seconds,
            }

        # Mock data
        return {
            "product_id": product_id,
            "total_appearances": 12,
            "total_clicks": 890,
            "click_rate": 0.12,
            "total_orders": 134,
            "total_gmv_fen": 2560000,
            "avg_attention_seconds": 45,
        }
