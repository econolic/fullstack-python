from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import auth as auth_api
from src.conf.config import settings
from src.schemas import (
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RequestEmail,
    UserCreate,
)
from src.services.auth import Hash, create_email_token, utc_now


def test_is_expired_handles_naive_and_aware_datetimes() -> None:
    assert auth_api._is_expired(utc_now() - timedelta(seconds=1))
    assert auth_api._is_expired((utc_now() - timedelta(seconds=1)).replace(tzinfo=None))
    assert not auth_api._is_expired(utc_now() + timedelta(minutes=1))


def auth_user(
    username: str = "user",
    email: str = "user@example.com",
    confirmed: bool = True,
    user_id: int = 1,
) -> Any:
    return SimpleNamespace(
        id=user_id,
        username=username,
        email=email,
        hashed_password=Hash().get_password_hash("password123"),
        avatar=None,
        role="user",
        confirmed=confirmed,
        created_at=utc_now(),
    )


def request() -> Request:
    return cast(Request, SimpleNamespace(base_url="http://testserver/"))


def db_session() -> AsyncSession:
    return cast(AsyncSession, SimpleNamespace(rollback=AsyncMock()))


@pytest.mark.asyncio
async def test_register_user_direct_success_and_conflicts(monkeypatch) -> None:
    existing_email = auth_user(email="taken@example.com")
    existing_username = auth_user(username="taken")
    created_user = auth_user(username="new-user", email="new@example.com")

    class FakeUserService:
        def __init__(self, db) -> None:
            self.db = db

        async def get_user_by_email(self, email: str):
            return existing_email if email == existing_email.email else None

        async def get_user_by_username(self, username: str):
            return existing_username if username == existing_username.username else None

        async def create_user(self, user_data):
            if user_data.username == "integrity":
                raise IntegrityError("statement", "params", Exception("duplicate"))
            return created_user

    monkeypatch.setattr(auth_api, "UserService", FakeUserService)
    background_tasks = BackgroundTasks()
    db = db_session()

    response = await auth_api.register_user(
        UserCreate(
            username="new-user", email="new@example.com", password="password123"
        ),
        background_tasks,
        request(),
        db,
    )
    assert response.username == "new-user"
    assert len(background_tasks.tasks) == 1

    with pytest.raises(HTTPException) as email_exc:
        await auth_api.register_user(
            UserCreate(
                username="another",
                email="taken@example.com",
                password="password123",
            ),
            BackgroundTasks(),
            request(),
            db,
        )
    assert email_exc.value.status_code == 409

    with pytest.raises(HTTPException) as username_exc:
        await auth_api.register_user(
            UserCreate(
                username="taken", email="free@example.com", password="password123"
            ),
            BackgroundTasks(),
            request(),
            db,
        )
    assert username_exc.value.status_code == 409

    with pytest.raises(HTTPException) as integrity_exc:
        await auth_api.register_user(
            UserCreate(
                username="integrity",
                email="integrity@example.com",
                password="password123",
            ),
            BackgroundTasks(),
            request(),
            db,
        )
    assert integrity_exc.value.status_code == 409
    cast(Any, db).rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_refresh_and_logout_direct_branches(monkeypatch) -> None:
    users = {
        "active": auth_user("active", "active@example.com"),
        "unconfirmed": auth_user("unconfirmed", "unconfirmed@example.com", False),
    }
    refresh_records: dict[str, Any] = {}

    class FakeUserService:
        def __init__(self, db) -> None:
            self.db = db

        async def get_user_by_username(self, username: str):
            return users.get(username)

        async def create_refresh_token(self, user, jti: str, expires_at):
            refresh_records[jti] = SimpleNamespace(
                jti=jti,
                expires_at=expires_at,
                revoked_at=None,
                user=user,
                replaced_by_jti=None,
            )

        async def get_refresh_token_by_jti(self, jti: str):
            return refresh_records.get(jti)

        async def revoke_refresh_token(
            self,
            refresh_token,
            revoked_at,
            replaced_by_jti: str | None = None,
        ) -> None:
            refresh_token.revoked_at = revoked_at
            refresh_token.replaced_by_jti = replaced_by_jti

    monkeypatch.setattr(auth_api, "UserService", FakeUserService)
    db = db_session()

    with pytest.raises(HTTPException) as wrong_password:
        await auth_api.login_user(
            cast(
                OAuth2PasswordRequestForm,
                SimpleNamespace(username="active", password="wrong"),
            ),
            db,
        )
    assert wrong_password.value.status_code == 401

    with pytest.raises(HTTPException) as unconfirmed:
        await auth_api.login_user(
            cast(
                OAuth2PasswordRequestForm,
                SimpleNamespace(username="unconfirmed", password="password123"),
            ),
            db,
        )
    assert unconfirmed.value.status_code == 401

    tokens = await auth_api.login_user(
        cast(
            OAuth2PasswordRequestForm,
            SimpleNamespace(username="active", password="password123"),
        ),
        db,
    )
    assert tokens.access_token
    assert tokens.refresh_token

    rotated = await auth_api.refresh_tokens(
        RefreshTokenRequest(refresh_token=cast(str, tokens.refresh_token)),
        db,
    )
    assert rotated.refresh_token != tokens.refresh_token

    with pytest.raises(HTTPException) as reused_refresh:
        await auth_api.refresh_tokens(
            RefreshTokenRequest(refresh_token=cast(str, tokens.refresh_token)),
            db,
        )
    assert reused_refresh.value.status_code == 401

    await auth_api.logout_user(
        LogoutRequest(refresh_token=cast(str, rotated.refresh_token)),
        db,
    )
    with pytest.raises(HTTPException) as after_logout:
        await auth_api.refresh_tokens(
            RefreshTokenRequest(refresh_token=cast(str, rotated.refresh_token)),
            db,
        )
    assert after_logout.value.status_code == 401

    missing_subject, _, _ = await auth_api.create_refresh_token({})
    with pytest.raises(HTTPException) as missing_subject_exc:
        await auth_api.refresh_tokens(
            RefreshTokenRequest(refresh_token=missing_subject),
            db,
        )
    assert missing_subject_exc.value.status_code == 401

    missing_user_token, missing_user_jti, missing_user_exp = (
        await auth_api.create_refresh_token({"sub": "missing"})
    )
    refresh_records[missing_user_jti] = SimpleNamespace(
        jti=missing_user_jti,
        expires_at=missing_user_exp,
        revoked_at=None,
    )
    with pytest.raises(HTTPException) as missing_user_exc:
        await auth_api.refresh_tokens(
            RefreshTokenRequest(refresh_token=missing_user_token),
            db,
        )
    assert missing_user_exc.value.status_code == 401

    no_jti_token = jwt.encode(
        {
            "sub": "active",
            "exp": utc_now() + timedelta(minutes=5),
            "token_type": "refresh",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException) as logout_no_jti:
        await auth_api.logout_user(LogoutRequest(refresh_token=no_jti_token), db)
    assert logout_no_jti.value.status_code == 401


@pytest.mark.asyncio
async def test_email_confirmation_and_password_reset_direct_branches(
    monkeypatch,
) -> None:
    users_by_email = {
        "confirmed@example.com": auth_user(
            "confirmed",
            "confirmed@example.com",
            True,
            1,
        ),
        "pending@example.com": auth_user("pending", "pending@example.com", False, 2),
    }
    users_by_id = {user.id: user for user in users_by_email.values()}
    reset_token = SimpleNamespace(
        user_id=2,
        used_at=None,
        expires_at=utc_now() + timedelta(minutes=5),
    )
    background_tasks = BackgroundTasks()

    class FakeUserService:
        def __init__(self, db) -> None:
            self.db = db

        async def get_user_by_email(self, email: str):
            return users_by_email.get(email)

        async def confirmed_email(self, email: str) -> None:
            users_by_email[email].confirmed = True

        async def create_password_reset_token(self, user, token_hash, expires_at):
            reset_token.user_id = user.id
            reset_token.token_hash = token_hash
            reset_token.expires_at = expires_at

        async def get_password_reset_token(self, token_hash):
            return reset_token if token_hash == "valid-hash" else None

        async def get_user_by_id(self, user_id: int):
            return users_by_id.get(user_id)

        async def update_password(self, user, hashed_password: str) -> None:
            user.hashed_password = hashed_password

        async def mark_password_reset_token_used(self, token, used_at) -> None:
            token.used_at = used_at

    monkeypatch.setattr(auth_api, "UserService", FakeUserService)
    monkeypatch.setattr(auth_api, "invalidate_user_cache", AsyncMock())
    monkeypatch.setattr(auth_api, "hash_token", lambda token: f"{token}-hash")
    monkeypatch.setattr(auth_api, "create_password_reset_token", lambda: "raw-token")
    monkeypatch.setattr(auth_api, "send_email", AsyncMock())
    monkeypatch.setattr(auth_api, "send_password_reset_email", AsyncMock())
    db = db_session()

    confirmed_token = create_email_token({"sub": "confirmed@example.com"})
    already_confirmed = await auth_api.confirmed_email(confirmed_token, db)
    assert already_confirmed["message"] == "Email is already confirmed"

    pending_token = create_email_token({"sub": "pending@example.com"})
    confirmed = await auth_api.confirmed_email(pending_token, db)
    assert confirmed["message"] == "Email confirmed"

    missing_token = create_email_token({"sub": "missing@example.com"})
    with pytest.raises(HTTPException) as missing_email:
        await auth_api.confirmed_email(missing_token, db)
    assert missing_email.value.status_code == 400

    missing_request = await auth_api.request_email(
        RequestEmail(email="missing@example.com"),
        background_tasks,
        request(),
        db,
    )
    assert missing_request["message"] == "Check your email for confirmation"

    confirmed_request = await auth_api.request_email(
        RequestEmail(email="confirmed@example.com"),
        background_tasks,
        request(),
        db,
    )
    assert confirmed_request["message"] == "Email is already confirmed"

    users_by_email["pending@example.com"].confirmed = False
    pending_request = await auth_api.request_email(
        RequestEmail(email="pending@example.com"),
        background_tasks,
        request(),
        db,
    )
    assert pending_request["message"] == "Check your email for confirmation"

    missing_reset = await auth_api.request_password_reset(
        PasswordResetRequest(email="missing@example.com"),
        background_tasks,
        request(),
        db,
    )
    assert missing_reset["message"].startswith("If this email exists")

    existing_reset = await auth_api.request_password_reset(
        PasswordResetRequest(email="pending@example.com"),
        background_tasks,
        request(),
        db,
    )
    assert existing_reset["message"].startswith("If this email exists")

    with pytest.raises(HTTPException) as invalid_reset:
        await auth_api.confirm_password_reset(
            PasswordResetConfirm(token="missing", new_password="newpassword123"),
            db,
        )
    assert invalid_reset.value.status_code == 400

    reset_token.used_at = None
    reset_token.expires_at = utc_now() + timedelta(minutes=5)
    users_by_email["pending@example.com"].confirmed = True
    success = await auth_api.confirm_password_reset(
        PasswordResetConfirm(token="valid", new_password="newpassword123"),
        db,
    )
    assert success["message"] == "Password has been reset"

    reset_token.used_at = None
    reset_token.user_id = 404
    with pytest.raises(HTTPException) as missing_user:
        await auth_api.confirm_password_reset(
            PasswordResetConfirm(token="valid", new_password="newpassword123"),
            db,
        )
    assert missing_user.value.status_code == 400
