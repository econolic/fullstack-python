from datetime import date, timedelta
import calendar

from sqlalchemy import Integer, cast, extract, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact
from src.schemas import ContactCreate, ContactReplace, ContactUpdate


class ContactRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_contacts(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> list[Contact]:
        stmt = select(Contact).order_by(Contact.id)

        if first_name:
            stmt = stmt.where(Contact.first_name.ilike(f"%{first_name.strip()}%"))
        if last_name:
            stmt = stmt.where(Contact.last_name.ilike(f"%{last_name.strip()}%"))
        if email:
            stmt = stmt.where(Contact.email.ilike(f"%{email.strip()}%"))

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_contact_by_id(self, contact_id: int) -> Contact | None:
        result = await self.session.scalars(
            select(Contact).where(Contact.id == contact_id)
        )
        return result.first()

    async def create_contact(self, body: ContactCreate) -> Contact:
        contact = Contact(**body.model_dump())
        self.session.add(contact)
        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def update_contact(self, contact: Contact, body: ContactUpdate) -> Contact:
        update_data = body.model_dump(exclude_unset=True)
        if not update_data:
            return contact

        for field, value in update_data.items():
            setattr(contact, field, value)

        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def replace_contact(self, contact: Contact, body: ContactReplace) -> Contact:
        replace_data = body.model_dump()

        for field, value in replace_data.items():
            setattr(contact, field, value)

        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def delete_contact(self, contact: Contact) -> None:
        await self.session.delete(contact)
        await self.session.commit()

    async def get_upcoming_birthdays(self, days: int = 7) -> list[Contact]:
        today = date.today()
        period_end = today + timedelta(days=days)

        month_day_pairs = self._build_month_day_pairs(today, days)
        month_expr = cast(extract("month", Contact.birthday), Integer)
        day_expr = cast(extract("day", Contact.birthday), Integer)

        stmt = (
            select(Contact)
            .where(tuple_(month_expr, day_expr).in_(month_day_pairs))
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
