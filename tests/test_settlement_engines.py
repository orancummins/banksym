"""Unit tests for the netting and inter-bank settlement engines."""

# Import for self-registration.
import pytest

import banksym.capabilities.settlement.interbank  # noqa: F401
import banksym.capabilities.settlement.netting  # noqa: F401
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


def _funded_debtor(banking: CoreBankingService, bank_id: str, amount: str) -> str:
    funding = banking.open_account(bank_id, "EUR", type=AccountType.INTERNAL)
    customer = banking.create_customer(bank_id, "Payer")
    debtor = banking.open_account(bank_id, "EUR", customer_id=customer.id)
    banking.transfer(bank_id, funding.id, debtor.id, Money.from_decimal(amount, "EUR"))
    return debtor.id


def test_engines_registered():
    names = settlement_registry.names()
    assert "netting" in names
    assert "interbank" in names


def test_netting_defers_then_settles_on_cycle(banking: CoreBankingService):
    bank_id = "bank_1"
    debtor_id = _funded_debtor(banking, bank_id, "500.00")
    engine = settlement_registry.get("netting")(banking)

    result = engine.settle(
        SettlementInstruction(
            bank_id=bank_id,
            debtor_account_id=debtor_id,
            amount=Money.from_decimal("120.00", "EUR"),
            reference="inv-1",
        )
    )
    assert result.status == SettlementStatus.PENDING
    # Debtor already debited into suspense.
    assert banking.balance(bank_id, debtor_id) == Money.from_decimal("380.00", "EUR")

    cycle = engine.run_cycle(bank_id)
    assert len(cycle) == 1
    assert cycle[0].status == SettlementStatus.SETTLED

    # Net settlement account holds the swept position.
    settlement = next(
        a
        for a in banking.list_accounts(bank_id)
        if a.type == AccountType.SETTLEMENT and a.name == "Net settlement"
    )
    assert banking.balance(bank_id, settlement.id) == Money.from_decimal("120.00", "EUR")


def test_netting_rejects_insufficient_funds(banking: CoreBankingService):
    bank_id = "bank_1"
    customer = banking.create_customer(bank_id, "Broke")
    debtor = banking.open_account(bank_id, "EUR", customer_id=customer.id)
    engine = settlement_registry.get("netting")(banking)
    result = engine.settle(
        SettlementInstruction(
            bank_id=bank_id,
            debtor_account_id=debtor.id,
            amount=Money.from_decimal("10.00", "EUR"),
        )
    )
    assert result.status == SettlementStatus.REJECTED


def test_interbank_settles_to_nostro(banking: CoreBankingService):
    bank_id = "bank_1"
    debtor_id = _funded_debtor(banking, bank_id, "300.00")
    engine = settlement_registry.get("interbank")(banking)
    result = engine.settle(
        SettlementInstruction(
            bank_id=bank_id,
            debtor_account_id=debtor_id,
            amount=Money.from_decimal("75.00", "EUR"),
            creditor_iban="DE00OTHERBANK",
        )
    )
    assert result.status == SettlementStatus.SETTLED
    nostro = next(
        a for a in banking.list_accounts(bank_id) if a.type == AccountType.NOSTRO
    )
    assert banking.balance(bank_id, nostro.id) == Money.from_decimal("75.00", "EUR")


def test_rtgs_run_cycle_is_noop(banking: CoreBankingService):
    engine = settlement_registry.get("rtgs")(banking)
    assert engine.run_cycle("bank_1") == []
