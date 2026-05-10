import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL is None:
    test_db_path = Path(__file__).resolve().parents[1] / ".pytest_cache" / "test.db"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm", "-journal"):
        stale_db_file = Path(f"{test_db_path}{suffix}")
        if stale_db_file.exists():
            stale_db_file.unlink()
    TEST_DATABASE_URL = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("MAIL_USERNAME", "test@example.com")
os.environ.setdefault("MAIL_PASSWORD", "password")
os.environ.setdefault("MAIL_FROM", "test@example.com")
os.environ.setdefault("MAIL_SERVER", "smtp.example.com")
os.environ.setdefault("CLD_NAME", "cloud")
os.environ.setdefault("CLD_API_KEY", "key")
os.environ.setdefault("CLD_API_SECRET", "secret")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_SECONDS", "3600")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_SECONDS", "604800")
os.environ.setdefault("PASSWORD_RESET_TOKEN_EXPIRE_SECONDS", "3600")
os.environ.setdefault("USER_CACHE_TTL_SECONDS", "900")

from main import app
from src.database.db import get_db
from src.database.models import Base, User, UserRole
from src.services.auth import Hash

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def override_get_db() -> AsyncIterator[AsyncSession]:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def reset_database() -> Iterator[None]:
    async def _reset() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    yield


@pytest.fixture(autouse=True)
def disable_external_cache(monkeypatch) -> Iterator[None]:
    async def fake_get_cached_user(username):
        return None

    async def fake_cache_user(user):
        return None

    async def fake_invalidate_user_cache(username):
        return None

    async def fake_close_cache():
        return None

    async def fake_close_database():
        return None

    monkeypatch.setattr("src.services.auth.get_cached_user", fake_get_cached_user)
    monkeypatch.setattr("src.services.auth.cache_user", fake_cache_user)
    monkeypatch.setattr(
        "src.api.auth.invalidate_user_cache", fake_invalidate_user_cache
    )
    monkeypatch.setattr(
        "src.api.users.invalidate_user_cache", fake_invalidate_user_cache
    )
    monkeypatch.setattr("main.close_cache", fake_close_cache)
    monkeypatch.setattr("main.sessionmanager.close", fake_close_database)
    yield


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def create_test_user(
    username: str = "user",
    email: str = "user@example.com",
    password: str = "password123",
    confirmed: bool = True,
    role: str = UserRole.USER.value,
) -> User:
    async with TestingSessionLocal() as session:
        user = User(
            username=username,
            email=email,
            hashed_password=Hash().get_password_hash(password),
            confirmed=confirmed,
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
