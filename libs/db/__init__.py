"""
Database client factory for PostgreSQL + SQLAlchemy (async).

All services use this single entry point to create DB connections.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from libs.common.config import ServiceConfig


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class Database:
    """Async database connection manager.

    Usage:
        db = Database(ServiceConfig("user-svc"))
        await db.connect()
        async with db.session() as session:
            ...
    """

    def __init__(self, config: ServiceConfig):
        self.config = config
        self._engine = None
        self._session_factory = None

    @property
    def dsn(self) -> str:
        host = self.config.get("DB_HOST", "localhost")
        port = self.config.get("DB_PORT", 5432)
        name = self.config.get("DB_NAME", "livestream_tts")
        user = self.config.get("DB_USER", "livestream")
        password = self.config.get("DB_PASSWORD", "livestream_dev")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    async def connect(self) -> None:
        pool_size = self.config.get_int("DB_POOL_SIZE", 10)
        self._engine = create_async_engine(
            self.dsn,
            pool_size=pool_size,
            max_overflow=20,
            echo=self.config.env == "dev",
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()

    def session(self) -> AsyncSession:
        if not self._session_factory:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._session_factory()

    async def health_check(self) -> bool:
        """Return True if DB is reachable."""
        try:
            async with self.session() as session:
                await session.execute(Base.metadata.tables.values())  # light query
            return True
        except Exception:
            return False
