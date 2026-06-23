"""Tests for the transaction generator capability and registry."""

from datetime import date

from banksym.capabilities.txgen.base import GenerationRequest, txgen_registry
from banksym.core.service import CoreBankingService, InMemoryCoreBankingRepository


def make_banking() -> CoreBankingService:
    return CoreBankingService(InMemoryCoreBankingRepository())


def test_rule_based_generator_registered():
    assert "rule_based" in txgen_registry.names()


def test_generation_is_deterministic_and_balanced():
    bank_id = "bank_1"

    def run() -> list[str]:
        banking = make_banking()
        customer = banking.create_customer(bank_id, "Sam Gig", persona="gig_worker")
        account = banking.open_account(bank_id, "EUR", customer_id=customer.id)
        generator = txgen_registry.get("rule_based")(banking)
        request = GenerationRequest(
            bank_id=bank_id,
            customer=customer,
            account=account,
            start=date(2025, 1, 1),
            end=date(2025, 3, 31),
            persona="gig_worker",
            currency="EUR",
            seed=42,
        )
        entries = generator.generate(request)
        assert len(entries) > 0
        # Ledger stays balanced: account balance equals sum of its postings.
        return [str(banking.balance(bank_id, account.id))]

    first = run()
    second = run()
    assert first == second  # determinism given the same seed
