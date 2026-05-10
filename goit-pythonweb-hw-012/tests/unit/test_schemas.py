from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from src.schemas import (
    ContactCreate,
    ContactUpdate,
    UserCreate,
    _get_script,
    _validate_person_name,
)


def _contact_payload(**overrides):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+380501112233",
        "birthday": date(1990, 1, 1),
        "additional_data": "Notes",
    }
    payload.update(overrides)
    return payload


def test_get_script_classifies_known_and_fallback():
    assert _get_script("A") == "LATIN"
    assert _get_script("\u4e00") == "CJK"
    assert _get_script("\U0001f600") == "OTHER"


def test_validate_person_name_rejects_empty():
    with pytest.raises(ValueError, match="Name fields must not be empty"):
        _validate_person_name("   ")


def test_validate_person_name_rejects_bad_separators():
    with pytest.raises(
        ValueError, match="Name can contain separators only between letters"
    ):
        _validate_person_name("John--Doe")


def test_validate_person_name_rejects_invalid_chars():
    with pytest.raises(
        ValueError, match="Name can contain only letters, spaces, hyphens and"
    ):
        _validate_person_name("John3")


def test_validate_person_name_rejects_mixed_scripts():
    mixed_name = "John \u0406van"
    with pytest.raises(ValueError, match="Name cannot mix different alphabets/scripts"):
        _validate_person_name(mixed_name)


def test_contact_create_rejects_invalid_phone():
    payload = _contact_payload(phone="invalid")
    with pytest.raises(ValidationError, match="Phone number has invalid format"):
        ContactCreate(**payload)


def test_contact_create_rejects_future_birthday():
    payload = _contact_payload(birthday=date.today() + timedelta(days=1))
    with pytest.raises(ValidationError, match="Birthday cannot be in the future"):
        ContactCreate(**payload)


def test_contact_create_normalizes_additional_data():
    contact = ContactCreate(**_contact_payload(additional_data="  "))
    assert contact.additional_data is None

    contact = ContactCreate(**_contact_payload(additional_data=None))
    assert contact.additional_data is None


def test_contact_update_optional_validators_allow_none():
    assert ContactUpdate.validate_optional_names(None) is None
    assert ContactUpdate.validate_optional_phone(None) is None
    assert ContactUpdate.validate_optional_birthday(None) is None
    assert ContactUpdate.normalize_optional_additional_data(None) is None


def test_contact_update_rejects_invalid_phone():
    with pytest.raises(ValidationError, match="Phone number has invalid format"):
        ContactUpdate(phone="1234567x")


def test_contact_update_rejects_future_birthday():
    with pytest.raises(ValidationError, match="Birthday cannot be in the future"):
        ContactUpdate(birthday=date.today() + timedelta(days=1))


def test_contact_update_accepts_past_birthday():
    contact = ContactUpdate(birthday=date(1990, 1, 1))
    assert contact.birthday == date(1990, 1, 1)


def test_user_create_rejects_blank_username():
    with pytest.raises(ValidationError, match="Username must not be empty"):
        UserCreate(
            username="   ",
            email="user@example.com",
            password="strong-password",
        )
