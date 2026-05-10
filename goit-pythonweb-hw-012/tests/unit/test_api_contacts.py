from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.api.contacts import (
    create_contact,
    delete_contact,
    get_contact,
    get_contact_repository,
    get_contacts,
    get_upcoming_birthdays,
    replace_contact,
    update_contact,
)
from src.database.models import User
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactReplace, ContactUpdate


def contact_object(contact_id: int = 1, email: str = "contact@example.com"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=contact_id,
        first_name="Ivan",
        last_name="Petrenko",
        email=email,
        phone="+380501112233",
        birthday=date(1998, 5, 20),
        additional_data="friend",
        created_at=now,
        updated_at=now,
    )


def contact_create(email: str = "contact@example.com") -> ContactCreate:
    return ContactCreate(
        first_name="Ivan",
        last_name="Petrenko",
        email=email,
        phone="+380501112233",
        birthday=date(1998, 5, 20),
        additional_data="friend",
    )


def current_user() -> User:
    return cast(User, SimpleNamespace(id=1, username="owner"))


class FakeContactRepository:
    def __init__(self) -> None:
        self.session = SimpleNamespace(rollback=AsyncMock())
        self.contact = contact_object()
        self.create_contact = AsyncMock(return_value=self.contact)
        self.get_contacts = AsyncMock(return_value=[self.contact])
        self.get_upcoming_birthdays = AsyncMock(return_value=[self.contact])
        self.get_contact_by_id = AsyncMock(return_value=self.contact)
        self.replace_contact = AsyncMock(return_value=self.contact)
        self.update_contact = AsyncMock(return_value=self.contact)
        self.delete_contact = AsyncMock(return_value=None)


@pytest.mark.asyncio
async def test_contact_repository_dependency_factory() -> None:
    session = SimpleNamespace()
    repository = get_contact_repository(cast(AsyncMock, session))

    assert isinstance(repository, ContactRepository)


@pytest.mark.asyncio
async def test_contact_route_success_branches() -> None:
    repository = FakeContactRepository()
    repo = cast(ContactRepository, repository)
    user = current_user()

    created = await create_contact(contact_create(), user, repo)
    assert created.email == "contact@example.com"

    listed = await get_contacts("iv", "pet", "contact", user, repo)
    assert [contact.id for contact in listed] == [1]

    birthdays = await get_upcoming_birthdays(30, user, repo)
    assert [contact.id for contact in birthdays] == [1]

    fetched = await get_contact(1, user, repo)
    assert fetched.id == 1

    replaced = await replace_contact(
        1,
        ContactReplace(**contact_create("new@example.com").model_dump()),
        user,
        repo,
    )
    assert replaced.id == 1

    updated = await update_contact(
        1,
        ContactUpdate(additional_data="updated"),
        user,
        repo,
    )
    assert updated.id == 1

    assert await delete_contact(1, user, repo) is None
    repository.delete_contact.assert_awaited_once_with(repository.contact)


@pytest.mark.asyncio
async def test_contact_route_not_found_branches() -> None:
    repository = FakeContactRepository()
    repository.get_contact_by_id.return_value = None
    repo = cast(ContactRepository, repository)
    user = current_user()

    with pytest.raises(HTTPException) as get_exc:
        await get_contact(404, user, repo)
    assert get_exc.value.status_code == 404

    with pytest.raises(HTTPException) as replace_exc:
        await replace_contact(
            404,
            ContactReplace(**contact_create().model_dump()),
            user,
            repo,
        )
    assert replace_exc.value.status_code == 404

    with pytest.raises(HTTPException) as update_exc:
        await update_contact(404, ContactUpdate(first_name="Missing"), user, repo)
    assert update_exc.value.status_code == 404

    with pytest.raises(HTTPException) as delete_exc:
        await delete_contact(404, user, repo)
    assert delete_exc.value.status_code == 404


@pytest.mark.asyncio
async def test_contact_route_conflict_branches() -> None:
    repository = FakeContactRepository()
    repo = cast(ContactRepository, repository)
    user = current_user()
    integrity_error = IntegrityError("statement", "params", Exception("duplicate"))

    repository.create_contact.side_effect = integrity_error
    with pytest.raises(HTTPException) as create_exc:
        await create_contact(contact_create(), user, repo)
    assert create_exc.value.status_code == 409
    repository.session.rollback.assert_awaited()

    repository.session.rollback.reset_mock()
    repository.create_contact.side_effect = None
    repository.replace_contact.side_effect = integrity_error
    with pytest.raises(HTTPException) as replace_exc:
        await replace_contact(
            1,
            ContactReplace(**contact_create("duplicate@example.com").model_dump()),
            user,
            repo,
        )
    assert replace_exc.value.status_code == 409
    repository.session.rollback.assert_awaited()

    repository.session.rollback.reset_mock()
    repository.replace_contact.side_effect = None
    repository.update_contact.side_effect = integrity_error
    with pytest.raises(HTTPException) as update_exc:
        await update_contact(
            1, ContactUpdate(email="duplicate@example.com"), user, repo
        )
    assert update_exc.value.status_code == 409
    repository.session.rollback.assert_awaited()
