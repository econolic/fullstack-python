import pytest
from fastapi import HTTPException

from src.services.auth import (
    Hash,
    TokenService,
    create_access_token,
    create_password_reset_token,
    decode_token,
    hash_token,
)


def test_password_hash_and_verify():
    hashed = Hash().get_password_hash("password123")
    assert hashed != "password123"
    assert Hash().verify_password("password123", hashed)
    assert not Hash().verify_password("wrong", hashed)


def test_password_reset_token_hash_is_stable_and_not_plaintext():
    token = create_password_reset_token()
    token_hash = hash_token(token)
    assert token_hash == hash_token(token)
    assert token_hash != token
    assert len(token_hash) == 64


@pytest.mark.asyncio
async def test_token_type_validation():
    access = await create_access_token({"sub": "user"})
    assert decode_token(access, "access")["sub"] == "user"
    with pytest.raises(HTTPException):
        decode_token(access, "refresh")


@pytest.mark.asyncio
async def test_token_service_issues_typed_tokens():
    service = TokenService()

    access = await service.create_access_token({"sub": "user"})
    refresh, jti, expires_at = await service.create_refresh_token({"sub": "user"})
    email = service.create_email_token({"sub": "user@example.com"})

    assert service.decode_token(access, "access")["token_type"] == "access"
    refresh_payload = service.decode_token(refresh, "refresh")
    assert refresh_payload["token_type"] == "refresh"
    assert refresh_payload["jti"] == jti
    assert expires_at is not None
    assert service.decode_token(email, "email_verification")["sub"] == (
        "user@example.com"
    )


def test_token_service_password_reset_token_is_hashed():
    service = TokenService()
    token = service.create_password_reset_token()
    token_hash = service.hash_token(token)

    assert token_hash == service.hash_token(token)
    assert token_hash != token
    assert len(token_hash) == 64
