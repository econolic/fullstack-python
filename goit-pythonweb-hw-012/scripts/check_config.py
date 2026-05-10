"""Validate project and runtime configuration before build/startup."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_ENV_EXAMPLE_KEYS = {
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_SECONDS",
    "REFRESH_TOKEN_EXPIRE_SECONDS",
    "PASSWORD_RESET_TOKEN_EXPIRE_SECONDS",
    "USER_CACHE_TTL_SECONDS",
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_FROM",
    "MAIL_PORT",
    "MAIL_SERVER",
    "MAIL_STARTTLS",
    "MAIL_SSL_TLS",
    "USE_CREDENTIALS",
    "VALIDATE_CERTS",
    "CLD_NAME",
    "CLD_API_KEY",
    "CLD_API_SECRET",
    "CORS_ORIGINS",
}

PLACEHOLDER_PARTS = (
    "replace-with",
    "example@example.com",
    "smtp.example.com",
)


def parse_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def fail(message: str) -> None:
    print(f"Configuration check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return any(part in normalized for part in PLACEHOLDER_PARTS)


def validate_url(name: str, value: str, allowed_schemes: set[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in allowed_schemes:
        fail(f"{name} must use one of: {', '.join(sorted(allowed_schemes))}")
    if not parsed.hostname:
        fail(f"{name} must include a hostname")


def validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        fail(f"{name} must be greater than zero")


def validate_build_config() -> None:
    """Validate files that must be correct inside the Docker image."""
    if not ENV_EXAMPLE.exists():
        fail(".env.example is missing")

    env_values = parse_env_example(ENV_EXAMPLE)
    missing = sorted(REQUIRED_ENV_EXAMPLE_KEYS - set(env_values))
    if missing:
        fail(f".env.example is missing keys: {', '.join(missing)}")

    if "JWT_EXPIRATION_SECONDS" in env_values:
        fail(".env.example still contains old JWT_EXPIRATION_SECONDS")

    for relative_path in ("pyproject.toml", "poetry.lock", "alembic.ini"):
        if not (ROOT / relative_path).exists():
            fail(f"{relative_path} is missing")

    print("Build configuration check passed")


def validate_runtime_config() -> None:
    """Validate environment variables before the API starts."""
    from src.conf.config import settings

    validate_url(
        "DATABASE_URL",
        settings.database_url,
        {"postgresql+asyncpg", "sqlite+aiosqlite"},
    )
    validate_url("REDIS_URL", settings.redis_url, {"redis", "rediss"})

    if settings.jwt_algorithm != "HS256":
        fail("JWT_ALGORITHM must be HS256")
    if len(settings.jwt_secret) < 32 or is_placeholder(settings.jwt_secret):
        fail("JWT_SECRET must be a real secret with at least 32 characters")

    validate_positive_int(
        "ACCESS_TOKEN_EXPIRE_SECONDS", settings.access_token_expire_seconds
    )
    validate_positive_int(
        "REFRESH_TOKEN_EXPIRE_SECONDS", settings.refresh_token_expire_seconds
    )
    validate_positive_int(
        "PASSWORD_RESET_TOKEN_EXPIRE_SECONDS",
        settings.password_reset_token_expire_seconds,
    )
    validate_positive_int("USER_CACHE_TTL_SECONDS", settings.user_cache_ttl_seconds)
    if settings.access_token_expire_seconds >= settings.refresh_token_expire_seconds:
        fail(
            "ACCESS_TOKEN_EXPIRE_SECONDS must be lower than REFRESH_TOKEN_EXPIRE_SECONDS"
        )

    for name, value in {
        "MAIL_USERNAME": settings.mail_username,
        "MAIL_PASSWORD": settings.mail_password,
        "MAIL_FROM": settings.mail_from,
        "MAIL_SERVER": settings.mail_server,
        "CLD_NAME": settings.cld_name,
        "CLD_API_KEY": settings.cld_api_key,
        "CLD_API_SECRET": settings.cld_api_secret,
    }.items():
        if not value or is_placeholder(value):
            fail(f"{name} must be configured with a real value")

    validate_positive_int("MAIL_PORT", settings.mail_port)
    if settings.mail_starttls and settings.mail_ssl_tls:
        fail("MAIL_STARTTLS and MAIL_SSL_TLS cannot both be True")

    if settings.cors_origins.strip() != "*":
        for origin in settings.cors_origin_list:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                fail(f"CORS_ORIGINS contains invalid origin: {origin}")

    print("Runtime configuration check passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("build", "runtime"), required=True)
    args = parser.parse_args()

    os.chdir(ROOT)
    if args.mode == "build":
        validate_build_config()
    else:
        validate_runtime_config()


if __name__ == "__main__":
    main()
