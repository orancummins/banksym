"""End-to-end test: deferred (netting) settlement reconciled via the settlement cycle endpoint."""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


def _funded_bank(client: TestClient) -> tuple[str, str]:
    bank = client.post(
        "/banks",
        json={
            "display_name": "Netting Bank",
            "country": "DE",
            "capabilities": {"txgen": "rule_based", "settlement": "netting"},
        },
    ).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Payer", "persona": "young_professional"},
    ).json()
    account = client.post(
        f"/banks/{bank_id}/accounts", json={"currency": "EUR", "customer_id": customer["id"]}
    ).json()
    client.post(
        f"/banks/{bank_id}/accounts/{account['id']}/generate-history",
        json={"start": "2025-01-01", "end": "2025-03-31", "seed": 4},
    )
    # Resolve the IBAN via AIS.
    base = f"/xs2a/{bank_id}/v1"
    token = client.post(
        f"/banks/{bank_id}/auth/login",
        json={"username": customer["username"], "password": "foobar!"},
    ).json()["token"]
    consent = client.post(
        f"{base}/consents", json={"access": {"availableAccounts": "allAccounts"}}
    ).json()
    cid = consent["consentId"]
    auth = client.post(f"{base}/consents/{cid}/authorisations").json()
    client.put(
        f"{base}/consents/{cid}/authorisations/{auth['authorisationId']}",
        json={"scaAuthenticationData": "000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    accounts = client.get(f"{base}/accounts", headers={"Consent-ID": cid}).json()
    iban = accounts["accounts"][0]["iban"]
    return bank_id, iban


def test_netting_payment_pending_then_settled_by_cycle(client: TestClient):
    bank_id, iban = _funded_bank(client)
    base = f"/xs2a/{bank_id}/v1"
    product = "sepa-credit-transfers"

    payment = client.post(
        f"{base}/payments/{product}",
        json={
            "instructedAmount": {"currency": "EUR", "amount": "30.00"},
            "debtorAccount": {"iban": iban},
            "creditorAccount": {"iban": "DE00BSYMEXTERNAL00000000"},
            "creditorName": "Vendor",
        },
    ).json()
    payment_id = payment["paymentId"]
    auth = client.post(f"{base}/payments/{product}/{payment_id}/authorisations").json()
    client.put(
        f"{base}/payments/{product}/{payment_id}/authorisations/{auth['authorisationId']}",
        json={"scaAuthenticationData": "111111"},
    )

    # Deferred: accepted-technical-validation, awaiting the cycle.
    status = client.get(f"{base}/payments/{product}/{payment_id}/status").json()
    assert status["transactionStatus"] == "ACTC"

    cycle = client.post(f"/banks/{bank_id}/settlement/run-cycle")
    assert cycle.status_code == 200
    assert len(cycle.json()["settled"]) >= 1

    settled = client.get(f"{base}/payments/{product}/{payment_id}/status").json()
    assert settled["transactionStatus"] == "ACSC"


def test_rtgs_cycle_is_empty(client: TestClient):
    bank = client.post(
        "/banks",
        json={"display_name": "RTGS Bank", "country": "DE", "capabilities": {"settlement": "rtgs"}},
    ).json()
    cycle = client.post(f"/banks/{bank['id']}/settlement/run-cycle")
    assert cycle.status_code == 200
    assert cycle.json()["settled"] == []
