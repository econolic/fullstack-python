import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User, UserRole
from src.services.cache import cache_user, get_cached_user
from src.services.users import UserService


class Hash:
    """Bcrypt password hashing helper."""

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Check a plain-text password against a bcrypt hash.

        :param plain_password: The candidate password.
        :type plain_password: str
        :param hashed_password: The stored bcrypt hash.
        :type hashed_password: str
        :returns: ``True`` when the password matches.
        :rtype: bool
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Return a bcrypt hash of *password*.

        :param password: The plain-text password to hash.
        :type password: str
        :returns: A bcrypt hash string.
        :rtype: str
        """
        return self.pwd_context.hash(password)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class TokenService:
    """JWT and one-time token helper.

    Centralises all token creation and validation logic so that
    callers do not need to interact with ``python-jose`` directly.
    """

    async def create_access_token(
        self, data: dict, expires_delta: Optional[int] = None
    ) -> str:
        """Create a JWT access token for API authorisation.

        :param data: Claims to embed (must include ``sub``).
        :type data: dict
        :param expires_delta: Lifetime in seconds; defaults to
            ``settings.access_token_expire_seconds``.
        :type expires_delta: int | None
        :returns: An encoded JWT string.
        :rtype: str
        """
        to_encode = data.copy()
        expires_in = expires_delta or settings.access_token_expire_seconds
        expire = utc_now() + timedelta(seconds=expires_in)
        to_encode.update({"exp": expire, "token_type": "access"})
        return jwt.encode(
            to_encode,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

    async def create_refresh_token(self, data: dict) -> tuple[str, str, datetime]:
        """Create a JWT refresh token.

        :param data: Claims to embed (must include ``sub``).
        :type data: dict
        :returns: A 3-tuple of *(encoded token, jti, expiry datetime)*.
        :rtype: tuple[str, str, datetime]
        """
        jti = uuid4().hex
        expire = utc_now() + timedelta(seconds=settings.refresh_token_expire_seconds)
        to_encode = data.copy()
        to_encode.update({"exp": expire, "jti": jti, "token_type": "refresh"})
        token = jwt.encode(
            to_encode,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        return token, jti, expire

    def decode_token(self, token: str, expected_type: str) -> dict:
        """Decode a JWT and validate its ``token_type`` claim.

        :param token: The encoded JWT string.
        :type token: str
        :param expected_type: Required value of the ``token_type`` claim
            (e.g. ``"access"``, ``"refresh"``, ``"email_verification"``).
        :type expected_type: str
        :returns: The decoded payload dictionary.
        :rtype: dict
        :raises HTTPException: ``401`` if the token is invalid or the
            ``token_type`` does not match *expected_type*.
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if payload.get("token_type") != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    def create_email_token(self, data: dict) -> str:
        """Create a short-lived JWT for email-address verification.

        :param data: Claims to embed (should include ``sub`` = email).
        :type data: dict
        :returns: An encoded JWT string valid for 7 days.
        :rtype: str
        """
        to_encode = data.copy()
        expire = utc_now() + timedelta(days=7)
        to_encode.update(
            {"iat": utc_now(), "exp": expire, "token_type": "email_verification"}
        )
        return jwt.encode(
            to_encode,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

    def create_password_reset_token(self) -> str:
        """Generate a cryptographically random URL-safe password-reset token.

        :returns: A 32-byte URL-safe random string.
        :rtype: str
        """
        return secrets.token_urlsafe(32)

    def hash_token(self, token: str) -> str:
        """Return a SHA-256 hex digest of *token* for safe database storage.

        :param token: The raw token string.
        :type token: str
        :returns: A 64-character hex digest.
        :rtype: str
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


token_service = TokenService()


async def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Module-level shortcut for :meth:`TokenService.create_access_token`."""
    return await token_service.create_access_token(data, expires_delta)


async def create_refresh_token(data: dict) -> tuple[str, str, datetime]:
    """Module-level shortcut for :meth:`TokenService.create_refresh_token`."""
    return await token_service.create_refresh_token(data)


def decode_token(token: str, expected_type: str) -> dict:
    """Module-level shortcut for :meth:`TokenService.decode_token`."""
    return token_service.decode_token(token, expected_type)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that returns the authenticated user.

    The user is first looked up in the Redis cache.  On a cache miss
    the database is queried and the result is written back to cache.

    :param token: Bearer JWT extracted by OAuth2 scheme.
    :type token: str
    :param db: Database session injected by FastAPI.
    :type db: AsyncSession
    :returns: The authenticated user instance.
    :rtype: User
    :raises HTTPException: ``401`` if the token is invalid or the user
        does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token, "access")
    username: str | None = payload.get("sub")
    if username is None:
        raise credentials_exception

    cached_user = await get_cached_user(username)
    if cached_user is not None:
        return cached_user

    user = await UserService(db).get_user_by_username(username)
    if user is None:
        raise credentials_exception
    await cache_user(user)
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to administrators.

    :param user: The authenticated user (injected via :func:`get_current_user`).
    :type user: User
    :returns: The same user, if they have the ``admin`` role.
    :rtype: User
    :raises HTTPException: ``403`` if the user is not an admin.
    """
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action",
        )
    return user


def create_email_token(data: dict) -> str:
    """Module-level shortcut for :meth:`TokenService.create_email_token`."""
    return token_service.create_email_token(data)


async def get_email_from_token(token: str) -> str:
    """Extract an email address from an email-verification JWT.

    :param token: The encoded email-verification token.
    :type token: str
    :returns: The email address stored in the ``sub`` claim.
    :rtype: str
    :raises HTTPException: ``422`` if the token is invalid.
    """
    try:
        payload = decode_token(token, "email_verification")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email verification token",
        )
    email: str | None = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email verification token",
        )
    return email


def create_password_reset_token() -> str:
    """Module-level shortcut for :meth:`TokenService.create_password_reset_token`."""
    return token_service.create_password_reset_token()


def hash_token(token: str) -> str:
    """Module-level shortcut for :meth:`TokenService.hash_token`."""
    return token_service.hash_token(token)
