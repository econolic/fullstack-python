import logging

import pytest

from src.services.auth import create_access_token
from tests.conftest import create_test_user


def contact_payload(
    email: str,
    first_name: str = "Ivan",
    last_name: str = "Petrenko",
) -> dict[str, str]:
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": "+380501112233",
        "birthday": "1998-05-20",
        "additional_data": "friend",
    }


@pytest.mark.asyncio
async def test_me_uses_cache(client, monkeypatch):
    user = await create_test_user(username="cached", email="cached@example.com")
    token = await create_access_token({"sub": user.username})
    calls = {"cache": 0}

    async def fake_get_cached_user(username):
        calls["cache"] += 1
        return user

    async def fake_cache_user(user):
        raise AssertionError("Database lookup should not happen on cache hit")

    monkeypatch.setattr("src.services.auth.get_cached_user", fake_get_cached_user)
    monkeypatch.setattr("src.services.auth.cache_user", fake_cache_user)

    response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "cached"
    assert calls["cache"] == 1


@pytest.mark.asyncio
async def test_contacts_require_token_and_are_user_scoped(client):
    user = await create_test_user(username="owner", email="owner@example.com")
    other = await create_test_user(username="other", email="other@example.com")
    owner_token = await create_access_token({"sub": user.username})
    other_token = await create_access_token({"sub": other.username})
    body = contact_payload("ivan@example.com")

    unauthorized = client.post("/api/contacts/", json=body)
    assert unauthorized.status_code == 401

    created = client.post(
        "/api/contacts/",
        json=body,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 201
    contact_id = created.json()["id"]

    visible = client.get(
        f"/api/contacts/{contact_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert visible.status_code == 200

    hidden = client.get(
        f"/api/contacts/{contact_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert hidden.status_code == 404


@pytest.mark.asyncio
async def test_contacts_full_router_workflow(client):
    user = await create_test_user(username="workflow", email="workflow@example.com")
    token = await create_access_token({"sub": user.username})
    headers = {"Authorization": f"Bearer {token}"}
    body = contact_payload("olena@example.com", "Olena", "Shevchenko")

    created = client.post("/api/contacts/", json=body, headers=headers)
    assert created.status_code == 201
    contact_id = created.json()["id"]

    duplicate = client.post("/api/contacts/", json=body, headers=headers)
    assert duplicate.status_code == 409

    listed = client.get("/api/contacts/?first_name=olen", headers=headers)
    assert listed.status_code == 200
    assert [contact["id"] for contact in listed.json()] == [contact_id]

    replaced_body = {
        **body,
        "first_name": "Maria",
        "email": "maria@example.com",
        "phone": "+380501112244",
    }
    replaced = client.put(
        f"/api/contacts/{contact_id}",
        json=replaced_body,
        headers=headers,
    )
    assert replaced.status_code == 200
    assert replaced.json()["first_name"] == "Maria"
    assert replaced.json()["email"] == "maria@example.com"

    patched = client.patch(
        f"/api/contacts/{contact_id}",
        json={"additional_data": "updated note"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["additional_data"] == "updated note"

    birthdays = client.get(
        "/api/contacts/upcoming-birthdays?days=365",
        headers=headers,
    )
    assert birthdays.status_code == 200
    assert any(contact["id"] == contact_id for contact in birthdays.json())

    deleted = client.delete(f"/api/contacts/{contact_id}", headers=headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/contacts/{contact_id}", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_contacts_missing_and_email_conflict_branches(client):
    user = await create_test_user(username="branches", email="branches@example.com")
    token = await create_access_token({"sub": user.username})
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/contacts/",
        json=contact_payload("first@example.com", "First", "Owner"),
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        "/api/contacts/",
        json=contact_payload("second@example.com", "Second", "Owner"),
        headers=headers,
    )
    assert second.status_code == 201

    missing_replace = client.put(
        "/api/contacts/9999",
        json=contact_payload("replace@example.com", "Missing", "Contact"),
        headers=headers,
    )
    assert missing_replace.status_code == 404

    missing_update = client.patch(
        "/api/contacts/9999",
        json={"first_name": "Missing"},
        headers=headers,
    )
    assert missing_update.status_code == 404

    missing_delete = client.delete("/api/contacts/9999", headers=headers)
    assert missing_delete.status_code == 404

    replace_conflict = client.put(
        f"/api/contacts/{first_id}",
        json=contact_payload("second@example.com", "First", "Conflict"),
        headers=headers,
    )
    assert replace_conflict.status_code == 409

    update_conflict = client.patch(
        f"/api/contacts/{first_id}",
        json={"email": "second@example.com"},
        headers=headers,
    )
    assert update_conflict.status_code == 409

    filtered = client.get(
        "/api/contacts/?last_name=owner&email=second",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [contact["email"] for contact in filtered.json()] == ["second@example.com"]


@pytest.mark.asyncio
async def test_avatar_requires_admin_role(client, monkeypatch):
    user = await create_test_user(username="regular", email="regular@example.com")
    admin = await create_test_user(
        username="admin",
        email="admin@example.com",
        role="admin",
    )
    user_token = await create_access_token({"sub": user.username})
    admin_token = await create_access_token({"sub": admin.username})

    files = {"file": ("avatar.jpg", b"image", "image/jpeg")}
    forbidden = client.patch(
        "/api/users/avatar",
        files=files,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden.status_code == 403

    monkeypatch.setattr(
        "src.api.users.UploadFileService.upload_file",
        lambda self, file, username: "https://res.cloudinary.com/demo/avatar.jpg",
    )
    updated = client.patch(
        "/api/users/avatar",
        files={"file": ("avatar.jpg", b"image", "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["avatar"].startswith("https://res.cloudinary.com/")


@pytest.mark.asyncio
async def test_cors_preflight_and_rate_limit(client, monkeypatch):
    slowapi_logger = logging.getLogger("slowapi")
    monkeypatch.setattr(slowapi_logger, "warning", lambda *args, **kwargs: None)

    user = await create_test_user(username="limited", email="limited@example.com")
    token = await create_access_token({"sub": user.username})

    cors = client.options(
        "/api/contacts/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert cors.status_code == 200

    statuses = [
        client.get(
            "/api/users/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        for _ in range(12)
    ]
    assert 429 in statuses
