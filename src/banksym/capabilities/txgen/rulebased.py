"""Deterministic, rule-based transaction generator.

Uses persona-driven monthly income and categorised spending to build a plausible history, with
localized merchant names and income labels from the active :class:`LocalizationProvider`. Fully
deterministic given a seed, so tests and demos are reproducible. Requires no external services.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from banksym.capabilities.localization.base import LocalePack, resolve_pack
from banksym.capabilities.txgen.base import (
    GenerationRequest,
    TransactionGenerator,
    txgen_registry,
)
from banksym.capabilities.txgen.personas import profile_for
from banksym.core.domain.account import Account, AccountType
from banksym.core.domain.ledger import JournalEntry, Posting
from banksym.core.kernel.money import Money


_MERCHANT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("groceries", "instore"),
    ("restaurant", "instore"),
    ("transport", "in_app"),
    ("utilities", "direct_debit"),
    ("shopping", "online"),
    ("entertainment", "online"),
    ("pharmacy", "instore"),
    ("subscriptions", "online"),
)

_LOCATIONS: dict[str, tuple[str, ...]] = {
    "DE": ("Berlin", "Munich", "Hamburg", "Cologne"),
    "ES": ("Madrid", "Barcelona", "Valencia", "Seville"),
    "FR": ("Paris", "Lyon", "Marseille", "Toulouse"),
    "GB": ("London", "Manchester", "Leeds", "Bristol"),
    "IE": ("Dublin", "Cork", "Galway", "Limerick"),
    "NL": ("Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"),
    "US": ("New York", "Chicago", "Austin", "Seattle"),
    "CA": ("Toronto", "Vancouver", "Montreal", "Calgary"),
    "BR": ("São Paulo", "Rio de Janeiro", "Brasília", "Curitiba"),
    "CN": ("北京", "上海", "广州", "深圳"),
    "ZA": ("Johannesburg", "Cape Town", "Durban", "Pretoria"),
}


def _month_starts(start: date, end: date):
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        yield cursor
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )


@txgen_registry.register
class RuleBasedTransactionGenerator(TransactionGenerator):
    """Persona-driven, seeded transaction generator."""

    capability_name = "rule_based"

    def generate(self, request: GenerationRequest) -> list[JournalEntry]:
        rng = random.Random(request.seed)
        profile = profile_for(request.persona)
        pack = self._locale_pack(request)
        counterparty = self._counterparty_account(request.bank_id, request.currency)
        entries: list[JournalEntry] = []

        for month_start in _month_starts(request.start, request.end):
            pay_day = min(month_start.replace(day=25), request.end)
            if pay_day >= request.start:
                income = Money.from_decimal(
                    round(profile.monthly_income * rng.uniform(0.97, 1.03), 2),
                    request.currency,
                )
                entries.append(
                    self._book(
                        request,
                        debit_account=counterparty.id,
                        credit_account=request.account.id,
                        amount=income,
                        description=pack.income_label,
                        reference=f"SAL-{pay_day.strftime('%Y%m')}",
                        metadata={
                            "merchant_name": pack.income_label,
                            "category": "income",
                            "payment_reference": f"PAYROLL-{pay_day.strftime('%Y%m')}",
                            "location": self._location_for(request, rng),
                            "channel": "bank_transfer",
                        },
                    )
                )

            spend_budget = profile.monthly_income * profile.monthly_spend_ratio
            n_purchases = rng.randint(12, 28)
            for _ in range(n_purchases):
                day_offset = rng.randint(0, 27)
                when = month_start + timedelta(days=day_offset)
                if when < request.start or when > request.end:
                    continue
                base = spend_budget / n_purchases
                low = 1 - profile.spend_volatility
                high = 1 + profile.spend_volatility
                amount_val = max(1.0, round(base * rng.uniform(low, high), 2))
                amount = Money.from_decimal(amount_val, request.currency)
                merchant_idx = rng.randrange(len(pack.merchant_categories))
                merchant = pack.merchant_for(merchant_idx)
                category, channel = _MERCHANT_CATEGORIES[merchant_idx % len(_MERCHANT_CATEGORIES)]
                payment_ref = f"{category[:3].upper()}-{when.strftime('%m%d')}-{rng.randint(1000, 9999)}"
                entries.append(
                    self._book(
                        request,
                        debit_account=request.account.id,
                        credit_account=counterparty.id,
                        amount=amount,
                        description=merchant,
                        reference=payment_ref,
                        metadata={
                            "merchant_name": merchant,
                            "category": category,
                            "payment_reference": payment_ref,
                            "location": self._location_for(request, rng),
                            "channel": channel,
                        },
                    )
                )
        return entries

    def _locale_pack(self, request: GenerationRequest) -> LocalePack:
        return resolve_pack(request.language, request.country)

    def _counterparty_account(self, bank_id: str, currency: str) -> Account:
        return self.banking.ensure_internal_account(
            bank_id, currency, AccountType.INTERNAL, "External world"
        )

    def _book(
        self,
        request: GenerationRequest,
        *,
        debit_account: str,
        credit_account: str,
        amount: Money,
        description: str,
        reference: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            bank_id=request.bank_id,
            description=description,
            reference=reference,
            metadata=metadata or {},
            postings=[
                Posting(account_id=debit_account, amount=-amount),
                Posting(account_id=credit_account, amount=amount),
            ],
        )
        return self.banking.post_journal_entry(entry)

    def _location_for(self, request: GenerationRequest, rng: random.Random) -> str:
        return rng.choice(_LOCATIONS.get((request.country or "").upper(), (request.country or "Online",)))
