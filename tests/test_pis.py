"""End-to-end tests for Berlin Group payment initiation (PIS) with RTGS settlement."""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


def _bank_with_funded_account(client: TestClient, *, fund: bool = True) -> tuple[str, str, str]:
    """Return (bank_id, account_id, iban) for a customer account, optionally funded."""
    bank = client.post(
        "/banks",
        json={
            "display_name": "Pay Bank",
            "country": "DE",
            "capabilities": {"txgen": "rule_based", "settlement": "rtgs"},
        },
    ).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Payer One", "persona": "young_professional"},
    ).json()
    account = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "EUR", "customer_id": customer["id"]},
    ).json()
    if fund:
        client.post(
            f"/banks/{bank_id}/accounts/{account['id']}/generate-history",
            json={"start": "2025-01-01", "end": "2025-03-31", "seed": 9},
        )
    iban = _read_iban_via_ais(client, bank_id, account["id"], customer["username"])
    return bank_id, account["id"], iban


def _read_iban_via_ais(client: TestClient, bank_id: str, account_id: str, username: str) -> str:
    base = f"/xs2a/{bank_id}/v1"
    token = client.post(
        f"/banks/{bank_id}/auth/login",
        json={"username": username, "password": "foobar!"},
    ).json()["token"]
    consent = client.post(
        f"{base}/consents", json={"access": {"availableAccounts": "allAccounts"}}
    ).json()
    consent_id = consent["consentId"]
    auth = client.post(f"{base}/consents/{consent_id}/authorisations").json()
    client.put(
        f"{base}/consents/{consent_id}/authorisations/{auth['authorisationId']}",
        json={"scaAuthenticationData": "000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    accounts = client.get(f"{base}/accounts", headers={"Consent-ID": consent_id}).json()
    return next(a["iban"] for a in accounts["accounts"] if a["resourceId"] == account_id)


def test_settlement_listed_in_architecture(client: TestClient):
    arch = client.get("/architecture").json()
    settlement = next(c for c in arch["capabilities"] if c["kind"] == "settlement")
    assert settlement["status"] == "implemented"
    assert "rtgs" in settlement["implementations"]


def test_payment_initiation_settles(client: TestClient):
    bank_id, account_id, iban = _bank_with_funded_account(client)
    base = f"/xs2a/{bank_id}/v1"
    product = "sepa-credit-transfers"

    balance_before = float(
        client.get(f"/banks/{bank_id}/accounts").json()[0]["balance"].split()[0]
    )

    payment = client.post(
        f"{base}/payments/{product}",
        json={
            "instructedAmount": {"currency": "EUR", "amount": "42.50"},
            "debtorAccount": {"iban": iban},
            "creditorAccount": {"iban": "DE00BSYMEXTERNAL00000000"},
            "creditorName": "Landlord",
            "remittanceInformationUnstructured": "Rent",
        },
    )
    assert payment.status_code == 201
    body = payment.json()
    assert body["transactionStatus"] == "RCVD"
    payment_id = body["paymentId"]

    # Authorise (auto-approve SCA) -> triggers settlement.
    auth = client.post(f"{base}/payments/{product}/{payment_id}/authorisations").json()
    put = client.put(
        f"{base}/payments/{product}/{payment_id}/authorisations/{auth['authorisationId']}",
        json={"scaAuthenticationData": "111111"},
    )
    assert put.json()["scaStatus"] == "finalised"

    status = client.get(f"{base}/payments/{product}/{payment_id}/status").json()
    assert status["transactionStatus"] == "ACSC"

    balance_after = float(
        client.get(f"/banks/{bank_id}/accounts").json()[0]["balance"].split()[0]
    )
    assert round(balance_before - balance_after, 2) == 42.50


def test_payment_rejected_when_insufficient_funds(client: TestClient):
    bank_id, account_id, iban = _bank_with_funded_account(client, fund=False)
    base = f"/xs2a/{bank_id}/v1"
    product = "sepa-credit-transfers"

    payment = client.post(
        f"{base}/payments/{product}",
        json={
            "instructedAmount": {"currency": "EUR", "amount": "100.00"},
            "debtorAccount": {"iban": iban},
            "creditorAccount": {"iban": "DE00BSYMEXTERNAL00000000"},
        },
    ).json()
    payment_id = payment["paymentId"]
    auth = client.post(f"{base}/payments/{product}/{payment_id}/authorisations").json()
    client.put(
        f"{base}/payments/{product}/{payment_id}/authorisations/{auth['authorisationId']}",
        json={},
    )
    status = client.get(f"{base}/payments/{product}/{payment_id}/status").json()
    assert status["transactionStatus"] == "RJCT"


def test_payment_unknown_debtor_rejected(client: TestClient):
    bank = client.post("/banks", json={"display_name": "X", "country": "DE"}).json()
    base = f"/xs2a/{bank['id']}/v1"
    resp = client.post(
        f"{base}/payments/sepa-credit-transfers",
        json={
            "instructedAmount": {"currency": "EUR", "amount": "10.00"},
            "debtorAccount": {"iban": "DE00BSYMNOSUCHACCOUNT000"},
            "creditorAccount": {"iban": "DE00BSYMEXTERNAL00000000"},
        },
    )
    assert resp.status_code == 400
