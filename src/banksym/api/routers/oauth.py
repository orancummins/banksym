"""Per-bank OAuth2 redirect SCA endpoints.

These replicate a real Open Banking authorisation: the TPP redirects the PSU to a *bank-hosted*
login page (so the TPP never sees the PSU's credentials), the PSU authenticates and approves the
consent at the bank, and the bank redirects back to the TPP with a one-time authorization ``code``.
The TPP then exchanges that code for an access token.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException

from banksym.api.deps import BankIdDep, ContainerDep
from banksym.api.schemas import (
    OAuthAccountItem,
    OAuthAccountsRequest,
    OAuthAccountsResponse,
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthTokenRequest,
    OAuthTokenResponse,
)

router = APIRouter(prefix="/banks/{bank_id}/oauth", tags=["oauth (redirect SCA)"])


def _eligible_accounts(container: ContainerDep, bank_id: str, customer_id: str | None):
    """Customer-facing (non-internal) accounts the authenticated PSU could share."""
    return [
        a
        for a in container.banking.list_accounts(bank_id)
        if not a.is_internal and a.customer_id is not None and a.customer_id == customer_id
    ]


def _synth_iban(account, country: str) -> str:
    """Match the pseudo-IBAN the Berlin Group AIS exposes for accounts without a real one."""
    if account.iban:
        return account.iban
    tail = account.id.replace("acc_", "")[:16].upper().ljust(16, "0")
    return f"{country[:2].upper()}00BSYM{tail}"


@router.post(
    "/accounts",
    response_model=OAuthAccountsResponse,
    summary="List the PSU's accounts for selection",
)
def authorize_accounts(
    body: OAuthAccountsRequest, bank_id: BankIdDep, container: ContainerDep
) -> OAuthAccountsResponse:
    """Authenticate the PSU and return their accounts so they can choose which to share.

    Called by the bank-hosted authorisation page after the PSU clicks *Authenticate* and before
    they grant access. This step does **not** activate the consent or mint a code — it only previews
    the accounts the PSU may permission.
    """
    provider = container.resolve_auth_provider(bank_id)
    session = provider.authenticate(bank_id, body.username, body.password)
    if session is None:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    consent = container.consent_store.get(bank_id, body.consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    if consent.psu_id and session.username != consent.psu_id:
        raise HTTPException(
            status_code=403, detail="This login does not match the requested account holder"
        )

    country = container.bank_service.get_bank(bank_id).country
    accounts = _eligible_accounts(container, bank_id, session.customer_id)
    items = [
        OAuthAccountItem(
            id=a.id,
            iban=_synth_iban(a, country),
            name=a.name,
            type=a.type,
            currency=a.currency,
            balance=str(container.banking.balance(bank_id, a.id)),
        )
        for a in accounts
    ]
    return OAuthAccountsResponse(accounts=items)


@router.post(
    "/authorize", response_model=OAuthAuthorizeResponse, summary="Authorise at the bank (PSU login)"
)
def authorize(
    body: OAuthAuthorizeRequest, bank_id: BankIdDep, container: ContainerDep
) -> OAuthAuthorizeResponse:
    """Authenticate the PSU at the bank, activate the consent, and mint an authorization code.

    Called by the bank-hosted login page. On success the browser is told to return to the TPP's
    ``redirect_uri`` with the ``code`` (and ``state``) appended. When ``account_ids`` is supplied,
    the consent is narrowed to exactly the accounts the PSU selected.
    """
    provider = container.resolve_auth_provider(bank_id)
    session = provider.authenticate(bank_id, body.username, body.password)
    if session is None:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    consent = container.consent_store.get(bank_id, body.consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    if consent.psu_id and session.username != consent.psu_id:
        raise HTTPException(
            status_code=403, detail="This login does not match the requested account holder"
        )

    account_ids = body.account_ids
    if account_ids is not None:
        # Reject a selection that includes accounts the PSU does not actually hold.
        owned = {a.id for a in _eligible_accounts(container, bank_id, session.customer_id)}
        account_ids = [aid for aid in account_ids if aid in owned]

    container.approve_consent(
        bank_id, body.consent_id, customer_id=session.customer_id, account_ids=account_ids
    )
    code = container.issue_oauth_code(bank_id, body.consent_id, session.token, body.redirect_uri)

    separator = "&" if "?" in body.redirect_uri else "?"
    redirect_to = f"{body.redirect_uri}{separator}code={quote(code)}"
    if body.state:
        redirect_to += f"&state={quote(body.state)}"
    return OAuthAuthorizeResponse(redirect_to=redirect_to)


@router.post(
    "/token", response_model=OAuthTokenResponse, summary="Exchange authorization code for token"
)
def token(
    body: OAuthTokenRequest, bank_id: BankIdDep, container: ContainerDep
) -> OAuthTokenResponse:
    """Exchange a one-time authorization code for the PSU's access token."""
    if body.grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")
    record = container.exchange_oauth_code(bank_id, body.code, body.redirect_uri)
    if record is None:
        raise HTTPException(status_code=400, detail="invalid_grant")
    return OAuthTokenResponse(access_token=record.session_token, consent_id=record.consent_id)
