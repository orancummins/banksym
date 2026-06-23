"""Persistence layer — SQLAlchemy engine, ORM models, and repository implementations.

This package adapts the domain/capability storage ``Protocol`` interfaces onto a real database so
state survives restarts. It depends on the layers it persists (core, tenancy, auth) but nothing in
those layers depends on it, preserving the architectural boundaries.
"""

from banksym.persistence.engine import (
    Base,
    init_db,
    make_engine,
    make_session_factory,
)
from banksym.persistence.repositories import (
    SqlBankRepository,
    SqlCoreBankingRepository,
    SqlCredentialStore,
)

__all__ = [
    "Base",
    "SqlBankRepository",
    "SqlCoreBankingRepository",
    "SqlCredentialStore",
    "init_db",
    "make_engine",
    "make_session_factory",
]
