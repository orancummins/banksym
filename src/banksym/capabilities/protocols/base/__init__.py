"""Protocol capability — exposes the bank over a banking protocol (PSD2 XS2A, STET, ...).

A :class:`ProtocolAdapter` is a pluggable capability that translates an external protocol's
request/response shapes to and from the protocol-neutral :class:`CoreBankingService` and the
shared :class:`ConsentStore`. Multiple protocol standards can be implemented side by side; a bank
enables whichever it needs.
"""

from banksym.capabilities.protocols.base.adapter import ProtocolAdapter, protocol_registry
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
    "ProtocolAdapter",
    "ScaStatus",
    "protocol_registry",
]
