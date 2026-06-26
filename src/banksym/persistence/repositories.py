"""SQLAlchemy-backed repository implementations.

Each repository satisfies the structural ``Protocol`` defined in its domain/capability layer while
translating between persistent rows and the in-memory domain dataclasses. State therefore survives
process restarts (banks, customers, accounts, transactions, and online-banking credentials).
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from banksym.capabilities.auth.base import Credential
from banksym.core.domain.account import Account, AccountStatus, AccountType
from banksym.core.domain.customer import Customer
from banksym.core.domain.ledger import JournalEntry, Posting
from banksym.core.kernel.money import Money
from banksym.persistence.models import (
    AccountRow,
    BankRow,
    CredentialRow,
    CustomerRow,
    JournalEntryRow,
)
from banksym.tenancy.bank import Bank, BankBranding, CapabilitySelection


# -- Bank <-> row -------------------------------------------------------------------
def _bank_to_row(bank: Bank) -> BankRow:
    return BankRow(
        id=bank.id,
        display_name=bank.branding.display_name,
        logo_url=bank.branding.logo_url,
        primary_color=bank.branding.primary_color,
        secondary_color=bank.branding.secondary_color,
        country=bank.country,
        locale=bank.locale,
        base_currency=bank.base_currency,
        supported_currencies=list(bank.supported_currencies),
        supported_languages=list(bank.supported_languages),
        supported_customer_types=list(bank.supported_customer_types),
        open_banking_enabled=bool(bank.open_banking_enabled),
        card_products=list(bank.card_products),
        current_account_products=list(bank.current_account_products),
        savings_account_products=list(bank.savings_account_products),
        loan_products=list(bank.loan_products),
        enabled_protocols=list(bank.enabled_protocols),
        capabilities=dict(bank.capabilities.selected),
    )


def _row_to_bank(row: BankRow) -> Bank:
    currencies = list(row.supported_currencies or [])
    if row.base_currency and row.base_currency not in currencies:
        currencies.insert(0, row.base_currency)
    return Bank(
        branding=BankBranding(
            display_name=row.display_name,
            logo_url=row.logo_url,
            primary_color=row.primary_color,
            secondary_color=getattr(row, "secondary_color", None) or row.primary_color,
        ),
        country=row.country,
        locale=row.locale,
        base_currency=row.base_currency,
        supported_currencies=currencies,
        supported_languages=list(getattr(row, "supported_languages", []) or []),
        supported_customer_types=list(getattr(row, "supported_customer_types", []) or []),
        open_banking_enabled=bool(getattr(row, "open_banking_enabled", False) or list(row.enabled_protocols or [])),
        card_products=list(getattr(row, "card_products", []) or []),
        current_account_products=list(getattr(row, "current_account_products", []) or []),
        savings_account_products=list(getattr(row, "savings_account_products", []) or []),
        loan_products=list(getattr(row, "loan_products", []) or []),
        enabled_protocols=list(row.enabled_protocols or []),
        capabilities=CapabilitySelection(selected=dict(row.capabilities or {})),
        id=row.id,
    )


class SqlBankRepository:
    """Persistent :class:`~banksym.tenancy.repository.BankRepository`."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def add(self, bank: Bank) -> None:
        with self._sf.begin() as s:
            s.merge(_bank_to_row(bank))

    def get(self, bank_id: str) -> Bank | None:
        with self._sf() as s:
            row = s.get(BankRow, bank_id)
            return _row_to_bank(row) if row else None

    def list(self) -> list[Bank]:
        with self._sf() as s:
            return [_row_to_bank(r) for r in s.scalars(select(BankRow)).all()]

    def remove(self, bank_id: str) -> None:
        with self._sf.begin() as s:
            s.execute(delete(BankRow).where(BankRow.id == bank_id))


# -- Customer / Account / Journal <-> row ------------------------------------------
def _customer_to_row(c: Customer) -> CustomerRow:
    return CustomerRow(
        id=c.id,
        bank_id=c.bank_id,
        full_name=c.full_name,
        email=c.email,
        phone=c.phone,
        date_of_birth=c.date_of_birth,
        country=c.country,
        address=c.address,
        persona=c.persona,
        source=c.source,
    )


