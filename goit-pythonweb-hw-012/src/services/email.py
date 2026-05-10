"""Transactional email helpers for verification and password reset.

Emails are sent asynchronously via ``fastapi-mail`` using HTML templates
stored in the ``templates/`` subdirectory.
"""

import logging
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from src.conf.config import settings
from src.services.auth import create_email_token

logger = logging.getLogger(__name__)

conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=settings.use_credentials,
    VALIDATE_CERTS=settings.validate_certs,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates",
)


async def send_email(email: EmailStr, username: str, host: str) -> None:
    """Send an email-verification message with a one-time link.

    :param email: Recipient's email address.
    :type email: EmailStr
    :param username: Display name used in the email body.
    :type username: str
    :param host: Base URL of the running application (used to build
        the verification link).
    :type host: str
    """
    try:
        token_verification = create_email_token({"sub": str(email)})
        message = MessageSchema(
            subject="Confirm your email",
            recipients=[email],
            template_body={
                "host": host,
                "username": username,
                "token": token_verification,
            },
            subtype=MessageType.html,
        )
        fm = FastMail(conf)
        await fm.send_message(message, template_name="verify_email.html")
    except ConnectionErrors as err:
        logger.warning("Email was not sent: %s", err)


async def send_password_reset_email(
    email: EmailStr, username: str, host: str, token: str
) -> None:
    """Send a password-reset message containing a one-time token.

    :param email: Recipient's email address.
    :type email: EmailStr
    :param username: Display name used in the email body.
    :type username: str
    :param host: Base URL of the running application.
    :type host: str
    :param token: The raw (unhashed) password-reset token.
    :type token: str
    """
    try:
        message = MessageSchema(
            subject="Reset your password",
            recipients=[email],
            template_body={
                "host": host,
                "username": username,
                "token": token,
            },
            subtype=MessageType.html,
        )
        fm = FastMail(conf)
        await fm.send_message(message, template_name="reset_password.html")
    except ConnectionErrors as err:
        logger.warning("Password reset email was not sent: %s", err)
