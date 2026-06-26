"""ORM models mapping domain entities to relational tables.

These are deliberately thin row representations; the repository layer translates between rows and
the rich domain dataclasses so the rest of the codebase stays persistence-agnostic.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from banksym.persistence.engine import Base


class BankRow(Base):
    __tablename__ = "banks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    primary_color: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    locale: Mapped[str] = mapped_column(String)
    base_currency: Mapped[str] = mapped_column(String)
    supported_currencies: Mapped[list] = mapped_column(JSON, default=list)
    enabled_protocols: Mapped[list] = mapped_column(JSON, default=list)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)


class CustomerRow(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bank_id: Mapped[str] = mapped_column(String, index=True)
    full_name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    persona: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, default="manual")


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bank_id: Mapped[str] = mapped_column(String, index=True)
    currency: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    iban: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    account_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)


class JournalEntryRow(Base):
    __tablename__ = "journal_entries"

    # Autoincrement sequence preserves insertion order for stable history rendering.
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String, unique=True, index=True)
    bank_id: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String, default="")
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    booked_at: Mapped[datetime] = mapped_column()
    # [{"account_id": str, "minor_units": int, "currency": str}, ...]
    postings: Mapped[list] = mapped_column(JSON, default=list)
    entry_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class CredentialRow(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bank_id: Mapped[str] = mapped_column(String, index=True)
    username: Mapped[str] = mapped_column(String, index=True)
    secret_hash: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str] = mapped_column(String)


__all__ = [
    "AccountRow",
    "BankRow",
    "CredentialRow",
    "CustomerRow",
    "JournalEntryRow",
]
