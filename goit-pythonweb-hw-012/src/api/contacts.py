import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.database.models import User
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactReplace, ContactResponse, ContactUpdate
from src.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["contacts"])


def get_contact_repository(db: AsyncSession = Depends(get_db)) -> ContactRepository:
    return ContactRepository(db)


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    """Create a contact for the authenticated user."""
    try:
        contact = await repository.create_contact(body, current_user)
        return ContactResponse.model_validate(contact)
    except IntegrityError:
        await repository.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact with this email already exists",
        )


@router.get("/", response_model=list[ContactResponse])
async def get_contacts(
    first_name: str | None = Query(default=None, min_length=1, max_length=50),
    last_name: str | None = Query(default=None, min_length=1, max_length=50),
    email: str | None = Query(default=None, min_length=1, max_length=255),
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> list[ContactResponse]:
    """Return contacts owned by the authenticated user."""
    contacts = await repository.get_contacts(current_user, first_name, last_name, email)
    return [ContactResponse.model_validate(contact) for contact in contacts]


@router.get("/upcoming-birthdays", response_model=list[ContactResponse])
async def get_upcoming_birthdays(
    days: int = Query(default=7, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> list[ContactResponse]:
    """Return contacts with birthdays in the upcoming period."""
    contacts = await repository.get_upcoming_birthdays(current_user, days)
    return [ContactResponse.model_validate(contact) for contact in contacts]


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    """Return one contact owned by the authenticated user."""
    contact = await repository.get_contact_by_id(contact_id, current_user)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return ContactResponse.model_validate(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
async def replace_contact(
    contact_id: int,
    body: ContactReplace,
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    """Replace one contact owned by the authenticated user."""
    contact = await repository.get_contact_by_id(contact_id, current_user)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    try:
        replaced_contact = await repository.replace_contact(contact, body)
        return ContactResponse.model_validate(replaced_contact)
    except IntegrityError:
        await repository.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact with this email already exists",
        )


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    body: ContactUpdate,
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    """Partially update one contact owned by the authenticated user."""
    contact = await repository.get_contact_by_id(contact_id, current_user)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    try:
        updated_contact = await repository.update_contact(contact, body)
        return ContactResponse.model_validate(updated_contact)
    except IntegrityError:
        await repository.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact with this email already exists",
        )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    repository: ContactRepository = Depends(get_contact_repository),
) -> None:
    """Delete one contact owned by the authenticated user."""
    contact = await repository.get_contact_by_id(contact_id, current_user)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    await repository.delete_contact(contact)
    logger.info("Deleted contact id=%s", contact_id)
