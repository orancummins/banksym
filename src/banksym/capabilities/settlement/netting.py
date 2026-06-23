"""Deferred net settlement (DNS) engine.

Instructions are *not* settled immediately. Each payment debits the debtor and credits an internal
netting *suspense* account, returning ``PENDING``. A later settlement cycle (:meth:`run_cycle`)
nets the accumulated positions: the suspense balance per currency is swept into the final
settlement account in a single movement, mimicking end-of-day net settlement.
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

_SUSPENSE_NAME = "Netting suspense"
_SETTLEMENT_NAME = "Net settlement"


@settlement_registry.register
class BatchNettingSettlementEngine(SettlementEngine):
    capability_name = "netting"
    engine_title = "Deferred Net Settlement"

    def settle(self, instruction: SettlementInstruction) -> SettlementResult:
        suspense = self.banking.ensure_internal_account(
            instruction.bank_id,
            instruction.amount.currency,
            AccountType.SETTLEMENT,
            _SUSPENSE_NAME,
        )
        creditor = instruction.creditor_name or instruction.creditor_iban or "creditor"
        description = instruction.reference or f"Queued payment to {creditor}"
        try:
            entry = self.banking.transfer(
                instruction.bank_id,
                instruction.debtor_account_id,
                suspense.id,
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
            status=SettlementStatus.PENDING,
            journal_id=entry.id,
        )

    def run_cycle(self, bank_id: str) -> list[SettlementResult]:
        results: list[SettlementResult] = []
        for account in self.banking.list_accounts(bank_id):
            if not (
                account.type == AccountType.SETTLEMENT and account.name == _SUSPENSE_NAME
            ):
                continue
            balance = self.banking.balance(bank_id, account.id)
            if balance.minor_units <= 0:
                continue
            settlement = self.banking.ensure_internal_account(
                bank_id, balance.currency, AccountType.SETTLEMENT, _SETTLEMENT_NAME
            )
            entry = self.banking.transfer(
                bank_id,
                account.id,
                settlement.id,
                balance,
                description=f"Net settlement sweep ({balance.currency})",
            )
            results.append(
                SettlementResult(
                    instruction_id=f"cycle:{balance.currency}",
                    status=SettlementStatus.SETTLED,
                    journal_id=entry.id,
                    detail=f"Swept {balance.currency} net position",
                )
            )
        return results
