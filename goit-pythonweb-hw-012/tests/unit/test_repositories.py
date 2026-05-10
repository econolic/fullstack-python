from datetime import date, timedelta

import pytest

from src.database.models import Contact
from src.repository.contacts import ContactRepository
from src.services.auth import utc_now
from src.services.users import UserService
from src.schemas import ContactCreate, ContactUpdate, UserCreate
from tests.conftest import TestingSessionLocal, create_test_user


@pytest.mark.asyncio
async def test_contact_repository_crud_and_owner_filtering():
    owner = await create_test_user(username="repo-owner", email="owner@example.com")
    other = await create_test_user(username="repo-other", email="other@example.com")
    async with TestingSessionLocal() as session:
        repository = ContactRepository(session)
        created = await repository.create_contact(
            ContactCreate(
                first_name="Ivan",
                last_name="Petrenko",
                email="repo@example.com",
                phone="+380501112233",
                birthday=date(1998, 5, 20),
            ),
            owner,
        )
        assert created.id
        assert await repository.get_contact_by_id(created.id, other) is None

        updated = await repository.update_contact(
            created, ContactUpdate(phone="+380501112244")
        )
        assert updated.phone == "+380501112244"

        contacts = await repository.get_contacts(owner, email="repo")
        assert len(contacts) == 1

        birthdays = await repository.get_upcoming_birthdays(owner, 365)
        assert birthdays

        await repository.delete_contact(created)
        assert await repository.get_contact_by_id(created.id, owner) is None


@pytest.mark.asyncio
async def test_user_repository_tokens_and_password_reset():
    async with TestingSessionLocal() as session:
        service = UserService(session)
        user = await service.create_user(
            UserCreate(
                username="repo-user",
                email="repo-user@example.com",
                password="hashed-password",
            )
        )
        refresh = await service.create_refresh_token(
            user, "jti-1", utc_now() + timedelta(hours=1)
        )
        stored_refresh = await service.get_refresh_token_by_jti("jti-1")
        assert stored_refresh is not None
        assert stored_refresh.id == refresh.id

        await service.revoke_refresh_token(refresh, utc_now(), "jti-2")
        assert refresh.revoked_at is not None
        assert refresh.replaced_by_jti == "jti-2"

        reset = await service.create_password_reset_token(
            user, "hash", utc_now() + timedelta(hours=1)
        )
        stored_reset = await service.get_password_reset_token("hash")
        assert stored_reset is not None
        assert stored_reset.id == reset.id

        await service.mark_password_reset_token_used(reset, utc_now())
        assert reset.used_at is not None

        await service.update_password(user, "new-hash")
        assert user.hashed_password == "new-hash"
