"""Inter-bank (correspondent) settlement engine.

Settles outbound payments across bank boundaries via a correspondent relationship: the debtor is
debited and the bank's NOSTRO account (its balance held at the correspondent) is credited,
representing the cover moving through the correspondent. Settlement is immediate and gross.
"""

from __future__ import annotations

from banksym.capabilities.settlement.base import (
    SettlementEngine,
    SettlementInstruction,
    SettlementResult,
    SettlementStatus,
    settlement_registry,
)
from banksym.core.domain.account import AccountType
from banksym.core.kernel.errors import InsufficientFundsError

_NOSTRO_NAME = "Correspondent NOSTRO"


@settlement_registry.register
class InterBankSettlementEngine(SettlementEngine):
    capability_name = "interbank"
    engine_title = "Inter-bank Correspondent Settlement"

    def settle(self, instruction: SettlementInstruction) -> SettlementResult:
        nostro = self.banking.ensure_internal_account(
            instruction.bank_id,
            instruction.amount.currency,
            AccountType.NOSTRO,
            _NOSTRO_NAME,
        )
        creditor = instruction.creditor_name or instruction.creditor_iban or "creditor"
        description = instruction.reference or f"Correspondent payment to {creditor}"
        try:
            entry = self.banking.transfer(
                instruction.bank_id,
                instruction.debtor_account_id,
                nostro.id,
                instruction.amount,
                description=description,
                reference=instruction.reference,
            )
        except InsufficientFundsError as exc:
            return SettlementResult(
                instruction_id=instruction.id,
                status=SettlementStatus.REJECTED,
                detail=str(exc),
            )
        return SettlementResult(
            instruction_id=instruction.id,
            status=SettlementStatus.SETTLED,
            journal_id=entry.id,
        )
