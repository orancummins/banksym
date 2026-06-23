"""Tests for bank deletion and duplicate display-name prevention."""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container
from banksym.tenancy.repository import InMemoryBankRepository
from banksym.tenancy.service import BankService, DuplicateBankNameError


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


# -- Service-level -----------------------------------------------------------
def test_duplicate_display_name_rejected():
    service = BankService(InMemoryBankRepository())
    service.create_bank(display_name="Acme Bank", country="DE")
    with pytest.raises(DuplicateBankNameError):
        service.create_bank(display_name="Acme Bank", country="FR")


def test_duplicate_name_is_case_insensitive():
    service = BankService(InMemoryBankRepository())
    service.create_bank(display_name="Acme Bank", country="DE")
    with pytest.raises(DuplicateBankNameError):
        service.create_bank(display_name="  acme bank ", country="FR")


def test_delete_then_name_reusable():
    service = BankService(InMemoryBankRepository())
    bank = service.create_bank(display_name="Acme Bank", country="DE")
    service.delete_bank(bank.id)
    # Name can be reused after deletion.
    again = service.create_bank(display_name="Acme Bank", country="DE")
    assert again.id != bank.id


# -- API-level ---------------------------------------------------------------
def test_create_duplicate_via_api_returns_400(client: TestClient):
    client.post("/banks", json={"display_name": "Dup Bank", "country": "DE"})
    resp = client.post("/banks", json={"display_name": "Dup Bank", "country": "FR"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "duplicate_bank_name"


def test_delete_bank_purges_data(client: TestClient):
    bank = client.post("/banks", json={"display_name": "Temp Bank", "country": "DE"}).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers", json={"full_name": "Jane"}
    ).json()
    client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "EUR", "customer_id": customer["id"]},
    )

    deleted = client.delete(f"/banks/{bank_id}")
    assert deleted.status_code == 204

    # Bank is gone.
    assert client.get(f"/banks/{bank_id}").status_code == 404
    # Scoped resources are gone too.
    assert client.get(f"/banks/{bank_id}/customers").status_code == 404
    assert bank_id not in [b["id"] for b in client.get("/banks").json()]


def test_delete_unknown_bank_returns_404(client: TestClient):
    assert client.delete("/banks/bank_missing").status_code == 404


def test_delete_isolates_other_banks(client: TestClient):
    a = client.post("/banks", json={"display_name": "Bank A", "country": "DE"}).json()
    b = client.post("/banks", json={"display_name": "Bank B", "country": "FR"}).json()
    client.post(f"/banks/{b['id']}/customers", json={"full_name": "Bob"})

    client.delete(f"/banks/{a['id']}")

    # Bank B and its data survive.
    assert client.get(f"/banks/{b['id']}").status_code == 200
    customers_b = client.get(f"/banks/{b['id']}/customers").json()
    assert [c["full_name"] for c in customers_b] == ["Bob"]
