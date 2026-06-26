"""API capability — exposes the bank over an external banking API (PSD2 XS2A, STET, ...).

A :class:`APIAdapter` is a pluggable capability that translates an external API's
request/response shapes to and from the API-neutral :class:`CoreBankingService` and the
shared :class:`ConsentStore`. Multiple API standards can be implemented side by side; a bank
enables whichever it needs.
"""

from banksym.capabilities.protocols.base.adapter import (
    APIAdapter,
    ProtocolAdapter,
    api_registry,
    protocol_registry,
)
from banksym.capabilities.protocols.base.consent import (
    Consent,
    ConsentStatus,
    ConsentStore,
    InMemoryConsentStore,
    ScaStatus,
)
from banksym.capabilities.protocols.base.payment import (
    InMemoryPaymentStore,
    Payment,
    PaymentStatus,
    PaymentStore,
)

__all__ = [
    "Consent",
    "ConsentStatus",
    "ConsentStore",
    "InMemoryConsentStore",
    "InMemoryPaymentStore",
    "Payment",
    "PaymentStatus",
    "PaymentStore",
    "APIAdapter",
    "ProtocolAdapter",
    "ScaStatus",
    "api_registry",
    "protocol_registry",
]
