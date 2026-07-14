"""
Tests for profile-svc: profile CRUD, event tracking, segmentation.
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
from models.profile import AudienceProfile, Segment, BehaviorEvent

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
async def test_create_and_get_profile(db_session):
    """Test creating a profile via update and fetching it."""
    from services.profile_service import ProfileService
    svc = ProfileService(db=db_session)

    data = await svc.update_profile(
        platform_user_id="user_001",
        platform="taobao",
        nickname="测试用户",
        tags=["高消费", "新用户"],
    )
    assert data["profile_id"] is not None
    assert data["platform_user_id"] == "user_001"
    assert data["nickname"] == "测试用户"
    assert "高消费" in data["tags"]

    fetched = await svc.get_profile(
        platform_user_id="user_001",
        platform="taobao",
    )
    assert fetched["profile_id"] == data["profile_id"]


@pytest.mark.asyncio
async def test_update_existing_profile(db_session):
    """Test updating an existing profile's nickname."""
    from services.profile_service import ProfileService
    svc = ProfileService(db=db_session)

    await svc.update_profile(
        platform_user_id="user_001", platform="douyin", nickname="旧名称"
    )
    updated = await svc.update_profile(
        platform_user_id="user_001", platform="douyin", nickname="新名称"
    )
    assert updated["nickname"] == "新名称"


@pytest.mark.asyncio
async def test_track_event_updates_visit_count(db_session):
    """Test tracking an event increments visit_count."""
    from services.profile_service import ProfileService
    svc = ProfileService(db=db_session)

    await svc.update_profile(
        platform_user_id="user_001", platform="taobao"
    )
    await svc.track_event(
        platform_user_id="user_001",
        platform="taobao",
        event_type="view_product",
        live_room_id="room_001",
    )
    profile = await svc.get_profile(
        platform_user_id="user_001", platform="taobao"
    )
    assert profile["visit_count"] == 1


@pytest.mark.asyncio
async def test_track_purchase_updates_purchase_count(db_session):
    """Test tracking a purchase event increments purchase count."""
    from services.profile_service import ProfileService
    svc = ProfileService(db=db_session)

    await svc.update_profile(
        platform_user_id="user_001", platform="taobao"
    )
    await svc.track_event(
        platform_user_id="user_001",
        platform="taobao",
        event_type="purchase",
        properties={"amount_fen": "9900"},
    )
    profile = await svc.get_profile(
        platform_user_id="user_001", platform="taobao"
    )
    assert profile["purchase_count"] == 1
    assert profile["total_spent_fen"] == 9900


@pytest.mark.asyncio
async def test_get_segment(db_session):
    """Test getting a segment definition."""
    from models.profile import Segment
    from services.profile_service import ProfileService

    seg = Segment(
        segment_id="seg_001",
        store_id="store_001",
        name="高价值用户",
        rule_json='{"min_purchase_count": 3}',
        audience_size=150,
    )
    db_session.add(seg)
    await db_session.flush()

    svc = ProfileService(db=db_session)
    result = await svc.get_segment(segment_id="seg_001")
    assert result.name == "高价值用户"
    assert result.audience_size == 150
