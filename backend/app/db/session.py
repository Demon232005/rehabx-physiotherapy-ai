"""SQLAlchemy session management.

Supports SQLite (local dev) and PostgreSQL (production) via DATABASE_URL.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables, apply file-based migrations and seed reference data."""
    # Import models so they register on Base.metadata.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from app.db.migrations import run_migrations

    run_migrations(engine)

    from app.services.seed import seed_reference_data

    session = SessionLocal()
    try:
        seed_reference_data(session)
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
