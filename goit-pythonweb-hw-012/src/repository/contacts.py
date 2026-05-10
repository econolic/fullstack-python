from datetime import date, timedelta
import calendar

from sqlalchemy import Integer, cast, extract, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.schemas import ContactCreate, ContactReplace, ContactUpdate


class ContactRepository:
    """Data-access layer for user-owned contacts.

    Every query is scoped to the authenticated user so that contacts
    belonging to other users are never exposed.
    """

    def __init__(self, session: AsyncSession):
        """Initialise the repository with an async database session.

        :param session: An active SQLAlchemy async session.
        :type session: AsyncSession
        """
        self.session = session

    async def get_contacts(
        self,
        user: User,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> list[Contact]:
        """Return contacts owned by *user*, optionally filtered.

        Filters use case-insensitive ``ILIKE`` matching so that partial
        strings are accepted.

        :param user: The authenticated contact owner.
        :type user: User
        :param first_name: Substring filter for the first name.
        :type first_name: str | None
        :param last_name: Substring filter for the last name.
        :type last_name: str | None
        :param email: Substring filter for the email.
        :type email: str | None
        :returns: A list of matching contacts ordered by ID.
        :rtype: list[Contact]
        """
        stmt = select(Contact).where(Contact.user_id == user.id).order_by(Contact.id)

        if first_name:
            stmt = stmt.where(Contact.first_name.ilike(f"%{first_name.strip()}%"))
        if last_name:
            stmt = stmt.where(Contact.last_name.ilike(f"%{last_name.strip()}%"))
        if email:
            stmt = stmt.where(Contact.email.ilike(f"%{email.strip()}%"))

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_contact_by_id(self, contact_id: int, user: User) -> Contact | None:
        """Fetch a single contact by primary key, scoped to the owner.

        :param contact_id: The contact's database ID.
        :type contact_id: int
        :param user: The authenticated owner.
        :type user: User
        :returns: The contact or ``None`` if not found or not owned.
        :rtype: Contact | None
        """
        result = await self.session.scalars(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id)
        )
        return result.first()

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        """Create a new contact owned by *user*.

        :param body: Validated contact data.
        :type body: ContactCreate
        :param user: The authenticated owner.
        :type user: User
        :returns: The newly created contact with a database-assigned ID.
        :rtype: Contact
        :raises sqlalchemy.exc.IntegrityError: If a contact with the
            same email already exists for this user.
        """
        contact = Contact(**body.model_dump(), user_id=user.id)
        self.session.add(contact)
        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def update_contact(self, contact: Contact, body: ContactUpdate) -> Contact:
        """Apply a partial update to an existing contact.

        Only fields explicitly set in *body* are written; unset fields
        remain unchanged.

        :param contact: The contact instance to modify.
        :type contact: Contact
        :param body: Fields to update (only set values are applied).
        :type body: ContactUpdate
        :returns: The updated contact.
        :rtype: Contact
        """
        update_data = body.model_dump(exclude_unset=True)
        if not update_data:
            return contact

        for field, value in update_data.items():
            setattr(contact, field, value)

        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def replace_contact(self, contact: Contact, body: ContactReplace) -> Contact:
        """Replace all editable fields of an existing contact.

        :param contact: The contact instance to overwrite.
        :type contact: Contact
        :param body: Complete replacement payload.
        :type body: ContactReplace
        :returns: The replaced contact.
        :rtype: Contact
        :raises sqlalchemy.exc.IntegrityError: If the new email
            collides with another contact of the same owner.
        """
        replace_data = body.model_dump()

        for field, value in replace_data.items():
            setattr(contact, field, value)

        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def delete_contact(self, contact: Contact) -> None:
        """Delete a contact from the database.

        :param contact: The contact instance to remove.
        :type contact: Contact
        """
        await self.session.delete(contact)
        await self.session.commit()

    async def get_upcoming_birthdays(self, user: User, days: int = 7) -> list[Contact]:
        """Return contacts whose birthday falls within the next *days* days.

        Leap-year birthdays (29 Feb) are handled: on non-leap years they
        are matched against 28 Feb.

        :param user: The authenticated contact owner.
        :type user: User
        :param days: Look-ahead window in days (default 7).
        :type days: int
        :returns: Contacts with upcoming birthdays, ordered by ID.
        :rtype: list[Contact]
        """
        today = date.today()
        period_end = today + timedelta(days=days)

        month_day_pairs = self._build_month_day_pairs(today, days)
        month_expr = cast(extract("month", Contact.birthday), Integer)
        day_expr = cast(extract("day", Contact.birthday), Integer)

        stmt = (
            select(Contact)
            .where(
                Contact.user_id == user.id,
                tuple_(month_expr, day_expr).in_(month_day_pairs),
            )
            .order_by(Contact.id)
        )
        result = await self.session.scalars(stmt)
        contacts = list(result.all())

        upcoming = []
        for contact in contacts:
            next_birthday = self._next_birthday(contact.birthday, today)
            if today <= next_birthday <= period_end:
                upcoming.append(contact)

        return upcoming

    @staticmethod
    def _build_month_day_pairs(from_date: date, days: int) -> list[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()

        for offset in range(days + 1):
            current = from_date + timedelta(days=offset)
            pairs.add((current.month, current.day))

            if (
                current.month == 2
                and current.day == 28
                and not calendar.isleap(current.year)
            ):
                pairs.add((2, 29))

        return sorted(pairs)

    @staticmethod
    def _next_birthday(birthday: date, from_date: date) -> date:
        target_year = from_date.year

        try:
            candidate = birthday.replace(year=target_year)
        except ValueError:
            # Handle 29 Feb on non-leap years.
            candidate = birthday.replace(year=target_year, day=28)

        if candidate < from_date:
            target_year += 1
            try:
                candidate = birthday.replace(year=target_year)
            except ValueError:
                candidate = birthday.replace(year=target_year, day=28)

        return candidate
