from io import BytesIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from cloudinary.exceptions import Error as CloudinaryError
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import utils as utils_api
from src.api.utils import healthchecker
from src.database.models import User
from src.services import cache as cache_service
from src.services.avatar import AvatarService
from src.services.auth import utc_now
from src.services.cache import (
    cache_user,
    close_cache,
    deserialize_user,
    get_cached_user,
    invalidate_user_cache,
    serialize_user,
    user_cache_key,
)
from src.services.upload_file import UploadFileError, UploadFileService


class FakeRedis:
    def __init__(self):
        self.storage = {}
        self.deleted = []
        self.closed = False

    async def get(self, key):
        return self.storage.get(key)

    async def setex(self, key, ttl, value):
        self.storage[key] = value

    async def delete(self, key):
        self.deleted.append(key)
        self.storage.pop(key, None)

    async def aclose(self):
        self.closed = True


def test_cache_user_serialization_roundtrip():
    user = User(
        id=7,
        username="cached",
        email="cached@example.com",
        avatar="https://example.com/avatar.jpg",
        confirmed=True,
        role="admin",
        created_at=utc_now(),
    )

    payload = serialize_user(user)
    restored = deserialize_user(payload)

    assert user_cache_key(user.username) == "user:cached"
    assert restored.id == user.id
    assert restored.username == user.username
    assert restored.role == "admin"
    assert restored.hashed_password is None


@pytest.mark.asyncio
async def test_cache_user_lifecycle(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", fake_redis)

    user = User(
        id=1,
        username="cache-hit",
        email="cache-hit@example.com",
        confirmed=True,
        role="user",
        created_at=utc_now(),
    )

    await cache_user(user)
    cached = await get_cached_user(user.username)
    assert cached is not None
    assert cached.email == user.email

    await invalidate_user_cache(user.username)
    assert await get_cached_user(user.username) is None

    await close_cache()
    assert fake_redis.closed is True


@pytest.mark.asyncio
async def test_invalid_cached_user_payload_is_evicted(monkeypatch):
    fake_redis = FakeRedis()
    fake_redis.storage["user:broken"] = "{not-json"
    monkeypatch.setattr(cache_service, "redis_client", fake_redis)
    warning = MagicMock()
    monkeypatch.setattr(cache_service.logger, "warning", warning)

    assert await get_cached_user("broken") is None
    assert fake_redis.deleted == ["user:broken"]
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_healthchecker_success_and_failure(monkeypatch):
    class SuccessDb:
        async def execute(self, statement):
            return SimpleNamespace(scalar_one_or_none=lambda: 1)

    class FailingDb:
        async def execute(self, statement):
            raise RuntimeError("database down")

    assert await healthchecker(cast(AsyncSession, SuccessDb())) == {
        "message": "Contacts API is healthy"
    }
    log_exception = MagicMock()
    monkeypatch.setattr(utils_api.logger, "exception", log_exception)
    with pytest.raises(HTTPException) as exc:
        await healthchecker(cast(AsyncSession, FailingDb()))
    assert exc.value.status_code == 500
    log_exception.assert_called_once_with("Healthcheck failed")


def test_upload_file_success_and_error(monkeypatch):
    uploaded = {}

    def fake_upload(file, public_id, overwrite):
        uploaded["public_id"] = public_id
        uploaded["overwrite"] = overwrite
        return {"version": 42}

    class FakeCloudinaryImage:
        def __init__(self, public_id):
            self.public_id = public_id

        def build_url(self, **kwargs):
            assert self.public_id == "ContactsAPI/admin"
            assert kwargs["version"] == 42
            return "https://res.cloudinary.com/demo/avatar.jpg"

    monkeypatch.setattr("cloudinary.uploader.upload", fake_upload)
    monkeypatch.setattr("cloudinary.CloudinaryImage", FakeCloudinaryImage)

    file = cast(UploadFile, SimpleNamespace(file=BytesIO(b"image")))
    assert UploadFileService.upload_file(file, "admin").endswith("/avatar.jpg")
    assert uploaded == {"public_id": "ContactsAPI/admin", "overwrite": True}

    def fail_upload(file, public_id, overwrite):
        raise CloudinaryError("broken")

    monkeypatch.setattr("cloudinary.uploader.upload", fail_upload)
    with pytest.raises(UploadFileError):
        UploadFileService.upload_file(file, "admin")


def test_avatar_service_returns_none_when_gravatar_lookup_fails(monkeypatch):
    class BrokenGravatar:
        def __init__(self, email):
            self.email = email

        def get_image(self):
            raise RuntimeError("lookup failed")

    monkeypatch.setattr("src.services.avatar.Gravatar", BrokenGravatar)

    assert AvatarService().get_default_avatar("user@example.com") is None
