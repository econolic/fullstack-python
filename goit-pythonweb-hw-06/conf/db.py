from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_DB_URL = (
    "postgresql+psycopg2://postgres:hw06_secure_pass_2026@localhost:5432/postgres"
)
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

_engine: Optional[Engine] = None
_session_local: Optional[sessionmaker] = None


def get_session_factory() -> sessionmaker:
    global _engine, _session_local

    if _session_local is None:
        _engine = create_engine(DATABASE_URL, echo=False)
        _session_local = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    return _session_local


@contextmanager
def get_session() -> Session:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_database_url() -> str:
    return DATABASE_URL
