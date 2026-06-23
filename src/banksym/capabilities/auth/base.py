"""Auth & SCA capability interfaces.

``AuthProvider`` verifies PSU credentials and manages sessions; ``ScaProvider`` issues and verifies
strong-authentication challenges. Both are capability families resolved per-bank, so a bank can run
a simple password provider while another runs an OAuth/OIDC provider, without touching core.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar, Protocol

from banksym.core.kernel.ids import new_id
from banksym.core.kernel.registry import Capability, CapabilityRegistry

AUTH_KIND = "auth"
SCA_KIND = "sca"


@dataclass(slots=True)
class Credential:
    """A PSU login credential, scoped to a bank and linked to a customer."""

    bank_id: str
    username: str
    secret_hash: str
    customer_id: str
    id: str = field(default_factory=lambda: new_id("cred"))


@dataclass(slots=True)
class Session:
    """An authenticated session token issued after successful login."""

    bank_id: str
    customer_id: str
    username: str
    token: str = field(default_factory=lambda: new_id("sess"))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ScaChallenge:
    """A strong-authentication challenge bound to a session/operation."""

    bank_id: str
    customer_id: str
    method: str = "auto"
    verified: bool = False
    id: str = field(default_factory=lambda: new_id("sca"))


class CredentialStore(Protocol):
    def add(self, credential: Credential) -> None: ...
    def find(self, bank_id: str, username: str) -> Credential | None: ...
    def find_by_customer(self, bank_id: str, customer_id: str) -> Credential | None: ...
    def purge(self, bank_id: str) -> None: ...


class SessionStore(Protocol):
    def add(self, session: Session) -> None: ...
    def get(self, token: str) -> Session | None: ...
    def remove(self, token: str) -> None: ...


class InMemoryCredentialStore:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Credential] = {}

    def add(self, credential: Credential) -> None:
        self._by_key[(credential.bank_id, credential.username)] = credential

    def find(self, bank_id: str, username: str) -> Credential | None:
        return self._by_key.get((bank_id, username))

    def find_by_customer(self, bank_id: str, customer_id: str) -> Credential | None:
        for (b, _), cred in self._by_key.items():
            if b == bank_id and cred.customer_id == customer_id:
                return cred
        return None

    def purge(self, bank_id: str) -> None:
        self._by_key = {
            key: c for key, c in self._by_key.items() if key[0] != bank_id
        }


class InMemorySessionStore:
    def __init__(self) -> None:
        self._by_token: dict[str, Session] = {}

    def add(self, session: Session) -> None:
        self._by_token[session.token] = session

    def get(self, token: str) -> Session | None:
        return self._by_token.get(token)

    def remove(self, token: str) -> None:
        self._by_token.pop(token, None)


class AuthProvider(Capability, abc.ABC):
    """Verify PSU credentials and manage sessions."""

    capability_kind: ClassVar[str] = AUTH_KIND

    def __init__(self, credentials: CredentialStore, sessions: SessionStore) -> None:
        self.credentials = credentials
        self.sessions = sessions

    @abc.abstractmethod
    def register(self, bank_id: str, username: str, password: str, customer_id: str) -> Credential:
        """Create and persist a credential for a PSU."""

    @abc.abstractmethod
    def authenticate(self, bank_id: str, username: str, password: str) -> Session | None:
        """Return a new session on success, else ``None``."""

    def get_session(self, token: str) -> Session | None:
        return self.sessions.get(token)

    def logout(self, token: str) -> None:
        self.sessions.remove(token)


class ScaProvider(Capability, abc.ABC):
    """Issue and verify strong-customer-authentication challenges."""

    capability_kind: ClassVar[str] = SCA_KIND

    @abc.abstractmethod
    def start_challenge(self, bank_id: str, customer_id: str, method: str = "auto") -> ScaChallenge:
        """Begin an SCA challenge."""

    @abc.abstractmethod
    def verify(self, challenge: ScaChallenge, code: str | None = None) -> bool:
        """Verify the challenge, returning ``True`` on success."""


auth_registry: CapabilityRegistry[AuthProvider] = CapabilityRegistry(AUTH_KIND)
sca_registry: CapabilityRegistry[ScaProvider] = CapabilityRegistry(SCA_KIND)
