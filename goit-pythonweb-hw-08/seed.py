from __future__ import annotations

import argparse
import asyncio
import random
from dataclasses import dataclass

from faker import Faker
from sqlalchemy import delete, func, select

from src.database.db import sessionmanager
from src.database.models import Contact


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be a positive integer")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill contacts table with random data")
    parser.add_argument(
        "--count",
        type=positive_int,
        default=50,
        help="How many contacts to generate (default: 50)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing contacts before insert",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible output",
    )
    parser.add_argument(
        "--locale",
        default="uk_UA",
        help="Faker locale (default: uk_UA)",
    )
    return parser.parse_args()


def build_unique_email(faker: Faker, used_emails: set[str]) -> str:
    domains = ("example.com", "mail.com", "demo.org")
    for _ in range(500):
        email = (
            f"{faker.user_name()}.{random.randint(1000, 9999)}"
            f"@{random.choice(domains)}"
        ).lower()
        if email not in used_emails:
            used_emails.add(email)
            return email
    raise RuntimeError("Unable to generate unique email")


def build_contact(faker: Faker, used_emails: set[str]) -> Contact:
    first_name = faker.first_name().strip()[:50]
    last_name = faker.last_name().strip()[:50]

    # Keep phone format compatible with schema regex and field length.
    phone = faker.numerify("+380#########")

    note = faker.sentence(nb_words=6).strip()[:255]
    additional_data = note if random.random() > 0.3 else None

    return Contact(
        first_name=first_name or "Name",
        last_name=last_name or "Surname",
        email=build_unique_email(faker, used_emails),
        phone=phone,
        birthday=faker.date_between(start_date="-80y", end_date="-18y"),
        additional_data=additional_data,
    )


@dataclass
class SeedResult:
    inserted: int
    reset: bool
    seed: int | None
    total_after: int


async def seed_contacts(
    count: int,
    reset: bool,
    seed: int | None,
    locale: str,
) -> SeedResult:
    faker = Faker(locale)
    if seed is not None:
        random.seed(seed)
        faker.seed_instance(seed)

    async with sessionmanager.session() as session:
        if reset:
            await session.execute(delete(Contact))
            await session.flush()

        existing_emails = set((await session.scalars(select(Contact.email))).all())

        contacts = [build_contact(faker, existing_emails) for _ in range(count)]
        session.add_all(contacts)
        await session.commit()

        total_after = await session.scalar(select(func.count(Contact.id)))

    return SeedResult(
        inserted=count,
        reset=reset,
        seed=seed,
        total_after=int(total_after or 0),
    )


async def main() -> int:
    args = parse_args()
    try:
        result = await seed_contacts(
            count=args.count,
            reset=args.reset,
            seed=args.seed,
            locale=args.locale,
        )
    except Exception as exc:
        print(f"Seed failed: {exc}")
        return 1
    finally:
        await sessionmanager.close()

    print("Seed completed successfully")
    print(f"Inserted: {result.inserted}")
    print(f"Reset applied: {result.reset}")
    print(f"Seed: {result.seed}")
    print(f"Total contacts in DB: {result.total_after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
