"""Settlement capability — moves value for an initiated payment via a settlement strategy.

A :class:`SettlementEngine` takes a protocol-neutral :class:`SettlementInstruction` and books the
corresponding ledger movements through :class:`~banksym.core.service.CoreBankingService`. Different
strategies (real-time gross settlement, batch netting, inter-bank nostro/vostro) implement the same
interface, so a bank selects whichever model it wants to simulate.
"""

from banksym.capabilities.settlement.base import (
    SettlementEngine,
    SettlementInstruction,
    SettlementResult,
    SettlementStatus,
    settlement_registry,
)

__all__ = [
    "SettlementEngine",
    "SettlementInstruction",
    "SettlementResult",
    "SettlementStatus",
    "settlement_registry",
]
