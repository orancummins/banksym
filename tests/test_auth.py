"""Tests for the simple auth provider and auto-approve SCA, plus the auth API."""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container
from banksym.capabilities.auth.base import InMemoryCredentialStore, InMemorySessionStore
from banksym.capabilities.auth.simple import AutoApproveSca, SimpleAuthProvider


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


def test_password_round_trip():
    provider = SimpleAuthProvider(InMemoryCredentialStore(), InMemorySessionStore())
    provider.register("bank_1", "alice", "s3cret", "cus_1")
    assert provider.authenticate("bank_1", "alice", "s3cret") is not None
    assert provider.authenticate("bank_1", "alice", "wrong") is None


def test_password_is_hashed_not_stored_plain():
    store = InMemoryCredentialStore()
    provider = SimpleAuthProvider(store, InMemorySessionStore())
    cred = provider.register("bank_1", "bob", "hunter2", "cus_2")
    assert "hunter2" not in cred.secret_hash
    assert "$" in cred.secret_hash


def test_sca_auto_approves():
    sca = AutoApproveSca()
    challenge = sca.start_challenge("bank_1", "cus_1")
    assert challenge.verified is True
    assert sca.verify(challenge) is True


def test_auth_api_flow(client: TestClient):
    bank = client.post("/banks", json={"display_name": "Auth Bank", "country": "DE"}).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers", json={"full_name": "Ada"}
    ).json()
    client.post(
        f"/banks/{bank_id}/auth/credentials",
        json={"username": "ada", "password": "pw12345", "customer_id": customer["id"]},
    )
    login = client.post(
        f"/banks/{bank_id}/auth/login", json={"username": "ada", "password": "pw12345"}
    )
    assert login.status_code == 200
    token = login.json()["token"]

    session = client.get(
        f"/banks/{bank_id}/auth/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert session.status_code == 200
    assert session.json()["customer_id"] == customer["id"]

    logout = client.post(
        f"/banks/{bank_id}/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert logout.status_code == 204
    after = client.get(
        f"/banks/{bank_id}/auth/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert after.status_code == 401


def test_login_rejects_bad_password(client: TestClient):
    bank = client.post("/banks", json={"display_name": "B", "country": "DE"}).json()
    bank_id = bank["id"]
    customer = client.post(f"/banks/{bank_id}/customers", json={"full_name": "X"}).json()
    client.post(
        f"/banks/{bank_id}/auth/credentials",
        json={"username": "x", "password": "right", "customer_id": customer["id"]},
    )
    bad = client.post(
        f"/banks/{bank_id}/auth/login", json={"username": "x", "password": "wrong"}
    )
    assert bad.status_code == 401
