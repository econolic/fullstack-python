from src.conf.config import Settings


def _base_settings(**overrides):
    values = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "jwt_secret": "test-secret",
        "mail_username": "user@example.com",
        "mail_password": "password",
        "mail_from": "user@example.com",
        "mail_server": "smtp.example.com",
        "cld_name": "cloud",
        "cld_api_key": "key",
        "cld_api_secret": "secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_cors_origin_list_star():
    settings = _base_settings(cors_origins="*")
    assert settings.cors_origin_list == ["*"]


def test_cors_origin_list_parses_csv():
    settings = _base_settings(cors_origins="https://a.com, https://b.com, ,")
    assert settings.cors_origin_list == ["https://a.com", "https://b.com"]
