"""
Shared test fixtures for knowledge-svc tests.

Sets up the Python path and creates an in-memory SQLite database.
"""

import sys
from pathlib import Path

# Add repo root + src + modules to sys.path for test imports
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
_MODULES_DIR = str(Path(__file__).resolve().parent.parent / "modules")

for _p in (_REPO_ROOT, _SRC_DIR, _MODULES_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.db import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()
