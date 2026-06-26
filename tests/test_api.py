"""End-to-end API tests covering bank instantiation through history generation."""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


def test_health(client: TestClient):
    assert client.get("/health").json()["status"] == "ok"


def test_full_flow(client: TestClient):
    # Instantiate a bank.
    bank = client.post(
        "/banks",
        json={
            "display_name": "Banco de Prueba",
            "country": "ES",
            "locale": "es",
            "base_currency": "EUR",
            "capabilities": {"txgen": "rule_based"},
        },
    ).json()
    bank_id = bank["id"]

    # Create a persona customer and account.
    customer = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Lucia Gomez", "persona": "young_professional"},
    ).json()
    account = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "EUR", "customer_id": customer["id"]},
    ).json()

    # Generate history.
    gen = client.post(
        f"/banks/{bank_id}/accounts/{account['id']}/generate-history",
        json={"generator": "rule_based", "start": "2025-01-01", "end": "2025-02-28", "seed": 7},
    )
    assert gen.status_code == 200
    assert gen.json()["entries_booked"] > 0

    # Transactions are visible.
    txns = client.get(f"/banks/{bank_id}/accounts/{account['id']}/transactions").json()
    assert len(txns) == gen.json()["entries_booked"]
    sample = next((t for t in txns if t.get("category") != "income"), txns[0])
    assert sample["merchant_name"]
    assert sample["category"]
    assert sample["payment_reference"]
    assert sample["location"]
    assert sample["channel"]


def test_tenant_isolation_via_api(client: TestClient):
    bank_a = client.post("/banks", json={"display_name": "A", "country": "DE"}).json()
    bank_b = client.post("/banks", json={"display_name": "B", "country": "FR"}).json()
    client.post(f"/banks/{bank_a['id']}/customers", json={"full_name": "Alice"})
    customers_b = client.get(f"/banks/{bank_b['id']}/customers").json()
    assert customers_b == []


def test_unknown_bank_404(client: TestClient):
    resp = client.get("/banks/bank_does_not_exist/customers")
    assert resp.status_code == 404
