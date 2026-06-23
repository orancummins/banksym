"""Tests for ledger invariants and core banking operations."""

import pytest

from banksym.core.domain.account import AccountType
from banksym.core.domain.ledger import JournalEntry, Posting
from banksym.core.kernel.errors import (
    AccountNotFoundError,
    InsufficientFundsError,
    UnbalancedEntryError,
)
from banksym.core.kernel.money import Money
from banksym.core.service import CoreBankingService, InMemoryCoreBankingRepository


@pytest.fixture
def banking() -> CoreBankingService:
    return CoreBankingService(InMemoryCoreBankingRepository())


def test_unbalanced_entry_rejected():
    with pytest.raises(UnbalancedEntryError):
        JournalEntry(
            bank_id="bank_1",
            postings=[
                Posting("acc_a", Money(100, "EUR")),
                Posting("acc_b", Money(-50, "EUR")),
            ],
        )


def test_single_posting_rejected():
    with pytest.raises(UnbalancedEntryError):
        JournalEntry(bank_id="bank_1", postings=[Posting("acc_a", Money(0, "EUR"))])


def test_transfer_moves_funds_and_balances(banking: CoreBankingService):
    bank_id = "bank_1"
    funding = banking.open_account(bank_id, "EUR", type=AccountType.INTERNAL, name="Funding")
    customer = banking.create_customer(bank_id, "Ada Lovelace")
    acct = banking.open_account(bank_id, "EUR", customer_id=customer.id)

    banking.transfer(bank_id, funding.id, acct.id, Money.from_decimal("100.00", "EUR"))

    assert banking.balance(bank_id, acct.id) == Money.from_decimal("100.00", "EUR")
    assert banking.balance(bank_id, funding.id) == Money.from_decimal("-100.00", "EUR")


def test_transfer_insufficient_funds(banking: CoreBankingService):
    bank_id = "bank_1"
    customer = banking.create_customer(bank_id, "Grace Hopper")
    a = banking.open_account(bank_id, "EUR", customer_id=customer.id)
    b = banking.open_account(bank_id, "EUR", customer_id=customer.id)
    with pytest.raises(InsufficientFundsError):
        banking.transfer(bank_id, a.id, b.id, Money.from_decimal("10.00", "EUR"))


def test_post_journal_unknown_account(banking: CoreBankingService):
    entry = JournalEntry(
        bank_id="bank_1",
        postings=[
            Posting("acc_missing_a", Money(100, "EUR")),
            Posting("acc_missing_b", Money(-100, "EUR")),
        ],
    )
    with pytest.raises(AccountNotFoundError):
        banking.post_journal_entry(entry)


def test_transaction_history_running_balance(banking: CoreBankingService):
    bank_id = "bank_1"
    funding = banking.open_account(bank_id, "EUR", type=AccountType.INTERNAL)
    acct = banking.open_account(bank_id, "EUR")
    banking.transfer(bank_id, funding.id, acct.id, Money.from_decimal("100.00", "EUR"))
    banking.transfer(
        bank_id, acct.id, funding.id, Money.from_decimal("30.00", "EUR")
    )
    history = banking.transaction_history(bank_id, acct.id)
    assert [str(r.balance_after) for r in history] == ["100.00 EUR", "70.00 EUR"]


def test_tenant_isolation(banking: CoreBankingService):
    a = banking.create_customer("bank_a", "Customer A")
    banking.create_customer("bank_b", "Customer B")
    assert [c.id for c in banking.list_customers("bank_a")] == [a.id]
    assert banking.get_customer("bank_a", a.id).full_name == "Customer A"
