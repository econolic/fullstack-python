from __future__ import annotations

import pytest

from src.services.auth import create_access_token
from src.services.upload_file import UploadFileError
from tests.conftest import create_test_user


@pytest.mark.asyncio
async def test_update_avatar_user_success(client, monkeypatch):
    admin = await create_test_user(
        username="admin", email="admin@example.com", role="admin"
    )
    token = await create_access_token({"sub": admin.username})
    uploaded_url = "https://res.cloudinary.com/demo/avatar.jpg"
    invalidated = []

    def fake_upload(self, file, username):
        return uploaded_url

    async def fake_update_avatar(self, email, url):
        admin.avatar = url
        return admin

    async def fake_invalidate_user_cache(username):
        invalidated.append(username)

    monkeypatch.setattr("src.api.users.UploadFileService.upload_file", fake_upload)
    monkeypatch.setattr(
        "src.api.users.UserService.update_avatar_url", fake_update_avatar
    )
    monkeypatch.setattr(
        "src.api.users.invalidate_user_cache", fake_invalidate_user_cache
    )

    response = client.patch(
        "/api/users/avatar",
        files={"file": ("avatar.jpg", b"image", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["avatar"] == uploaded_url
    assert invalidated == [admin.username]


@pytest.mark.asyncio
async def test_update_avatar_user_upload_failure(client, monkeypatch):
    admin = await create_test_user(
        username="admin", email="admin@example.com", role="admin"
    )
    token = await create_access_token({"sub": admin.username})

    def fake_upload(self, file, username):
        raise UploadFileError("service unavailable")

    monkeypatch.setattr("src.api.users.UploadFileService.upload_file", fake_upload)

    response = client.patch(
        "/api/users/avatar",
        files={"file": ("avatar.jpg", b"image", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Avatar upload service is unavailable"


@pytest.mark.asyncio
async def test_update_avatar_user_not_found(client, monkeypatch):
    admin = await create_test_user(
        username="admin", email="admin@example.com", role="admin"
    )
    token = await create_access_token({"sub": admin.username})

    def fake_upload(self, file, username):
        return "https://res.cloudinary.com/demo/avatar.jpg"

    async def fake_update_avatar(self, email, url):
        return None

    monkeypatch.setattr("src.api.users.UploadFileService.upload_file", fake_upload)
    monkeypatch.setattr(
        "src.api.users.UserService.update_avatar_url", fake_update_avatar
    )

    response = client.patch(
        "/api/users/avatar",
        files={"file": ("avatar.jpg", b"image", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
