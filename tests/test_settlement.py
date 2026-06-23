"""Unit tests for the RTGS settlement engine."""

import pytest

from banksym.capabilities.settlement.base import (
    SettlementInstruction,
    SettlementStatus,
    settlement_registry,
)
from banksym.core.domain.account import AccountType
from banksym.core.kernel.money import Money
from banksym.core.service import CoreBankingService, InMemoryCoreBankingRepository


@pytest.fixture
def banking() -> CoreBankingService:
    return CoreBankingService(InMemoryCoreBankingRepository())


def test_rtgs_registered():
    assert "rtgs" in settlement_registry.names()


def test_rtgs_settles_and_debits_account(banking: CoreBankingService):
    bank_id = "bank_1"
    funding = banking.open_account(bank_id, "EUR", type=AccountType.INTERNAL)
    customer = banking.create_customer(bank_id, "Payer")
    debtor = banking.open_account(bank_id, "EUR", customer_id=customer.id)
    banking.transfer(bank_id, funding.id, debtor.id, Money.from_decimal("500.00", "EUR"))

    engine = settlement_registry.get("rtgs")(banking)
    result = engine.settle(
        SettlementInstruction(
            bank_id=bank_id,
            debtor_account_id=debtor.id,
            amount=Money.from_decimal("120.00", "EUR"),
            creditor_name="Acme",
            reference="invoice-1",
        )
    )

    assert result.status == SettlementStatus.SETTLED
    assert result.journal_id is not None
    assert banking.balance(bank_id, debtor.id) == Money.from_decimal("380.00", "EUR")


def test_rtgs_rejects_insufficient_funds(banking: CoreBankingService):
    bank_id = "bank_1"
    customer = banking.create_customer(bank_id, "Broke")
    debtor = banking.open_account(bank_id, "EUR", customer_id=customer.id)
    engine = settlement_registry.get("rtgs")(banking)
    result = engine.settle(
        SettlementInstruction(
            bank_id=bank_id,
            debtor_account_id=debtor.id,
            amount=Money.from_decimal("50.00", "EUR"),
        )
    )
    assert result.status == SettlementStatus.REJECTED
    assert result.journal_id is None
