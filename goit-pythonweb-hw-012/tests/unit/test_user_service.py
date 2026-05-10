from unittest.mock import AsyncMock, MagicMock
from typing import cast

import pytest

from src.database.models import User
from src.repository.users import UserRepository
from src.schemas import UserCreate
from src.services.avatar import AvatarService
from src.services.users import UserService


class FakeUserRepository:
    def __init__(self):
        self.created = None

    async def create_user(self, body, avatar=None, role="user"):
        self.created = {"body": body, "avatar": avatar, "role": role}
        return User(
            id=1,
            username=body.username,
            email=str(body.email),
            hashed_password=body.password,
            avatar=avatar,
            role=role,
        )


class FakeAvatarService:
    def __init__(self, avatar):
        self.avatar = avatar
        self.emails = []

    def get_default_avatar(self, email):
        self.emails.append(email)
        return self.avatar


class FailingAvatarService:
    def get_default_avatar(self, email):
        return None


@pytest.mark.asyncio
async def test_user_service_accepts_repository_and_avatar_provider():
    repository = FakeUserRepository()
    avatar_service = FakeAvatarService("https://example.com/avatar.jpg")
    service = UserService(
        repository=cast(UserRepository, repository),
        avatar_service=cast(AvatarService, avatar_service),
    )
    body = UserCreate(
        username="solid",
        email="solid@example.com",
        password="hashed-password",
    )

    user = await service.create_user(body, role="admin")

    assert avatar_service.emails == ["solid@example.com"]
    assert repository.created is not None
    assert repository.created["avatar"] == "https://example.com/avatar.jpg"
    assert repository.created["role"] == "admin"
    assert user.avatar == "https://example.com/avatar.jpg"
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_user_service_keeps_create_user_when_avatar_lookup_fails():
    repository = FakeUserRepository()
    service = UserService(
        repository=cast(UserRepository, repository),
        avatar_service=cast(AvatarService, FailingAvatarService()),
    )
    body = UserCreate(
        username="fallback",
        email="fallback@example.com",
        password="hashed-password",
    )

    user = await service.create_user(body)

    assert repository.created is not None
    assert repository.created["avatar"] is None
    assert user.avatar is None
    assert user.role == "user"


@pytest.mark.asyncio
async def test_user_service_create_user_with_async_mock_repository():
    body = UserCreate(
        username="mocked",
        email="mocked@example.com",
        password="hashed-password",
    )
    expected_user = User(
        id=10,
        username=body.username,
        email=str(body.email),
        hashed_password=body.password,
        avatar="https://example.com/mocked.jpg",
        role="admin",
    )
    repository = MagicMock()
    repository.create_user = AsyncMock(return_value=expected_user)
    avatar_service = MagicMock()
    avatar_service.get_default_avatar.return_value = expected_user.avatar
    service = UserService(repository=repository, avatar_service=avatar_service)

    user = await service.create_user(body, role="admin")

    assert user is expected_user
    avatar_service.get_default_avatar.assert_called_once_with("mocked@example.com")
    repository.create_user.assert_awaited_once_with(
        body,
        "https://example.com/mocked.jpg",
        "admin",
    )


def test_user_service_requires_session_or_repository():
    with pytest.raises(ValueError):
        UserService()
