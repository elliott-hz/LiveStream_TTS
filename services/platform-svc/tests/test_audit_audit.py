"""
Tests for audit-svc: pre-flight checks, live monitoring, post-session archive.
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
from models.audit import AuditResult, AuditLog

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
async def test_audit_avatar_approved(db_session):
    """Test avatar audit approves a normal avatar."""
    from services.platform_svc.src.modules.audit.services.audit_service import AuditService
    svc = AuditService(db=db_session)

    result = await svc.audit_avatar(
        avatar_id="av_001",
        celebrity_check=None,
    )
    assert result["verdict"] == "approved"
    assert len(result["violations"]) == 0


@pytest.mark.asyncio
async def test_audit_avatar_celebrity_check(db_session):
    """Test avatar audit flags celebrity likeness."""
    from services.platform_svc.src.modules.audit.services.audit_service import AuditService
    svc = AuditService(db=db_session)

    result = await svc.audit_avatar(
        avatar_id="av_002",
        celebrity_check="Jackie Chan",
    )
    assert result["verdict"] == "manual_review"
    assert len(result["violations"]) == 1
    assert result["violations"][0]["category"] == "celebrity_ip"


@pytest.mark.asyncio
async def test_audit_script_approved(db_session):
    """Test script audit approves clean content."""
    from services.platform_svc.src.modules.audit.services.audit_service import AuditService
    svc = AuditService(db=db_session)

    result = await svc.audit_script(
        script_id="sc_001",
        full_text="欢迎来到直播间，今天给大家带来一款优质产品。",
    )
    assert result["verdict"] == "approved"


@pytest.mark.asyncio
async def test_audit_script_banned_keywords(db_session):
    """Test script audit rejects banned content."""
    from services.platform_svc.src.modules.audit.services.audit_service import AuditService
    svc = AuditService(db=db_session)

    result = await svc.audit_script(
        script_id="sc_002",
        full_text="快来参与赌博，保证你赢钱！",
    )
    assert result["verdict"] == "rejected"
    assert len(result["violations"]) >= 1


@pytest.mark.asyncio
async def test_submit_screenshot(db_session):
    """Test submitting a screenshot for moderation."""
    from services.platform_svc.src.modules.audit.services.audit_service import AuditService
    svc = AuditService(db=db_session)

    result = await svc.submit_screenshot(
        live_room_id="room_001",
        timestamp=1000,
    )
    assert result["verdict"] == "approved"
    assert result["target_type"] == "screenshot"


@pytest.mark.asyncio
async def test_report_violation(db_session):
    """Test reporting a live violation."""
    from services.platform_svc.src.modules.audit.services.audit_service import AuditService
    svc = AuditService(db=db_session)

    result = await svc.report_violation(
        live_room_id="room_001",
        violation_type="inappropriate_content",
        description="Broadcasting prohibited items",
    )
    assert result["verdict"] == "manual_review"
    assert len(result["violations"]) == 1
    assert result["violations"][0]["category"] == "inappropriate_content"
