from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi_mail.errors import ConnectionErrors

from src.services import email as email_service


@pytest.mark.asyncio
async def test_send_email_builds_verification_message(monkeypatch) -> None:
    sent: dict[str, Any] = {}

    class FakeFastMail:
        def __init__(self, conf) -> None:
            sent["conf"] = conf

        async def send_message(self, message, template_name: str) -> None:
            sent["message"] = message
            sent["template_name"] = template_name

    monkeypatch.setattr(email_service, "create_email_token", lambda data: "token-123")
    monkeypatch.setattr(email_service, "FastMail", FakeFastMail)

    await email_service.send_email("user@example.com", "user", "http://testserver/")

    message = sent["message"]
    assert message.subject == "Confirm your email"
    assert message.recipients == ["user@example.com"]
    assert message.template_body == {
        "host": "http://testserver/",
        "username": "user",
        "token": "token-123",
    }
    assert sent["template_name"] == "verify_email.html"


@pytest.mark.asyncio
async def test_send_password_reset_email_builds_message(monkeypatch) -> None:
    sent: dict[str, Any] = {}

    class FakeFastMail:
        def __init__(self, conf) -> None:
            sent["conf"] = conf

        async def send_message(self, message, template_name: str) -> None:
            sent["message"] = message
            sent["template_name"] = template_name

    monkeypatch.setattr(email_service, "FastMail", FakeFastMail)

    await email_service.send_password_reset_email(
        "user@example.com",
        "user",
        "http://testserver/",
        "reset-token",
    )

    message = sent["message"]
    assert message.subject == "Reset your password"
    assert message.recipients == ["user@example.com"]
    assert message.template_body == {
        "host": "http://testserver/",
        "username": "user",
        "token": "reset-token",
    }
    assert sent["template_name"] == "reset_password.html"


@pytest.mark.asyncio
async def test_email_helpers_log_connection_errors(monkeypatch) -> None:
    class BrokenFastMail:
        def __init__(self, conf) -> None:
            self.conf = conf

        async def send_message(self, message, template_name: str) -> None:
            raise ConnectionErrors("smtp down")

    warning = MagicMock()
    monkeypatch.setattr(email_service, "FastMail", BrokenFastMail)
    monkeypatch.setattr(email_service, "create_email_token", lambda data: "token-123")
    monkeypatch.setattr(email_service.logger, "warning", warning)

    await email_service.send_email("user@example.com", "user", "http://testserver/")
    await email_service.send_password_reset_email(
        "user@example.com",
        "user",
        "http://testserver/",
        "reset-token",
    )

    assert warning.call_count == 2
    assert warning.call_args_list[0].args[0] == "Email was not sent: %s"
    assert warning.call_args_list[1].args[0] == "Password reset email was not sent: %s"
