"""Redis caching layer for authenticated user data.

The cache stores a JSON-serialised subset of
:class:`~src.database.models.User` fields (excluding the password hash)
under the key ``user:{username}`` with a configurable TTL.
"""

import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.conf.config import settings
from src.database.models import User

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def user_cache_key(username: str) -> str:
    """Build the Redis key for an authenticated user.

    :param username: The user's unique login name.
    :type username: str
    :returns: A namespaced key string, e.g. ``user:admin``.
    :rtype: str
    """
    return f"user:{username}"


def serialize_user(user: User) -> dict[str, Any]:
    """Convert a :class:`User` to a JSON-safe dictionary.

    Sensitive fields (e.g. ``hashed_password``) are intentionally
    excluded.

    :param user: The user instance to serialise.
    :type user: User
    :returns: A dictionary safe for Redis storage.
    :rtype: dict[str, Any]
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar": user.avatar,
        "confirmed": user.confirmed,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def deserialize_user(data: dict[str, Any]) -> User:
    """Recreate a lightweight :class:`User` from cached data.

    The returned instance is detached from any database session and
    should only be used for read-only attribute access.

    :param data: A dictionary previously produced by :func:`serialize_user`.
    :type data: dict[str, Any]
    :returns: A reconstructed user.
    :rtype: User
    """
    created_at = data.get("created_at")
    return User(
        id=data["id"],
        username=data["username"],
        email=data["email"],
        avatar=data.get("avatar"),
        confirmed=bool(data.get("confirmed")),
        role=data.get("role", "user"),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
    )


async def get_cached_user(username: str) -> User | None:
    """Read a user from the Redis cache.

    Returns ``None`` on a cache miss **or** if the cached payload is
    corrupt (in which case the bad entry is evicted automatically).

    :param username: The user's login name.
    :type username: str
    :returns: The cached user or ``None``.
    :rtype: User | None
    """
    try:
        cached = await redis_client.get(user_cache_key(username))
    except RedisError as err:
        logger.warning("Redis user cache read failed: %s", err)
        return None

    if cached is None:
        return None
    try:
        return deserialize_user(json.loads(cached))
    except (TypeError, ValueError, KeyError) as err:
        logger.warning("Invalid cached user payload for %s: %s", username, err)
        await invalidate_user_cache(username)
        return None


async def cache_user(user: User) -> None:
    """Write user data to the Redis cache with a TTL.

    :param user: The user instance to cache.
    :type user: User
    """
    try:
        await redis_client.setex(
            user_cache_key(user.username),
            settings.user_cache_ttl_seconds,
            json.dumps(serialize_user(user)),
        )
    except RedisError as err:
        logger.warning("Redis user cache write failed: %s", err)


async def invalidate_user_cache(username: str) -> None:
    """Remove a user entry from the Redis cache.

    Called after any mutation that changes cached fields (email
    confirmation, avatar update, password reset).

    :param username: The user's login name.
    :type username: str
    """
    try:
        await redis_client.delete(user_cache_key(username))
    except RedisError as err:
        logger.warning("Redis user cache invalidation failed: %s", err)


async def close_cache() -> None:
    """Close the Redis client connection pool.

    Should be called during application shutdown to release
    network resources gracefully.
    """
    await redis_client.aclose()
