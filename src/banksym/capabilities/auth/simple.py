"""Simple stdlib-only auth & SCA implementations.

``SimpleAuthProvider`` hashes passwords with PBKDF2-HMAC (no third-party deps). ``AutoApproveSca``
immediately approves challenges — convenient for tests and demos. Both register themselves on
import.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from banksym.capabilities.auth.base import (
    AuthProvider,
    Credential,
    ScaChallenge,
    ScaProvider,
    Session,
    auth_registry,
    sca_registry,
)

_ITERATIONS = 120_000


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
    except ValueError:
        return False
    expected = _hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(expected, digest_hex)


@auth_registry.register
class SimpleAuthProvider(AuthProvider):
    """Username/password auth backed by PBKDF2-HMAC hashing."""

    capability_name = "simple"

    def register(
        self, bank_id: str, username: str, password: str, customer_id: str
    ) -> Credential:
        credential = Credential(
            bank_id=bank_id,
            username=username,
            secret_hash=_hash_password(password),
            customer_id=customer_id,
        )
        self.credentials.add(credential)
        return credential

    def authenticate(self, bank_id: str, username: str, password: str) -> Session | None:
        credential = self.credentials.find(bank_id, username)
        if credential is None or not _verify_password(password, credential.secret_hash):
            return None
        session = Session(
            bank_id=bank_id, customer_id=credential.customer_id, username=username
        )
        self.sessions.add(session)
        return session


@sca_registry.register
class AutoApproveSca(ScaProvider):
    """SCA provider that auto-approves every challenge (for demos/tests)."""

    capability_name = "auto"

    def start_challenge(
        self, bank_id: str, customer_id: str, method: str = "auto"
    ) -> ScaChallenge:
        return ScaChallenge(
            bank_id=bank_id, customer_id=customer_id, method=method, verified=True
        )

    def verify(self, challenge: ScaChallenge, code: str | None = None) -> bool:
        challenge.verified = True
        return True
