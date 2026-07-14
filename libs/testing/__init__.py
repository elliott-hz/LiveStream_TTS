"""
Shared test utilities and fixtures.

Usage in service tests:
    from libs.testing import AsyncClient, fake_product, FakeDB
"""

import asyncio
from typing import Any, AsyncGenerator

import pytest_asyncio


@pytest_asyncio.fixture
async def async_db():
    """Provides an in-memory SQLite database for tests."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from libs.db import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ── Fake data generators ──

def fake_product(product_id: str = "prod_test_001", **overrides) -> dict[str, Any]:
    """Generate a fake product for tests."""
    return {
        "product_id": product_id,
        "store_id": "store_test",
        "title": "测试商品",
        "description": "用于测试的商品",
        "category_path": ["测试", "单元测试"],
        "attributes": {},
        "selling_points": ["卖点1", "卖点2"],
        "skus": [],
        "status": "active",
        **overrides,
    }


def fake_script(script_id: str = "script_test_001", **overrides) -> dict[str, Any]:
    """Generate a fake script for tests."""
    return {
        "script_id": script_id,
        "product_id": "prod_test_001",
        "version": 1,
        "status": "draft",
        "style": "激情带货",
        "sections": [
            {
                "section_id": "sec_001",
                "order": 1,
                "type": "opening",
                "text": "欢迎来到直播间！",
                "emotion": "excited",
            }
        ],
        **overrides,
    }


def fake_user(user_id: str = "user_test_001", **overrides) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "username": "test_user",
        "email": "test@example.com",
        "role": "merchant_admin",
        "store_id": "store_test",
        **overrides,
    }