def _row_to_customer(r: CustomerRow) -> Customer:
    return Customer(
        bank_id=r.bank_id,
        full_name=r.full_name,
        id=r.id,
        email=r.email,
        phone=r.phone,
        date_of_birth=r.date_of_birth,
        country=r.country,
        address=r.address,
        persona=r.persona,
        source=getattr(r, "source", "manual") or "manual",
    )


def _account_to_row(a: Account) -> AccountRow:
    return AccountRow(
        id=a.id,
        bank_id=a.bank_id,
        currency=a.currency,
        type=a.type.value,
        status=a.status.value,
        customer_id=a.customer_id,
        iban=a.iban,
        name=a.name,
        account_metadata=a.metadata or {},
    )


def _row_to_account(r: AccountRow) -> Account:
    return Account(
        bank_id=r.bank_id,
        currency=r.currency,
        type=AccountType(r.type),
        status=AccountStatus(r.status),
        customer_id=r.customer_id,
        iban=r.iban,
        name=r.name,
        metadata=dict(r.account_metadata or {}),
        id=r.id,
    )


def _entry_to_row(e: JournalEntry) -> JournalEntryRow:
    return JournalEntryRow(
        id=e.id,
        bank_id=e.bank_id,
        description=e.description,
        reference=e.reference,
        booked_at=e.booked_at,
        postings=[
            {
                "account_id": p.account_id,
                "minor_units": p.amount.minor_units,
                "currency": p.amount.currency,
            }
            for p in e.postings
        ],
        entry_metadata=dict(e.metadata),
    )


def _row_to_entry(r: JournalEntryRow) -> JournalEntry:
    postings = [
        Posting(
            account_id=p["account_id"],
            amount=Money(p["minor_units"], p["currency"]),
        )
        for p in (r.postings or [])
    ]
    return JournalEntry(
        bank_id=r.bank_id,
        postings=postings,
        description=r.description or "",
        reference=r.reference,
        id=r.id,
        booked_at=r.booked_at,
        metadata=dict(r.entry_metadata or {}),
    )


