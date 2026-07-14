"""
Tests for platform-sync-svc: binding, sync, and adapters.

Uses in-memory SQLite for DB tests.
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
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.db import Base
from models.platform import PlatformStoreBinding, SyncJob
from adapters.taobao import TaobaoAdapter
from adapters.douyin import DouyinAdapter


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
async def test_binding_create_and_list(db_session):
    """Test creating a binding and listing it."""
    from services.binding_service import BindingService
    svc = BindingService(db=db_session)

    binding = await svc.bind_store(
        store_id="store_001",
        platform="taobao",
        auth_code="auth_test_code_1234",
    )
    assert binding.binding_id is not None
    assert binding.platform == "taobao"
    assert binding.status == "active"

    bindings = await svc.list_bindings(store_id="store_001")
    assert len(bindings) == 1
    assert bindings[0].binding_id == binding.binding_id


@pytest.mark.asyncio
async def test_binding_unbind(db_session):
    """Test unbinding (revoking) a store."""
    from services.binding_service import BindingService
    svc = BindingService(db=db_session)

    binding = await svc.bind_store(
        store_id="store_001",
        platform="douyin",
        auth_code="auth_dy_5678",
    )
    await svc.unbind_store(binding.binding_id)

    bindings = await svc.list_bindings(store_id="store_001")
    assert len(bindings) == 1
    assert bindings[0].status == "revoked"


@pytest.mark.asyncio
async def test_sync_product_push(db_session):
    """Test creating and executing a sync job (push)."""
    from services.sync_service import SyncService
    svc = SyncService(db=db_session)

    job = await svc.sync_product(
        product_id="prod_001",
        platform="taobao",
        direction="push",
    )
    assert job.job_id is not None
    assert job.product_id == "prod_001"
    assert job.platform == "taobao"
    assert job.status in ("success", "failed")
    if job.status == "success":
        assert job.platform_product_id != ""


@pytest.mark.asyncio
async def test_sync_product_pull(db_session):
    """Test sync product pull."""
    from services.sync_service import SyncService
    svc = SyncService(db=db_session)

    job = await svc.sync_product(
        product_id="prod_002",
        platform="douyin",
        direction="pull",
    )
    assert job.job_id is not None
    assert job.direction == "pull"
    assert job.status == "success"


@pytest.mark.asyncio
async def test_bulk_sync(db_session):
    """Test bulk sync across multiple platforms."""
    from services.sync_service import SyncService
    svc = SyncService(db=db_session)

    jobs = await svc.bulk_sync(
        product_ids=["prod_001", "prod_002"],
        platforms=["taobao", "douyin"],
    )
    assert len(jobs) == 4  # 2 products * 2 platforms


@pytest.mark.asyncio
async def test_tb_adapter_push():
    """Test Taobao adapter push product."""
    adapter = TaobaoAdapter()
    result = await adapter.push_product(
        {"product_id": "p1", "title": "Test"},
        "mock_token",
    )
    assert "platform_product_id" in result
    assert result["platform_product_id"].startswith("tb_")


@pytest.mark.asyncio
async def test_dy_adapter_push():
    """Test Douyin adapter push product."""
    adapter = DouyinAdapter()
    result = await adapter.push_product(
        {"product_id": "p2", "title": "Test DY"},
        "mock_token",
    )
    assert "platform_product_id" in result
    assert result["platform_product_id"].startswith("dy_")
