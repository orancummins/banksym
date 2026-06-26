"""Persistence boundary for the core banking domain.

The service depends only on the :class:`CoreBankingRepository` interface; a concrete backend
(in-memory now, SQLAlchemy later) is injected. This keeps the domain free of storage concerns.
"""

from __future__ import annotations

from typing import Protocol

from banksym.core.domain.account import Account
from banksym.core.domain.customer import Customer
from banksym.core.domain.ledger import JournalEntry


class CoreBankingRepository(Protocol):
    """Storage contract for core banking entities. All reads are scoped by ``bank_id``."""

    def add_customer(self, customer: Customer) -> None: ...

    def get_customer(self, bank_id: str, customer_id: str) -> Customer | None: ...

    def list_customers(self, bank_id: str) -> list[Customer]: ...

    def add_account(self, account: Account) -> None: ...

    def get_account(self, bank_id: str, account_id: str) -> Account | None: ...

    def list_accounts(
        self,
        bank_id: str,
        customer_id: str | None = None,
        limit: int | None = None,
    ) -> list[Account]: ...

    def add_journal_entry(self, entry: JournalEntry) -> None: ...

    def list_journal_entries(
        self, bank_id: str, account_id: str | None = None
    ) -> list[JournalEntry]: ...

    def remove_bank(self, bank_id: str) -> None: ...


class InMemoryCoreBankingRepository:
    """A simple in-memory backend, primarily for tests and local runs."""

    def __init__(self) -> None:
        self._customers: dict[tuple[str, str], Customer] = {}
        self._accounts: dict[tuple[str, str], Account] = {}
        self._journals: list[JournalEntry] = []

    def add_customer(self, customer: Customer) -> None:
        self._customers[(customer.bank_id, customer.id)] = customer

    def get_customer(self, bank_id: str, customer_id: str) -> Customer | None:
        return self._customers.get((bank_id, customer_id))

    def list_customers(self, bank_id: str) -> list[Customer]:
        return [c for (b, _), c in self._customers.items() if b == bank_id]

    def add_account(self, account: Account) -> None:
        self._accounts[(account.bank_id, account.id)] = account

    def get_account(self, bank_id: str, account_id: str) -> Account | None:
        return self._accounts.get((bank_id, account_id))

    def list_accounts(
        self,
        bank_id: str,
        customer_id: str | None = None,
        limit: int | None = None,
    ) -> list[Account]:
        accounts = [a for (b, _), a in self._accounts.items() if b == bank_id]
        if customer_id is not None:
            accounts = [a for a in accounts if a.customer_id == customer_id]
        if limit is not None:
            accounts = accounts[: max(0, limit)]
        return accounts

    def add_journal_entry(self, entry: JournalEntry) -> None:
        self._journals.append(entry)

    def list_journal_entries(
        self, bank_id: str, account_id: str | None = None
    ) -> list[JournalEntry]:
        entries = [e for e in self._journals if e.bank_id == bank_id]
        if account_id is not None:
            entries = [e for e in entries if account_id in e.account_ids()]
        return entries

    def remove_bank(self, bank_id: str) -> None:
        self._customers = {
            key: c for key, c in self._customers.items() if key[0] != bank_id
        }
        self._accounts = {
            key: a for key, a in self._accounts.items() if key[0] != bank_id
        }
        self._journals = [e for e in self._journals if e.bank_id != bank_id]
