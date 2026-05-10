"""Application settings loaded from environment variables and ``.env``.

All sensitive values (secrets, credentials, API keys) are read from the
environment and must not be hard-coded in the source tree.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic model that validates and exposes all runtime settings.

    Values are read from environment variables with an optional ``.env``
    file fallback.  See ``.env.example`` for the full list of supported
    keys.
    """

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    app_name: str = "Contacts API Auth"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_seconds: int = 3600
    refresh_token_expire_seconds: int = 604800
    password_reset_token_expire_seconds: int = 3600
    user_cache_ttl_seconds: int = 900

    mail_username: str
    mail_password: str
    mail_from: str
    mail_port: int = 465
    mail_server: str
    mail_from_name: str = "Contacts API"
    mail_starttls: bool = False
    mail_ssl_tls: bool = True
    use_credentials: bool = True
    validate_certs: bool = True

    cld_name: str
    cld_api_key: str
    cld_api_secret: str

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # pyright: ignore[reportCallIssue]
