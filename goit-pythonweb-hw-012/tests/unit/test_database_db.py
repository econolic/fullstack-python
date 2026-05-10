import contextlib
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import db as db_module
from src.database.db import DatabaseSessionManager


@pytest.mark.asyncio
async def test_database_session_manager_session_success_and_rollback() -> None:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

    async with manager.session() as session:
        assert session is not None

    with pytest.raises(RuntimeError, match="boom"):
        async with manager.session():
            raise RuntimeError("boom")

    await manager.close()
    await manager.close()


@pytest.mark.asyncio
async def test_database_session_manager_requires_session_factory() -> None:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    setattr(manager, "_session_maker", None)

    with pytest.raises(RuntimeError, match="session factory"):
        async with manager.session():
            pass

    await manager.close()


@pytest.mark.asyncio
async def test_get_db_yields_session_from_global_manager(monkeypatch) -> None:
    expected_session = object()

    class FakeSessionManager:
        @contextlib.asynccontextmanager
        async def session(self):
            yield expected_session

    monkeypatch.setattr(db_module, "sessionmanager", FakeSessionManager())

    generator = db_module.get_db()
    session = await anext(generator)
    assert session is cast(AsyncSession, expected_session)

    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_database_session_manager_initializes_engine() -> None:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

    assert cast(Any, manager)._engine is not None
    assert cast(Any, manager)._session_maker is not None
    await manager.close()
