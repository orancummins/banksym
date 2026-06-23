"""Per-bank authentication endpoints (PSU credential registration + login/logout)."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from banksym.api.deps import BankIdDep, ContainerDep
from banksym.api.schemas import (
    CredentialResponse,
    LoginRequest,
    RegisterCredentialRequest,
    SessionResponse,
)

router = APIRouter(prefix="/banks/{bank_id}/auth", tags=["auth"])


@router.post(
    "/credentials",
    response_model=CredentialResponse,
    status_code=201,
    summary="Register PSU credentials",
)
def register_credential(
    body: RegisterCredentialRequest, bank_id: BankIdDep, container: ContainerDep
) -> CredentialResponse:
    """Register online-banking credentials for an existing customer (PSU).

    Validates that the customer exists, then issues a username/password the PSU can use to log in
    and to authenticate during Open Banking SCA.
    """
    provider = container.resolve_auth_provider(bank_id)
    # Validate the customer exists before issuing a credential.
    container.banking.get_customer(bank_id, body.customer_id)
    credential = provider.register(bank_id, body.username, body.password, body.customer_id)
    return CredentialResponse(
        id=credential.id, username=credential.username, customer_id=credential.customer_id
    )


@router.post("/login", response_model=SessionResponse, summary="Log in (PSU)")
def login(body: LoginRequest, bank_id: BankIdDep, container: ContainerDep) -> SessionResponse:
    """Authenticate a PSU with their username and password and open a session.

    Returns the session token on success, or 401 if the credentials are invalid.
    """
    provider = container.resolve_auth_provider(bank_id)
    session = provider.authenticate(bank_id, body.username, body.password)
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return SessionResponse(
        token=session.token, customer_id=session.customer_id, username=session.username
    )


@router.get("/session", response_model=SessionResponse, summary="Inspect the current session")
def current_session(
    bank_id: BankIdDep,
    container: ContainerDep,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> SessionResponse:
    """Return the session bound to the ``Authorization: Bearer <token>`` header.

    Responds 401 if the token is missing, unknown, or belongs to a different bank.
    """
    token = _bearer(authorization)
    provider = container.resolve_auth_provider(bank_id)
    session = provider.get_session(token)
    if session is None or session.bank_id != bank_id:
        raise HTTPException(status_code=401, detail="No active session")
    return SessionResponse(
        token=session.token, customer_id=session.customer_id, username=session.username
    )


@router.post("/logout", status_code=204, summary="Log out (PSU)")
def logout(
    bank_id: BankIdDep,
    container: ContainerDep,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Invalidate the session identified by the ``Authorization: Bearer <token>`` header."""
    token = _bearer(authorization)
    container.resolve_auth_provider(bank_id).logout(token)


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Expected 'Bearer <token>'")
    return token
