"""End-to-end tests for the Berlin Group (XS2A) AIS flow and the architecture view."""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


_bank_seq = 0


def _seed_bank_with_history(client: TestClient) -> tuple[str, str, str]:
    global _bank_seq
    _bank_seq += 1
    bank = client.post(
        "/banks",
        json={
            "display_name": f"Test ASPSP {_bank_seq}",
            "country": "DE",
            "capabilities": {"txgen": "rule_based"},
        },
    ).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Erika Mustermann", "persona": "affluent_family"},
    ).json()
    account = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "EUR", "customer_id": customer["id"]},
    ).json()
    client.post(
        f"/banks/{bank_id}/accounts/{account['id']}/generate-history",
        json={"start": "2025-01-01", "end": "2025-02-28", "seed": 5},
    )
    return bank_id, account["id"], customer["username"]


def test_architecture_lists_berlin_group(client: TestClient):
    arch = client.get("/architecture").json()
    api = next(c for c in arch["capabilities"] if c["kind"] == "api")
    assert api["interface"] == "APIAdapter"
    assert "berlin_group" in api["implementations"]
    sca = next(c for c in arch["capabilities"] if c["kind"] == "sca")
    assert sca["extends"] == "APIAdapter"
    assert arch["core"]["interface"] == "CoreBankingService"


def test_ais_requires_valid_consent(client: TestClient):
    bank_id, _, _ = _seed_bank_with_history(client)
    # No Consent-ID header -> 401.
    resp = client.get(f"/xs2a/{bank_id}/v1/accounts")
    assert resp.status_code == 401


def test_full_ais_consent_flow(client: TestClient):
    bank_id, account_id, username = _seed_bank_with_history(client)
    base = f"/xs2a/{bank_id}/v1"

    # The customer signs in with their auto-created online-banking credentials.
    login = client.post(
        f"/banks/{bank_id}/auth/login",
        json={"username": username, "password": "foobar!"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Create consent for all available accounts.
    consent = client.post(
        f"{base}/consents",
        json={
            "access": {"availableAccounts": "allAccounts"},
            "recurringIndicator": True,
            "validUntil": "2025-12-31",
            "frequencyPerDay": 4,
        },
    )
    assert consent.status_code == 201
    consent_body = consent.json()
    assert consent_body["consentStatus"] == "received"
    consent_id = consent_body["consentId"]

    # 2. Before SCA, account data is refused.
    pre = client.get(f"{base}/accounts", headers={"Consent-ID": consent_id})
    assert pre.status_code == 401

    # 3. Start authorisation; the SCA PUT requires a real PSU session.
    auth = client.post(f"{base}/consents/{consent_id}/authorisations").json()
    auth_id = auth["authorisationId"]

    # Without a session token, SCA is rejected.
    unauth = client.put(
        f"{base}/consents/{consent_id}/authorisations/{auth_id}",
        json={"scaAuthenticationData": "123456"},
    )
    assert unauth.status_code == 401

    put = client.put(
        f"{base}/consents/{consent_id}/authorisations/{auth_id}",
        json={"scaAuthenticationData": "123456"},
        headers=auth_header,
    )
    assert put.json()["scaStatus"] == "finalised"
    assert client.get(f"{base}/consents/{consent_id}/status").json()["consentStatus"] == "valid"

    # 4. Now AIS works: accounts, balances, transactions.
    accounts = client.get(f"{base}/accounts", headers={"Consent-ID": consent_id}).json()
    assert len(accounts["accounts"]) == 1
    resource_id = accounts["accounts"][0]["resourceId"]

    balances = client.get(
        f"{base}/accounts/{resource_id}/balances", headers={"Consent-ID": consent_id}
    ).json()
    assert balances["balances"][0]["balanceType"] == "closingBooked"

    txns = client.get(
        f"{base}/accounts/{resource_id}/transactions", headers={"Consent-ID": consent_id}
    ).json()
    assert len(txns["transactions"]["booked"]) > 0


def test_consent_tenant_isolation(client: TestClient):
    bank_a, _, _ = _seed_bank_with_history(client)
    bank_b, _, _ = _seed_bank_with_history(client)
    consent = client.post(
        f"/xs2a/{bank_a}/v1/consents",
        json={"access": {"availableAccounts": "allAccounts"}},
    ).json()
    # Consent created on bank A is unknown on bank B.
    resp = client.get(f"/xs2a/{bank_b}/v1/consents/{consent['consentId']}/status")
    assert resp.status_code == 403


def test_ais_is_scoped_to_authenticated_psu(client: TestClient):
    """An 'all accounts' consent must only expose the authenticated PSU's own accounts."""
    global _bank_seq
    _bank_seq += 1
    bank_id = client.post(
        "/banks",
        json={
            "display_name": f"Scope Bank {_bank_seq}",
            "country": "DE",
            "enabled_protocols": ["berlin_group"],
            "capabilities": {"txgen": "rule_based"},
        },
    ).json()["id"]

    # Two customers: one with a single account, the PSU with two accounts.
    other = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Other Holder", "email": "other@example.com"},
    ).json()
    other_account = client.post(
        f"/banks/{bank_id}/accounts", json={"currency": "EUR", "customer_id": other["id"]}
    ).json()
    psu = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Real PSU", "email": "psu@example.com"},
    ).json()
    client.post(f"/banks/{bank_id}/accounts", json={"currency": "EUR", "customer_id": psu["id"]})
    client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "EUR", "type": "savings", "customer_id": psu["id"]},
    )

    base = f"/xs2a/{bank_id}/v1"
    redirect = "http://tpp.example/callback"
    consent_id = client.post(
        f"{base}/consents", json={"access": {"availableAccounts": "allAccounts"}}
    ).json()["consentId"]

    # The PSU authenticates at the bank (OAuth redirect SCA).
    authz = client.post(
        f"/banks/{bank_id}/oauth/authorize",
        json={
            "consent_id": consent_id,
            "username": psu["username"],
            "password": "foobar!",
            "redirect_uri": redirect,
        },
    )
    assert authz.status_code == 200

    # AIS exposes only the PSU's two accounts, not the other customer's.
    accounts = client.get(f"{base}/accounts", headers={"Consent-ID": consent_id}).json()
    assert len(accounts["accounts"]) == 2

    # The other customer's account cannot be read directly via the consent.
    cross = client.get(
        f"{base}/accounts/{other_account['id']}/balances", headers={"Consent-ID": consent_id}
    )
    assert cross.status_code == 404


def test_unknown_bank_xs2a_404(client: TestClient):
    resp = client.post(
        "/xs2a/bank_missing/v1/consents",
        json={"access": {"availableAccounts": "allAccounts"}},
    )
    assert resp.status_code == 404
