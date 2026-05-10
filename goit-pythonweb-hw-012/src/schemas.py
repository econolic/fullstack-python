from datetime import date, datetime
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PHONE_PATTERN = re.compile(r"^\+?[0-9().\-\s]{7,20}$")
NAME_SEPARATORS = {" ", "-", "'", "’", "ʼ"}


def _get_script(char: str) -> str:
    unicode_name = unicodedata.name(char, "")

    script_tokens = (
        "LATIN",
        "CYRILLIC",
        "GREEK",
        "ARMENIAN",
        "HEBREW",
        "ARABIC",
        "DEVANAGARI",
        "BENGALI",
        "GURMUKHI",
        "GUJARATI",
        "ORIYA",
        "TAMIL",
        "TELUGU",
        "KANNADA",
        "MALAYALAM",
        "SINHALA",
        "THAI",
        "LAO",
        "TIBETAN",
        "MYANMAR",
        "GEORGIAN",
        "HANGUL",
        "HIRAGANA",
        "KATAKANA",
    )

    for token in script_tokens:
        if token in unicode_name:
            return token

    if "CJK" in unicode_name or "IDEOGRAPH" in unicode_name:
        return "CJK"

    return "OTHER"


def _validate_person_name(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", value.strip())
    if not cleaned:
        raise ValueError("Name fields must not be empty")

    scripts: set[str] = set()
    has_letter = False
    previous_was_separator = False

    for index, char in enumerate(cleaned):
        if char in NAME_SEPARATORS:
            if index == 0 or index == len(cleaned) - 1 or previous_was_separator:
                raise ValueError("Name can contain separators only between letters")
            previous_was_separator = True
            continue

        if char.isalpha():
            has_letter = True
            scripts.add(_get_script(char))
            previous_was_separator = False
            continue

        raise ValueError(
            "Name can contain only letters, spaces, hyphens and apostrophes"
        )

    if not has_letter:
        raise ValueError("Name fields must contain letters")

    if len(scripts) > 1:
        raise ValueError("Name cannot mix different alphabets/scripts")

    return cleaned


class ContactBase(BaseModel):
    """Shared contact fields and validation rules.

    Used as the base schema for create, replace, and response payloads.
    Names are normalised, phone numbers are checked against a conservative
    pattern, and future birthdays are rejected.
    """

    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    birthday: date
    additional_data: str | None = Field(default=None, max_length=255)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        """Normalise and validate a contact first or last name."""
        return _validate_person_name(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Trim and validate a required phone number."""
        cleaned = value.strip()
        if not PHONE_PATTERN.match(cleaned):
            raise ValueError("Phone number has invalid format")
        return cleaned

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, value: date) -> date:
        """Reject birthdays that are later than today's date."""
        if value > date.today():
            raise ValueError("Birthday cannot be in the future")
        return value

    @field_validator("additional_data")
    @classmethod
    def normalize_additional_data(cls, value: str | None) -> str | None:
        """Trim optional contact notes and store blank values as ``None``."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ContactCreate(ContactBase):
    """Payload for creating a new contact."""

    pass


class ContactReplace(ContactBase):
    """Payload for replacing a contact with a complete set of fields."""

    pass


class ContactUpdate(BaseModel):
    """Payload for partially updating an existing contact.

    All fields are optional so callers can send only the values that should
    change.  Validators mirror :class:`ContactBase` for any provided fields.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    birthday: date | None = None
    additional_data: str | None = Field(default=None, max_length=255)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_optional_names(cls, value: str | None) -> str | None:
        """Validate a provided name while allowing omitted values."""
        if value is None:
            return None
        return _validate_person_name(value)

    @field_validator("phone")
    @classmethod
    def validate_optional_phone(cls, value: str | None) -> str | None:
        """Trim and validate a provided phone number."""
        if value is None:
            return None
        cleaned = value.strip()
        if not PHONE_PATTERN.match(cleaned):
            raise ValueError("Phone number has invalid format")
        return cleaned

    @field_validator("birthday")
    @classmethod
    def validate_optional_birthday(cls, value: date | None) -> date | None:
        """Reject a provided birthday when it is in the future."""
        if value is None:
            return None
        if value > date.today():
            raise ValueError("Birthday cannot be in the future")
        return value

    @field_validator("additional_data")
    @classmethod
    def normalize_optional_additional_data(cls, value: str | None) -> str | None:
        """Trim provided notes and store blank values as ``None``."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ContactResponse(ContactBase):
    """Contact representation returned by API endpoints."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Registration payload for a new user account."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """Trim the username and reject blank values."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Username must not be empty")
        return cleaned


class UserResponse(BaseModel):
    """Public user profile returned by the API.

    The password hash is intentionally excluded from this schema.
    """

    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    role: str
    confirmed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Bearer token response returned by login and refresh endpoints."""

    access_token: str
    refresh_token: str | None = None
    token_type: str


class RefreshTokenRequest(BaseModel):
    """Request body containing a refresh token to rotate."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body containing a refresh token to revoke."""

    refresh_token: str


class RequestEmail(BaseModel):
    """Request body for resending an email confirmation message."""

    email: EmailStr


class PasswordResetRequest(BaseModel):
    """Request body for starting the password reset flow."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Request body for completing a password reset with a one-time token."""

    token: str
    new_password: str = Field(min_length=6, max_length=128)
