"""SQLAlchemy engine + schema bootstrap for the persistence layer."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def make_engine(database_url: str) -> Engine:
    """Create an engine, configuring SQLite for shared in-process/in-memory use.

    In-memory SQLite (``sqlite://``) uses a :class:`StaticPool` so every session shares one
    connection — required for tests and for a single-process server to see consistent state.
    """
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            return create_engine(
                database_url, connect_args=connect_args, poolclass=StaticPool
            )
        return create_engine(database_url, connect_args=connect_args)
    return create_engine(database_url)


def init_db(engine: Engine) -> None:
    """Create all tables if they do not already exist."""
    # Importing models registers them on ``Base.metadata`` before ``create_all``.
    from banksym.persistence import models  # noqa: F401

    Base.metadata.create_all(engine)
    _backfill_columns(engine)


# Newly added nullable columns that may be absent from pre-existing databases. ``create_all`` only
# creates missing tables, never new columns, so we add them in-place to keep existing data.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "customers": {"address": "VARCHAR"},
}


def _backfill_columns(engine: Engine) -> None:
    """Idempotently add nullable columns introduced after a database was first created."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _ADDED_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        with engine.begin() as conn:
            for name, ddl_type in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
