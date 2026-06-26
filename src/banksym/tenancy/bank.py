"""The Bank tenant entity and its configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from banksym.core.kernel.ids import new_id


@dataclass(slots=True)
class BankBranding:
    """Visual identity shown in UIs and protocol metadata."""

    display_name: str
    logo_url: str | None = None
    primary_color: str = "#0B5FFF"


@dataclass(slots=True)
class CapabilitySelection:
    """Which capability implementation a bank uses for each capability kind.

    Keys are capability kinds (e.g. ``"txgen"``, ``"protocol"``, ``"settlement"``); values are the
    registered implementation names (e.g. ``"rule_based"``, ``"berlin_group"``).
    """

    selected: dict[str, str] = field(default_factory=dict)

    def get(self, kind: str) -> str | None:
        return self.selected.get(kind)

    def set(self, kind: str, name: str) -> None:
        self.selected[kind] = name


@dataclass(slots=True)
class Bank:
    """A simulated bank (tenant)."""

    branding: BankBranding
    country: str
    locale: str = "en"
    base_currency: str = "EUR"
    supported_currencies: list[str] = field(default_factory=list)
    enabled_protocols: list[str] = field(default_factory=list)
    capabilities: CapabilitySelection = field(default_factory=CapabilitySelection)
    id: str = field(default_factory=lambda: new_id("bank_"))
