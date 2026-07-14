"""
Tests for analytics-svc: live metrics, session reports, product performance.
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
_LIBS_PROTO = str(Path(_REPO_ROOT) / "libs" / "proto")

for _p in (_REPO_ROOT, _SRC_DIR, _LIBS_PROTO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.db import Base
from models.metrics import LiveMetrics, SessionReport, ProductPerformance

import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_live_metrics(db_session):
    """Test live metrics returns mock data."""
    from services.analytics_service import AnalyticsService
    svc = AnalyticsService(db=db_session)

    metrics = await svc.get_live_metrics(live_room_id="room_001")
    assert metrics["live_room_id"] == "room_001"
    assert metrics["viewer_count"] > 0
    assert metrics["gmv_fen"] > 0
    assert metrics["duration_seconds"] > 0


@pytest.mark.asyncio
async def test_get_real_time_metrics(db_session):
    """Test real-time metrics returns mock data with top products."""
    from services.analytics_service import AnalyticsService
    svc = AnalyticsService(db=db_session)

    metrics = await svc.get_real_time_metrics(live_room_id="room_001")
    assert metrics["live_room_id"] == "room_001"
    assert metrics["current_viewers"] > 0
    assert len(metrics["top_products"]) > 0
    assert metrics["top_products"][0]["product_id"] is not None


@pytest.mark.asyncio
async def test_get_product_performance(db_session):
    """Test product performance returns mock data."""
    from services.analytics_service import AnalyticsService
    svc = AnalyticsService(db=db_session)

    perf = await svc.get_product_performance(product_id="prod_001")
    assert perf["product_id"] == "prod_001"
    assert perf["total_appearances"] > 0
    assert perf["total_orders"] > 0


@pytest.mark.asyncio
async def test_create_and_get_session_report(db_session):
    """Test creating a session report and fetching it."""
    from models.metrics import SessionReport
    from services.analytics_service import AnalyticsService

    # Create a session report manually
    report = SessionReport(
        session_id="sess_001",
        live_room_id="room_001",
        store_id="store_001",
        summary_json={"live_room_id": "room_001", "viewer_count": 100},
        viewer_timeline=[{"timestamp": 1000, "value": 100}],
        funnel_json={"impressions": 500, "orders": 50},
    )
    db_session.add(report)
    await db_session.flush()

    svc = AnalyticsService(db=db_session)
    result = await svc.get_session_report(session_id="sess_001")
    assert result is not None
    assert result["session_id"] == "sess_001"
    assert result["summary"]["viewer_count"] == 100
    assert result["funnel"]["impressions"] == 500


@pytest.mark.asyncio
async def test_list_session_reports(db_session):
    """Test listing session reports with pagination."""
    from models.metrics import SessionReport
    from services.analytics_service import AnalyticsService

    for i in range(3):
        report = SessionReport(
            session_id=f"sess_{i:03d}",
            live_room_id=f"room_{i}",
            store_id="store_001",
        )
        db_session.add(report)
    await db_session.flush()

    svc = AnalyticsService(db=db_session)
    reports, total = await svc.list_session_reports(store_id="store_001")
    assert total == 3
    assert len(reports) == 3
