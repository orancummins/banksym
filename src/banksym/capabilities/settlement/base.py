"""SettlementEngine interface + registry."""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field

from banksym.core.kernel.ids import new_id
from banksym.core.kernel.money import Money
from banksym.core.kernel.registry import Capability, CapabilityRegistry
from banksym.core.service import CoreBankingService

CAPABILITY_KIND = "settlement"


class SettlementStatus(enum.StrEnum):
    SETTLED = "settled"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass(slots=True)
class SettlementInstruction:
    """A protocol-neutral request to settle one outbound payment."""

    bank_id: str
    debtor_account_id: str
    amount: Money
    creditor_name: str | None = None
    creditor_iban: str | None = None
    reference: str | None = None
    id: str = field(default_factory=lambda: new_id("settle_"))


@dataclass(slots=True)
class SettlementResult:
    instruction_id: str
    status: SettlementStatus
    journal_id: str | None = None
    detail: str = ""


class SettlementEngine(Capability, abc.ABC):
    """Books the ledger movements required to settle a payment."""

    capability_kind = CAPABILITY_KIND
    engine_title: str = ""

    def __init__(self, banking: CoreBankingService) -> None:
        self.banking = banking

    @abc.abstractmethod
    def settle(self, instruction: SettlementInstruction) -> SettlementResult:
        """Attempt to settle the instruction; return the outcome."""
        raise NotImplementedError

    def run_cycle(self, bank_id: str) -> list[SettlementResult]:
        """Run a deferred settlement cycle for a bank.

        Immediate engines (e.g. RTGS) settle on :meth:`settle` and have nothing to do here, so the
        default returns an empty list. Deferred engines (e.g. netting) override this to clear queued
        positions and return one result per settled batch.
        """
        return []


settlement_registry: CapabilityRegistry[SettlementEngine] = CapabilityRegistry(CAPABILITY_KIND)
