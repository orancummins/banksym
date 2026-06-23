"""Transaction history record — a per-account, ledger-derived view.

Transaction history is *derived* from journal postings, not a separate source of truth. Each
record is one posting as seen from a single account's perspective, with the running balance after
the posting was applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from banksym.core.domain.ledger import PostingSide
from banksym.core.kernel.money import Money


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    """One account-facing line of transaction history."""

    account_id: str
    journal_id: str
    amount: Money
    balance_after: Money
    side: PostingSide
    booked_at: datetime
    description: str = ""
    reference: str | None = None
