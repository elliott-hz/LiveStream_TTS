"""Shared test fixtures for live-mgr-svc tests.

Provides an in-memory SQLite database, test config, and reusable
service instances for all test modules.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.db import Base


class SessionFactory:
    """Callable that returns a pre-created AsyncSession.

    Matches the ``Database.session`` interface used by service classes:
    ``factory()`` returns an ``AsyncSession`` synchronously.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> AsyncSession:
        return self._session


@pytest_asyncio.fixture
async def async_db() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite database with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
def db_factory(async_db: AsyncSession) -> SessionFactory:
    """Return a factory that yields the shared test session."""
    return SessionFactory(async_db)
