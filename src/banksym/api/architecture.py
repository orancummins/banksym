"""Introspects the live capability registries to describe the logical design.

This powers the architecture visualization in the UI: it reports the single core banking interface
and every pluggable capability kind with its registered implementations, plus the capabilities that
are planned but not yet implemented.
"""

from __future__ import annotations

from typing import TypedDict

from banksym.capabilities.auth.base import auth_registry, sca_registry
from banksym.capabilities.localization.base import localization_registry
from banksym.capabilities.protocols.base import protocol_registry
from banksym.capabilities.settlement.base import settlement_registry
from banksym.capabilities.txgen.base import txgen_registry


class CapabilityView(TypedDict):
    kind: str
    interface: str
    description: str
    status: str
    implementations: list[str]


class ArchitectureView(TypedDict):
    core: dict
    capabilities: list[CapabilityView]


def get_architecture() -> ArchitectureView:
    capabilities: list[CapabilityView] = [
        {
            "kind": "protocol",
            "interface": "ProtocolAdapter",
            "description": "Exposes the bank over a banking protocol (PSD2 XS2A, STET, UK OB...).",
            "status": "implemented" if protocol_registry.names() else "planned",
            "implementations": protocol_registry.names(),
        },
        {
            "kind": "txgen",
            "interface": "TransactionGenerator",
            "description": "Synthesizes persona-driven transaction history into the ledger.",
            "status": "implemented" if txgen_registry.names() else "planned",
            "implementations": txgen_registry.names(),
        },
        {
            "kind": "settlement",
            "interface": "SettlementEngine",
            "description": (
                "RTGS, batch netting and inter-bank (nostro/vostro) settlement strategies."
            ),
            "status": "implemented" if settlement_registry.names() else "planned",
            "implementations": settlement_registry.names(),
        },
        {
            "kind": "localization",
            "interface": "LocalizationProvider",
            "description": (
                "Locale, currency, language and typical-merchant catalogs per country."
            ),
            "status": "implemented" if localization_registry.names() else "planned",
            "implementations": localization_registry.names(),
        },
        {
            "kind": "auth",
            "interface": "AuthProvider",
            "description": "PSU login and session management (password, OAuth2/OIDC...).",
            "status": "implemented" if auth_registry.names() else "planned",
            "implementations": auth_registry.names(),
        },
        {
            "kind": "sca",
            "interface": "ScaProvider",
            "description": "Strong Customer Authentication challenge issuance and verification.",
            "status": "implemented" if sca_registry.names() else "planned",
            "implementations": sca_registry.names(),
        },
    ]
    return {
        "core": {
            "interface": "CoreBankingService",
            "description": (
                "The single stateful domain of record: customers, accounts, the double-entry "
                "ledger and transaction history, persisted via SQLAlchemy so it survives "
                "restarts. Every capability depends on this interface; the core never depends "
                "on a capability."
            ),
            "implementations": [
                "SqlCoreBankingRepository",
                "InMemoryCoreBankingRepository",
            ],
        },
        "capabilities": capabilities,
    }
