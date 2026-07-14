"""Shared test fixtures for user-svc tests.

Provides an in-memory SQLite database, test config, and pre-built
service instances for all test modules.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.db import Base


class TestConfig:
    """Minimal config override for tests.

    Uses a fixed JWT secret so tokens are deterministic within a test run.
    """

    def __init__(self) -> None:
        self.env = "test"

    @property
    def jwt_secret(self) -> str:
        return "test-secret-key-012345678901234567"  # 32+ chars to avoid PyJWT warnings

    @property
    def jwt_algorithm(self) -> str:
        return "HS256"

    @property
    def access_token_expire_minutes(self) -> int:
        return 15

    @property
    def refresh_token_expire_days(self) -> int:
        return 7

    @property
    def grpc_port(self) -> int:
        return 0

    @property
    def http_port(self) -> int:
        return 0


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
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite database with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
def test_config() -> TestConfig:
    return TestConfig()


@pytest_asyncio.fixture
def db_factory(db_session: AsyncSession) -> SessionFactory:
    """Return a factory that yields the shared test session."""
    return SessionFactory(db_session)
