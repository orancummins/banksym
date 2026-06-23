"""Authentication & SCA capabilities.

Two pluggable capability families:

* :class:`AuthProvider` — PSU login: verify credentials and issue/inspect sessions.
* :class:`ScaProvider` — Strong Customer Authentication: issue and verify challenges.

Implementations are swappable (e.g. a simple password provider for tests, an OAuth2/OIDC provider
for realistic flows).
"""

from banksym.capabilities.auth.base import (
    AuthProvider,
    Credential,
    CredentialStore,
    InMemoryCredentialStore,
    InMemorySessionStore,
    ScaChallenge,
    ScaProvider,
    Session,
    SessionStore,
    auth_registry,
    sca_registry,
)

__all__ = [
    "AuthProvider",
    "Credential",
    "CredentialStore",
    "InMemoryCredentialStore",
    "InMemorySessionStore",
    "ScaChallenge",
    "ScaProvider",
    "Session",
    "SessionStore",
    "auth_registry",
    "sca_registry",
]
