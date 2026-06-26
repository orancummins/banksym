"""APIAdapter interface + registry."""

from __future__ import annotations

import abc
from collections.abc import Callable

from fastapi import APIRouter

from banksym.capabilities.auth.base import AuthProvider
from banksym.capabilities.protocols.base.consent import ConsentStore
from banksym.capabilities.protocols.base.payment import PaymentStore
from banksym.capabilities.settlement.base import SettlementEngine
from banksym.core.kernel.registry import Capability, CapabilityRegistry
from banksym.core.service import CoreBankingService
from banksym.tenancy import BankService

CAPABILITY_KIND = "api"

SettlementResolver = Callable[[str], SettlementEngine]
"""Resolves the settlement engine a given bank is configured to use."""

AuthResolver = Callable[[str], AuthProvider]
"""Resolves the auth provider a given bank is configured to use."""


class APIAdapter(Capability, abc.ABC):
    """Exposes the core bank over a specific banking protocol as a mountable FastAPI router.

    An adapter is a singleton bound to the shared, multi-tenant services; ``bank_id`` is carried in
    the request path so one adapter instance serves every bank that enables it.
    """

    capability_kind = CAPABILITY_KIND
    protocol_title: str = ""
    """Human-readable API name shown in the architecture view (e.g. 'Berlin Group XS2A')."""

    def __init__(
        self,
        banking: CoreBankingService,
        consents: ConsentStore,
        payments: PaymentStore,
        banks: BankService,
        settlement_resolver: SettlementResolver,
        auth_resolver: AuthResolver,
    ) -> None:
        self.banking = banking
        self.consents = consents
        self.payments = payments
        self.banks = banks
        self.settlement_resolver = settlement_resolver
        self.auth_resolver = auth_resolver

    @abc.abstractmethod
    def build_router(self) -> APIRouter:
        """Return a FastAPI router implementing the API's endpoints."""
        raise NotImplementedError


api_registry: CapabilityRegistry[APIAdapter] = CapabilityRegistry(CAPABILITY_KIND)

# Backward-compatible aliases for existing imports.
ProtocolAdapter = APIAdapter
protocol_registry = api_registry
