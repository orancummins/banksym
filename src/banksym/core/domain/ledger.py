"""Double-entry ledger primitives.

A :class:`JournalEntry` is an atomic, balanced set of :class:`Posting` rows. Each posting carries
a *signed* :class:`Money` amount representing the balance delta applied to its account: a positive
amount credits the account, a negative amount debits it. The core invariant is that, for every
currency in an entry, the signed amounts net to exactly zero (total debits == total credits).
"""

from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from banksym.core.kernel.errors import UnbalancedEntryError
from banksym.core.kernel.ids import new_id
from banksym.core.kernel.money import Money


class PostingSide(enum.StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


@dataclass(frozen=True, slots=True)
class Posting:
    """A single leg of a journal entry. ``amount`` is the signed balance delta to ``account_id``."""

    account_id: str
    amount: Money

    @property
    def side(self) -> PostingSide:
        return PostingSide.CREDIT if self.amount.is_positive else PostingSide.DEBIT


@dataclass(slots=True)
class JournalEntry:
    """An atomic, balanced group of postings."""

    bank_id: str
    postings: list[Posting]
    description: str = ""
    reference: str | None = None
    id: str = field(default_factory=lambda: new_id("jnl_"))
    booked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise :class:`UnbalancedEntryError` unless every currency nets to zero."""
        if len(self.postings) < 2:
            raise UnbalancedEntryError("A journal entry needs at least two postings")
        totals: dict[str, int] = defaultdict(int)
        for posting in self.postings:
            totals[posting.amount.currency] += posting.amount.minor_units
        unbalanced = {cur: total for cur, total in totals.items() if total != 0}
        if unbalanced:
            raise UnbalancedEntryError(f"Entry does not balance per currency: {unbalanced}")

    def account_ids(self) -> set[str]:
        return {p.account_id for p in self.postings}