class SqlCoreBankingRepository:
    """Persistent :class:`~banksym.core.service.repository.CoreBankingRepository`."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def add_customer(self, customer: Customer) -> None:
        with self._sf.begin() as s:
            s.merge(_customer_to_row(customer))

    def add_customers_and_accounts_bulk(
        self,
        customers: list[Customer],
        accounts: list[Account],
    ) -> None:
        """Insert many customers and accounts in a single transaction."""
        with self._sf.begin() as s:
            for c in customers:
                s.merge(_customer_to_row(c))
            for a in accounts:
                s.merge(_account_to_row(a))

    def count_journal_entries(self, bank_id: str) -> int:
        """Count distinct journal entries (one per transfer) for a bank."""
        with self._sf() as s:
            from sqlalchemy import func
            return s.scalar(
                select(func.count()).select_from(JournalEntryRow).where(
                    JournalEntryRow.bank_id == bank_id
                )
            ) or 0

    def get_customer(self, bank_id: str, customer_id: str) -> Customer | None:
        with self._sf() as s:
            row = s.get(CustomerRow, customer_id)
            if row is None or row.bank_id != bank_id:
                return None
            return _row_to_customer(row)

    def list_customers(self, bank_id: str) -> list[Customer]:
        with self._sf() as s:
            rows = s.scalars(
                select(CustomerRow).where(CustomerRow.bank_id == bank_id)
            ).all()
            return [_row_to_customer(r) for r in rows]

    def add_account(self, account: Account) -> None:
        with self._sf.begin() as s:
            s.merge(_account_to_row(account))

    def get_account(self, bank_id: str, account_id: str) -> Account | None:
        with self._sf() as s:
            row = s.get(AccountRow, account_id)
            if row is None or row.bank_id != bank_id:
                return None
            return _row_to_account(row)

    def list_accounts(
        self,
        bank_id: str,
        customer_id: str | None = None,
        limit: int | None = None,
    ) -> list[Account]:
        with self._sf() as s:
            stmt = (
                select(AccountRow)
                .where(AccountRow.bank_id == bank_id)
                .order_by(AccountRow.id)
            )
            if customer_id is not None:
                stmt = stmt.where(AccountRow.customer_id == customer_id)
            if limit is not None:
                stmt = stmt.limit(max(0, limit))
            return [_row_to_account(r) for r in s.scalars(stmt).all()]

    def add_journal_entry(self, entry: JournalEntry) -> None:
        with self._sf.begin() as s:
            s.add(_entry_to_row(entry))

    def list_journal_entries(
        self, bank_id: str, account_id: str | None = None
    ) -> list[JournalEntry]:
        with self._sf() as s:
            stmt = (
                select(JournalEntryRow)
                .where(JournalEntryRow.bank_id == bank_id)
                .order_by(JournalEntryRow.seq)
            )
            entries = [_row_to_entry(r) for r in s.scalars(stmt).all()]
        if account_id is not None:
            entries = [e for e in entries if account_id in e.account_ids()]
        return entries

    def remove_bank(self, bank_id: str) -> None:
        with self._sf.begin() as s:
            s.execute(delete(CustomerRow).where(CustomerRow.bank_id == bank_id))
            s.execute(delete(AccountRow).where(AccountRow.bank_id == bank_id))
            s.execute(delete(JournalEntryRow).where(JournalEntryRow.bank_id == bank_id))


# -- Credential <-> row -------------------------------------------------------------
def _credential_to_row(c: Credential) -> CredentialRow:
    return CredentialRow(
        id=c.id,
        bank_id=c.bank_id,
        username=c.username,
        secret_hash=c.secret_hash,
        customer_id=c.customer_id,
    )


def _row_to_credential(r: CredentialRow) -> Credential:
    return Credential(
        bank_id=r.bank_id,
        username=r.username,
        secret_hash=r.secret_hash,
        customer_id=r.customer_id,
        id=r.id,
    )


class SqlCredentialStore:
    """Persistent :class:`~banksym.capabilities.auth.base.CredentialStore`."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def add(self, credential: Credential) -> None:
        with self._sf.begin() as s:
            self._delete_existing(s, credential.bank_id, credential.username)
            s.add(_credential_to_row(credential))

    def find(self, bank_id: str, username: str) -> Credential | None:
        with self._sf() as s:
            row = s.scalars(
                select(CredentialRow).where(
                    CredentialRow.bank_id == bank_id,
                    CredentialRow.username == username,
                )
            ).first()
            return _row_to_credential(row) if row else None

    def find_by_customer(self, bank_id: str, customer_id: str) -> Credential | None:
        with self._sf() as s:
            row = s.scalars(
                select(CredentialRow).where(
                    CredentialRow.bank_id == bank_id,
                    CredentialRow.customer_id == customer_id,
                )
            ).first()
            return _row_to_credential(row) if row else None

    def list_by_bank(self, bank_id: str) -> dict[str, Credential]:
        """Fetch all credentials for a bank in one query; return dict keyed by customer_id."""
        with self._sf() as s:
            rows = s.scalars(
                select(CredentialRow).where(CredentialRow.bank_id == bank_id)
            ).all()
            return {r.customer_id: _row_to_credential(r) for r in rows if r.customer_id}

    def purge(self, bank_id: str) -> None:
        with self._sf.begin() as s:
            s.execute(delete(CredentialRow).where(CredentialRow.bank_id == bank_id))

    @staticmethod
    def _delete_existing(s: Session, bank_id: str, username: str) -> None:
        s.execute(
            delete(CredentialRow).where(
                CredentialRow.bank_id == bank_id,
                CredentialRow.username == username,
            )
        )


__all__ = [
    "SqlBankRepository",
    "SqlCoreBankingRepository",
    "SqlCredentialStore",
]
