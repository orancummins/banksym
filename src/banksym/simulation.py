"""Server-side live transaction simulator.

The simulator runs as a long-lived asyncio task inside the API process, so it keeps generating
transactions regardless of whether any browser tab is open. The Live UI merely starts/stops it and
polls a rolling feed of the most recent events (capped at :data:`_MAX_EVENTS`). Manual transactions
posted through the banking API are recorded into the same feed for a consistent picture.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import threading
from collections import deque
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from banksym.capabilities.localization.base import resolve_pack

if TYPE_CHECKING:
    from banksym.api.container import Container
    from banksym.core.domain.transaction import TransactionRecord

_MAX_EVENTS = 200

# Plausible counterparties for synthesised live transactions.
_MERCHANTS = (
    "Coffee shop",
    "Supermarket",
    "Online store",
    "Fuel station",
    "Pharmacy",
    "Restaurant",
    "Card payment",
    "ATM withdrawal",
    "Subscription",
    "Utility bill",
    "Transfer",
    "Salary",
    "Refund",
    "Mobile top-up",
    "Insurance",
    "Taxi",
)


class SimulationEngine:
    """Drives randomised transactions across selected accounts and keeps a rolling event feed."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._rng = random.Random()
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
        self._seq = 0
        self._targets: list[tuple[str, str]] = []
        self.running = False
        self.avg_seconds = 3.0
        self.generated = 0
        self._task: asyncio.Task[None] | None = None

    # -- Control -----------------------------------------------------------------
    async def start(self, avg_seconds: float, targets: list[tuple[str, str]]) -> None:
        """Start the simulation (or update its cadence/targets if already running)."""
        self.avg_seconds = max(0.1, float(avg_seconds))
        with self._lock:
            self._targets = list(targets)
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the simulation and cancel its background task."""
        self.running = False
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # -- Introspection -----------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._lock:
            target_count = len(self._targets)
            last_seq = self._seq
        return {
            "running": self.running,
            "avg_seconds": self.avg_seconds,
            "target_count": target_count,
            "generated": self.generated,
            "last_seq": last_seq,
        }

    def targets(self) -> list[tuple[str, str]]:
        """Return a snapshot of configured simulation targets as ``(bank_id, account_id)``."""
        with self._lock:
            return list(self._targets)

    def feed(self, after: int = 0, limit: int = _MAX_EVENTS) -> dict[str, Any]:
        """Return events with ``seq > after`` (oldest first), plus current status."""
        limit = max(1, min(limit, _MAX_EVENTS))
        with self._lock:
            events = [e for e in self._events if e["seq"] > after][-limit:]
            last_seq = self._seq
        return {
            "running": self.running,
            "generated": self.generated,
            "last_seq": last_seq,
            "events": events,
        }

    # -- Recording ---------------------------------------------------------------
    def record_manual(
        self, bank_id: str, account_id: str, record: TransactionRecord
    ) -> None:
        """Record a manually triggered transaction into the live feed."""
        self._record(bank_id, account_id, record, "manual")

    def _record(
        self, bank_id: str, account_id: str, record: TransactionRecord, kind: str
    ) -> None:
        bank_name, bank_color, country = bank_id, "#0B5FFF", ""
        try:
            bank = self._container.bank_service.get_bank(bank_id)
            bank_name, bank_color, country = (
                bank.branding.display_name,
                bank.branding.primary_color,
                bank.country,
            )
        except Exception:
            pass
        iban: str | None = None
        customer_name = ""
        try:
            account = self._container.banking.get_account(bank_id, account_id)
            iban = account.iban
            if account.customer_id:
                customer_name = self._container.banking.get_customer(
                    bank_id, account.customer_id
                ).full_name
        except Exception:
            pass
        with self._lock:
            self._seq += 1
            self._events.append(
                {
                    "seq": self._seq,
                    "kind": kind,
                    "bank_id": bank_id,
                    "bank_name": bank_name,
                    "bank_color": bank_color,
                    "country": country,
                    "account_id": account_id,
                    "iban": iban,
                    "customer_name": customer_name,
                    "amount": str(record.amount),
                    "side": record.side.value,
                    "balance_after": str(record.balance_after),
                    "description": record.description,
                    "booked_at": record.booked_at,
                }
            )

    # -- Loop --------------------------------------------------------------------
    def _next_delay(self) -> float:
        avg = self.avg_seconds
        # Exponential (Poisson) jitter around the chosen average for a natural cadence.
        d = -_log1m(self._rng.random()) * avg
        return min(max(d, 0.15), avg * 4 + 1.0)

    async def _run(self) -> None:
        try:
            while self.running:
                await asyncio.sleep(self._next_delay())
                if not self.running:
                    break
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(self._tick_once)
        except asyncio.CancelledError:
            pass

    def _tick_once(self) -> None:
        with self._lock:
            targets = list(self._targets)
        if not targets:
            return
        # Spread activity evenly across the selected *banks*: pick a bank first, then one of its
        # selected accounts. Choosing a flat account at random would over-weight banks that simply
        # have more accounts selected, making the feed look concentrated on one or two banks.
        by_bank: dict[str, list[str]] = {}
        for bank_id, account_id in targets:
            by_bank.setdefault(bank_id, []).append(account_id)
        bank_id = self._rng.choice(list(by_bank))
        account_id = self._rng.choice(by_bank[bank_id])
        side = "debit" if self._rng.random() < 0.55 else "credit"
        amount = Decimal(self._rng.randrange(100, 48000)) / 100
        description = self._rng.choice(self._merchants_for(bank_id))
        try:
            record = self._container.post_external_transaction(
                bank_id,
                account_id,
                amount=amount,
                side=side,
                description=description,
            )
        except Exception:
            # e.g. insufficient funds on a debit, or the account was deleted — skip this tick.
            return
        self.generated += 1
        self._record(bank_id, account_id, record, "sim")

    def _merchants_for(self, bank_id: str) -> tuple[str, ...]:
        """Return merchant labels in the bank's language, falling back to the English defaults."""
        try:
            bank = self._container.bank_service.get_bank(bank_id)
            pack = resolve_pack(bank.locale, bank.country)
            if pack.merchant_categories:
                return tuple(pack.merchant_categories)
        except Exception:
            pass
        return _MERCHANTS


def _log1m(u: float) -> float:
    """Return ``log(1 - u)`` guarding against ``u`` reaching 1.0."""
    import math

    return math.log(1.0 - min(u, 0.999999))
