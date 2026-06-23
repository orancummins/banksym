"""Account entity."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from banksym.core.kernel.ids import new_id


class AccountType(enum.StrEnum):
    CURRENT = "current"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    # Internal bank accounts used by the ledger / settlement.
    INTERNAL = "internal"
    NOSTRO = "nostro"
    VOSTRO = "vostro"
    SETTLEMENT = "settlement"


class AccountStatus(enum.StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    CLOSED = "closed"


@dataclass(slots=True)
class Account:
    """A ledger account. Customer-facing accounts reference a ``customer_id``; internal
    accounts (settlement, nostro/vostro) do not."""

    bank_id: str
    currency: str
    type: AccountType = AccountType.CURRENT
    status: AccountStatus = AccountStatus.ACTIVE
    customer_id: str | None = None
    iban: str | None = None
    name: str | None = None
    id: str = field(default_factory=lambda: new_id("acc_"))

    @property
    def is_internal(self) -> bool:
        return self.type in (
            AccountType.INTERNAL,
            AccountType.NOSTRO,
            AccountType.VOSTRO,
            AccountType.SETTLEMENT,
        )
