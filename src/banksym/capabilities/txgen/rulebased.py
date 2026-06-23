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
                merchant = pack.merchant_for(rng.randrange(len(pack.merchant_categories)))
                entries.append(
                    self._book(
                        request,
                        debit_account=request.account.id,
                        credit_account=counterparty.id,
                        amount=amount,
                        description=merchant,
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
    ) -> JournalEntry:
        entry = JournalEntry(
            bank_id=request.bank_id,
            description=description,
            postings=[
                Posting(account_id=debit_account, amount=-amount),
                Posting(account_id=credit_account, amount=amount),
            ],
        )
        return self.banking.post_journal_entry(entry)
