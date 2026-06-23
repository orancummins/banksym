"""Protocol-neutral consent + SCA state, shared across protocol adapters.

PSD2 (and similar) protocols all revolve around a TPP obtaining PSU consent and completing Strong
Customer Authentication (SCA). The state machine here is intentionally protocol-agnostic so the
Berlin Group, STET, and UK Open Banking adapters can reuse it; each adapter only maps its own wire
format onto these entities.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Protocol

from banksym.core.kernel.ids import new_id


class ConsentStatus(enum.StrEnum):
    """Berlin Group consent statuses (shared vocabulary)."""

    RECEIVED = "received"
    VALID = "valid"
    REJECTED = "rejected"
    REVOKED_BY_PSU = "revokedByPsu"
    EXPIRED = "expired"
    TERMINATED_BY_TPP = "terminatedByTpp"


class ScaStatus(enum.StrEnum):
    """Authorisation (SCA) sub-resource statuses."""

    RECEIVED = "received"
    PSU_AUTHENTICATED = "psuAuthenticated"
    SCA_METHOD_SELECTED = "scaMethodSelected"
    FINALISED = "finalised"
    FAILED = "failed"


@dataclass(slots=True)
class Authorisation:
    """A single SCA authorisation sub-resource attached to a consent."""

    id: str = field(default_factory=lambda: new_id("auth_"))
    sca_status: ScaStatus = ScaStatus.RECEIVED


@dataclass(slots=True)
class Consent:
    """An account-information consent and its authorisation state."""

    bank_id: str
    access: dict
    recurring: bool = True
    frequency_per_day: int = 4
    valid_until: date | None = None
    combined_service: bool = False
    psu_id: str | None = None
    # The customer who authenticated (via SCA) and to whom this consent is scoped. Until SCA
    # completes this is None; afterwards account access is limited to this customer's accounts.
    customer_id: str | None = None
    # The specific accounts the PSU ticked on the bank's authorisation page. ``None`` means the PSU
    # has not narrowed the selection (all of their accounts within the consent's scope are allowed);
    # an explicit list limits access to exactly those account ids.
    allowed_account_ids: list[str] | None = None
    status: ConsentStatus = ConsentStatus.RECEIVED
    id: str = field(default_factory=lambda: new_id("consent_"))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    authorisations: dict[str, Authorisation] = field(default_factory=dict)

    @property
    def all_accounts(self) -> bool:
        """True when the consent grants access to all available accounts."""
        access = self.access or {}
        return bool(access.get("availableAccounts") or access.get("allPsd2"))

    def allowed_ibans(self) -> set[str]:
        """IBANs explicitly listed under any access group."""
        ibans: set[str] = set()
        for group in ("accounts", "balances", "transactions"):
            for ref in (self.access or {}).get(group, []) or []:
                if isinstance(ref, dict) and ref.get("iban"):
                    ibans.add(ref["iban"])
        return ibans


class ConsentStore(Protocol):
    """Storage contract for consents, scoped by ``bank_id``."""

    def add(self, consent: Consent) -> None: ...

    def get(self, bank_id: str, consent_id: str) -> Consent | None: ...

    def list(self, bank_id: str) -> list[Consent]: ...

    def save(self, consent: Consent) -> None: ...

    def purge(self, bank_id: str) -> None: ...


class InMemoryConsentStore:
    def __init__(self) -> None:
        self._consents: dict[tuple[str, str], Consent] = {}

    def add(self, consent: Consent) -> None:
        self._consents[(consent.bank_id, consent.id)] = consent

    def get(self, bank_id: str, consent_id: str) -> Consent | None:
        return self._consents.get((bank_id, consent_id))

    def list(self, bank_id: str) -> list[Consent]:
        return [c for (b, _), c in self._consents.items() if b == bank_id]

    def save(self, consent: Consent) -> None:
        self._consents[(consent.bank_id, consent.id)] = consent

    def purge(self, bank_id: str) -> None:
        self._consents = {
            key: c for key, c in self._consents.items() if key[0] != bank_id
        }
