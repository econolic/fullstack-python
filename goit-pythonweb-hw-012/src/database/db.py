"""Async database session management.

:class:`DatabaseSessionManager` wraps an async SQLAlchemy engine and
provides a context-manager based session factory used by FastAPI
dependency injection.
"""

import contextlib
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.conf.config import settings


class DatabaseSessionManager:
    """Manage an async SQLAlchemy engine and session factory."""

    def __init__(self, url: str):
        """Create an engine for the given database URL.

        :param url: An async-compatible database URL
            (e.g. ``postgresql+asyncpg://…``).
        :type url: str
        """
        self._engine: AsyncEngine | None = create_async_engine(url, echo=False)
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        """Dispose of the engine and release all connection-pool resources."""
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a new async session and handle rollback on error.

        :raises RuntimeError: If the engine has not been initialised.
        """
        if self._session_maker is None:
            raise RuntimeError("Database session factory is not initialized")
        session = self._session_maker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


sessionmanager = DatabaseSessionManager(settings.database_url)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with sessionmanager.session() as session:
        yield session
