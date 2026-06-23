"""CoreBankingService — the only public surface plugins use to read/mutate banking state."""

from __future__ import annotations

from datetime import date

from banksym.core.domain.account import Account, AccountType
from banksym.core.domain.customer import Customer
from banksym.core.domain.ledger import JournalEntry, Posting
from banksym.core.domain.transaction import TransactionRecord
from banksym.core.kernel.errors import (
    AccountNotFoundError,
    CustomerNotFoundError,
    InsufficientFundsError,
)
from banksym.core.kernel.money import Money
from banksym.core.service.repository import CoreBankingRepository


class CoreBankingService:
    """Tenant-aware facade over customers, accounts, the ledger, and transaction history.

    Every method takes an explicit ``bank_id`` so all state is isolated per tenant. This is the
    single interface that pluggable capabilities (protocol adapters, generators, settlement, ...)
    are allowed to depend on.
    """

    def __init__(self, repository: CoreBankingRepository) -> None:
        self._repo = repository

    # -- Customers -----------------------------------------------------------------
    def create_customer(
        self,
        bank_id: str,
        full_name: str,
        *,
        email: str | None = None,
        phone: str | None = None,
        date_of_birth: date | None = None,
        country: str | None = None,
        address: str | None = None,
        persona: str | None = None,
    ) -> Customer:
        customer = Customer(
            bank_id=bank_id,
            full_name=full_name,
            email=email,
            phone=phone,
            date_of_birth=date_of_birth,
            country=country,
            address=address,
            persona=persona,
        )
        self._repo.add_customer(customer)
        return customer

    def get_customer(self, bank_id: str, customer_id: str) -> Customer:
        customer = self._repo.get_customer(bank_id, customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    def list_customers(self, bank_id: str) -> list[Customer]:
        return self._repo.list_customers(bank_id)

    # -- Accounts ------------------------------------------------------------------
    def open_account(
        self,
        bank_id: str,
        currency: str,
        *,
        customer_id: str | None = None,
        type: AccountType = AccountType.CURRENT,
        iban: str | None = None,
        name: str | None = None,
    ) -> Account:
        if customer_id is not None and self._repo.get_customer(bank_id, customer_id) is None:
            raise CustomerNotFoundError(customer_id)
        account = Account(
            bank_id=bank_id,
            currency=currency,
            customer_id=customer_id,
            type=type,
            iban=iban,
            name=name,
        )
        self._repo.add_account(account)
        return account

    def get_account(self, bank_id: str, account_id: str) -> Account:
        account = self._repo.get_account(bank_id, account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    def list_accounts(self, bank_id: str, customer_id: str | None = None) -> list[Account]:
        return self._repo.list_accounts(bank_id, customer_id)

    def ensure_internal_account(
        self, bank_id: str, currency: str, type: AccountType, name: str
    ) -> Account:
        """Find or create a named internal account (settlement, suspense, nostro/vostro...).

        Internal accounts have no customer and are looked up by ``(type, currency, name)`` so
        capabilities can reliably reuse the same account across requests.
        """
        for account in self._repo.list_accounts(bank_id):
            if (
                account.is_internal
                and account.type == type
                and account.currency == currency
                and account.name == name
            ):
                return account
        return self.open_account(bank_id, currency, type=type, name=name)

    # -- Ledger --------------------------------------------------------------------
    def post_journal_entry(self, entry: JournalEntry) -> JournalEntry:
        """Validate referenced accounts exist with matching currency, then persist the entry.

        The entry's own debits==credits invariant is enforced in :meth:`JournalEntry.validate`.
        """
        for posting in entry.postings:
            account = self._repo.get_account(entry.bank_id, posting.account_id)
            if account is None:
                raise AccountNotFoundError(posting.account_id)
            if account.currency != posting.amount.currency:
                raise InsufficientFundsError(
                    f"Posting currency {posting.amount.currency} != account currency "
                    f"{account.currency} for {account.id}"
                )
        self._repo.add_journal_entry(entry)
        return entry

    def transfer(
        self,
        bank_id: str,
        from_account_id: str,
        to_account_id: str,
        amount: Money,
        *,
        description: str = "",
        reference: str | None = None,
        allow_overdraft: bool = False,
    ) -> JournalEntry:
        """Move ``amount`` between two accounts via a balanced two-leg journal entry."""
        if not amount.is_positive:
            raise ValueError("Transfer amount must be positive")
        source = self.get_account(bank_id, from_account_id)
        self.get_account(bank_id, to_account_id)
        if not allow_overdraft and not source.is_internal:
            current = self.balance(bank_id, from_account_id)
            if (current - amount).is_negative:
                raise InsufficientFundsError(
                    f"Account {from_account_id} balance {current} < {amount}"
                )
        entry = JournalEntry(
            bank_id=bank_id,
            description=description,
            reference=reference,
            postings=[
                Posting(account_id=from_account_id, amount=-amount),
                Posting(account_id=to_account_id, amount=amount),
            ],
        )
        return self.post_journal_entry(entry)

    def balance(self, bank_id: str, account_id: str) -> Money:
        account = self.get_account(bank_id, account_id)
        total = Money.zero(account.currency)
        for entry in self._repo.list_journal_entries(bank_id, account_id):
            for posting in entry.postings:
                if posting.account_id == account_id:
                    total = total + posting.amount
        return total

    def transaction_history(
        self, bank_id: str, account_id: str
    ) -> list[TransactionRecord]:
        account = self.get_account(bank_id, account_id)
        entries = sorted(
            self._repo.list_journal_entries(bank_id, account_id),
            key=lambda e: e.booked_at,
        )
        running = Money.zero(account.currency)
        records: list[TransactionRecord] = []
        for entry in entries:
            for posting in entry.postings:
                if posting.account_id != account_id:
                    continue
                running = running + posting.amount
                records.append(
                    TransactionRecord(
                        account_id=account_id,
                        journal_id=entry.id,
                        amount=posting.amount,
                        balance_after=running,
                        side=posting.side,
                        booked_at=entry.booked_at,
                        description=entry.description,
                        reference=entry.reference,
                    )
                )
        return records
