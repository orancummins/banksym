"""Protocol-neutral payment state, shared across protocol adapters.

Like consents, payments carry SCA authorisation sub-resources. Statuses use the Berlin Group
``transactionStatus`` vocabulary so adapters can surface them directly.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from banksym.capabilities.protocols.base.consent import Authorisation
from banksym.core.kernel.ids import new_id
from banksym.core.kernel.money import Money


class PaymentStatus(enum.StrEnum):
    """Berlin Group transactionStatus values used by the test bank."""

    RECEIVED = "RCVD"
    ACCEPTED_TECHNICAL_VALIDATION = "ACTC"
    ACCEPTED_SETTLEMENT_COMPLETED = "ACSC"
    REJECTED = "RJCT"
    CANCELLED = "CANC"


@dataclass(slots=True)
class Payment:
    """An initiated credit transfer and its authorisation/settlement state."""

    bank_id: str
    payment_product: str
    debtor_account_id: str
    amount: Money
    creditor_iban: str | None = None
    creditor_name: str | None = None
    remittance: str | None = None
    end_to_end_id: str | None = None
    status: PaymentStatus = PaymentStatus.RECEIVED
    id: str = field(default_factory=lambda: new_id("pmt_"))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    authorisations: dict[str, Authorisation] = field(default_factory=dict)
    settlement_journal_id: str | None = None


class PaymentStore(Protocol):
    """Storage contract for payments, scoped by ``bank_id``."""

    def add(self, payment: Payment) -> None: ...

    def get(self, bank_id: str, payment_id: str) -> Payment | None: ...

    def list(self, bank_id: str) -> list[Payment]: ...

    def save(self, payment: Payment) -> None: ...

    def purge(self, bank_id: str) -> None: ...


class InMemoryPaymentStore:
    def __init__(self) -> None:
        self._payments: dict[tuple[str, str], Payment] = {}

    def add(self, payment: Payment) -> None:
        self._payments[(payment.bank_id, payment.id)] = payment

    def get(self, bank_id: str, payment_id: str) -> Payment | None:
        return self._payments.get((bank_id, payment_id))

    def list(self, bank_id: str) -> list[Payment]:
        return [p for (b, _), p in self._payments.items() if b == bank_id]

    def save(self, payment: Payment) -> None:
        self._payments[(payment.bank_id, payment.id)] = payment

    def purge(self, bank_id: str) -> None:
        self._payments = {
            key: p for key, p in self._payments.items() if key[0] != bank_id
        }
