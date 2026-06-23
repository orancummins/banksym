"""TransactionGenerator interface + registry."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date

from banksym.core.domain.account import Account
from banksym.core.domain.customer import Customer
from banksym.core.domain.ledger import JournalEntry
from banksym.core.kernel.registry import Capability, CapabilityRegistry
from banksym.core.service import CoreBankingService

CAPABILITY_KIND = "txgen"


@dataclass(slots=True)
class GenerationRequest:
    """Parameters describing the history to synthesize for one customer."""

    bank_id: str
    customer: Customer
    account: Account
    start: date
    end: date
    persona: str | None = None
    currency: str = "EUR"
    country: str = "DE"
    language: str = ""
    seed: int | None = None
    options: dict[str, str] = field(default_factory=dict)


class TransactionGenerator(Capability, abc.ABC):
    """Synthesize transaction history by posting balanced entries through the core service."""

    capability_kind = CAPABILITY_KIND

    def __init__(self, banking: CoreBankingService) -> None:
        self.banking = banking

    @abc.abstractmethod
    def generate(self, request: GenerationRequest) -> list[JournalEntry]:
        """Produce and persist journal entries; return the entries that were booked."""
        raise NotImplementedError


txgen_registry: CapabilityRegistry[TransactionGenerator] = CapabilityRegistry(CAPABILITY_KIND)
