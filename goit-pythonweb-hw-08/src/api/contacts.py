import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactReplace, ContactResponse, ContactUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["contacts"])


def get_contact_repository(db: AsyncSession = Depends(get_db)) -> ContactRepository:
    return ContactRepository(db)


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    try:
        contact = await repository.create_contact(body)
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
    repository: ContactRepository = Depends(get_contact_repository),
) -> list[ContactResponse]:
    contacts = await repository.get_contacts(first_name, last_name, email)
    return [ContactResponse.model_validate(contact) for contact in contacts]


@router.get("/upcoming-birthdays", response_model=list[ContactResponse])
async def get_upcoming_birthdays(
    days: int = Query(default=7, ge=1, le=365),
    repository: ContactRepository = Depends(get_contact_repository),
) -> list[ContactResponse]:
    contacts = await repository.get_upcoming_birthdays(days)
    return [ContactResponse.model_validate(contact) for contact in contacts]


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    contact = await repository.get_contact_by_id(contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return ContactResponse.model_validate(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
async def replace_contact(
    contact_id: int,
    body: ContactReplace,
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    contact = await repository.get_contact_by_id(contact_id)
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
    repository: ContactRepository = Depends(get_contact_repository),
) -> ContactResponse:
    contact = await repository.get_contact_by_id(contact_id)
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
    repository: ContactRepository = Depends(get_contact_repository),
) -> None:
    contact = await repository.get_contact_by_id(contact_id)
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    await repository.delete_contact(contact)
    logger.info("Deleted contact id=%s", contact_id)
