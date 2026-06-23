"""Real-Time Gross Settlement (RTGS) engine.

Each instruction is settled individually and immediately, gross (no netting), against an internal
settlement account that stands in for the central-bank/clearing leg. If the debtor lacks funds the
instruction is rejected rather than queued.
"""

from __future__ import annotations

from banksym.capabilities.settlement.base import (
    SettlementEngine,
    SettlementInstruction,
    SettlementResult,
    SettlementStatus,
    settlement_registry,
)
from banksym.core.domain.account import Account, AccountType
from banksym.core.kernel.errors import InsufficientFundsError

_SETTLEMENT_ACCOUNT_NAME = "RTGS settlement"


@settlement_registry.register
class RtgsSettlementEngine(SettlementEngine):
    capability_name = "rtgs"
    engine_title = "Real-Time Gross Settlement"

    def settle(self, instruction: SettlementInstruction) -> SettlementResult:
        settlement_account = self._settlement_account(
            instruction.bank_id, instruction.amount.currency
        )
        description = instruction.reference or (
            f"Payment to {instruction.creditor_name or instruction.creditor_iban or 'creditor'}"
        )
        try:
            entry = self.banking.transfer(
                instruction.bank_id,
                instruction.debtor_account_id,
                settlement_account.id,
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

    def _settlement_account(self, bank_id: str, currency: str) -> Account:
        for account in self.banking.list_accounts(bank_id):
            if (
                account.type == AccountType.SETTLEMENT
                and account.currency == currency
                and account.name == _SETTLEMENT_ACCOUNT_NAME
            ):
                return account
        return self.banking.open_account(
            bank_id,
            currency,
            type=AccountType.SETTLEMENT,
            name=_SETTLEMENT_ACCOUNT_NAME,
        )
