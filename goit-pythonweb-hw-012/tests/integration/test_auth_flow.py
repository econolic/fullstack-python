import pytest

from src.services.auth import create_email_token, create_refresh_token
from tests.conftest import create_test_user


def test_register_confirm_login_and_duplicate(client, monkeypatch):
    sent = []

    async def fake_send_email(email, username, host):
        sent.append((email, username, host))

    monkeypatch.setattr("src.api.auth.send_email", fake_send_email)
    payload = {
        "username": "agent",
        "email": "agent@example.com",
        "password": "password123",
    }

    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["role"] == "user"
    assert "hashed_password" not in data
    assert sent

    duplicate = client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409

    duplicate_username = client.post(
        "/api/auth/register",
        json={
            **payload,
            "email": "agent.alias@example.com",
        },
    )
    assert duplicate_username.status_code == 409

    denied = client.post(
        "/api/auth/login",
        data={"username": payload["username"], "password": payload["password"]},
    )
    assert denied.status_code == 401

    wrong_password = client.post(
        "/api/auth/login",
        data={"username": payload["username"], "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401

    token = create_email_token({"sub": payload["email"]})
    confirmed = client.get(f"/api/auth/confirmed_email/{token}")
    assert confirmed.status_code == 200
    assert confirmed.json()["message"] == "Email confirmed"

    already_confirmed = client.get(f"/api/auth/confirmed_email/{token}")
    assert already_confirmed.status_code == 200
    assert already_confirmed.json()["message"] == "Email is already confirmed"

    unknown_email_token = create_email_token({"sub": "missing@example.com"})
    unknown_email = client.get(f"/api/auth/confirmed_email/{unknown_email_token}")
    assert unknown_email.status_code == 400

    login = client.post(
        "/api/auth/login",
        data={"username": payload["username"], "password": payload["password"]},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert login.json()["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_rotation_and_logout(client):
    await create_test_user(username="rotator", email="rotator@example.com")
    login = client.post(
        "/api/auth/login",
        data={"username": "rotator", "password": "password123"},
    )
    refresh_token = login.json()["refresh_token"]

    rotated = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != refresh_token

    reused = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401

    logout = client.post("/api/auth/logout", json={"refresh_token": new_refresh})
    assert logout.status_code == 200
    after_logout = client.post("/api/auth/refresh", json={"refresh_token": new_refresh})
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_auth_auxiliary_error_branches(client, monkeypatch):
    confirmed = await create_test_user(
        username="confirmed", email="confirmed@example.com"
    )
    unconfirmed = await create_test_user(
        username="unconfirmed",
        email="unconfirmed@example.com",
        confirmed=False,
    )
    sent = []

    async def fake_send_email(email, username, host):
        sent.append((email, username, host))

    monkeypatch.setattr("src.api.auth.send_email", fake_send_email)

    missing_request = client.post(
        "/api/auth/request_email",
        json={"email": "missing@example.com"},
    )
    assert missing_request.status_code == 200
    assert missing_request.json()["message"] == "Check your email for confirmation"

    confirmed_request = client.post(
        "/api/auth/request_email",
        json={"email": confirmed.email},
    )
    assert confirmed_request.status_code == 200
    assert confirmed_request.json()["message"] == "Email is already confirmed"

    unconfirmed_request = client.post(
        "/api/auth/request_email",
        json={"email": unconfirmed.email},
    )
    assert unconfirmed_request.status_code == 200
    assert sent == [(unconfirmed.email, unconfirmed.username, "http://testserver/")]

    missing_reset = client.post(
        "/api/auth/password-reset/request",
        json={"email": "missing@example.com"},
    )
    assert missing_reset.status_code == 200

    token_without_subject, _, _ = await create_refresh_token({})
    invalid_refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": token_without_subject},
    )
    assert invalid_refresh.status_code == 401

    ghost_refresh, _, _ = await create_refresh_token({"sub": "ghost"})
    missing_refresh_record = client.post(
        "/api/auth/refresh",
        json={"refresh_token": ghost_refresh},
    )
    assert missing_refresh_record.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_flow(client, monkeypatch):
    await create_test_user(username="resetter", email="resetter@example.com")
    sent_tokens = []

    async def fake_send_password_reset_email(email, username, host, token):
        sent_tokens.append(token)

    monkeypatch.setattr(
        "src.api.auth.send_password_reset_email", fake_send_password_reset_email
    )

    request = client.post(
        "/api/auth/password-reset/request",
        json={"email": "resetter@example.com"},
    )
    assert request.status_code == 200
    assert sent_tokens

    confirm = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": sent_tokens[0], "new_password": "newpassword123"},
    )
    assert confirm.status_code == 200

    old_login = client.post(
        "/api/auth/login",
        data={"username": "resetter", "password": "password123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        data={"username": "resetter", "password": "newpassword123"},
    )
    assert new_login.status_code == 200

    reused = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": sent_tokens[0], "new_password": "anotherpass123"},
    )
    assert reused.status_code == 400
