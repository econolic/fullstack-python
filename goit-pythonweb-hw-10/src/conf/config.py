from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    app_name: str = "Contacts API Auth"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_seconds: int = 3600

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


settings = Settings()
