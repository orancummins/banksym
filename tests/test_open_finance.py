"""Open Finance adapter and dated transaction import.

The Open Finance surface exists alongside Berlin Group because a US consumer-finance
aggregator is shaped differently from PSD2: opaque account ids and masks rather than
IBANs, credit cards as first-class accounts, and enrichment (merchant, category,
channel) on every transaction.
"""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


def _seed(client: TestClient) -> tuple[str, str, str, str]:
    """A US bank with one customer holding a checking account and a credit card."""
    bank = client.post(
        "/banks",
        json={"display_name": "Test US Bank", "country": "US", "base_currency": "USD"},
    ).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers", json={"full_name": "Alex Morgan"}
    ).json()
    checking = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "USD", "customer_id": customer["id"], "type": "current",
              "name": "Everyday Checking"},
    ).json()
    card = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "USD", "customer_id": customer["id"], "type": "credit_card",
              "name": "Rewards Card"},
    ).json()
    return bank_id, customer["id"], checking["id"], card["id"]


def test_import_preserves_date_merchant_and_category(client):
    bank_id, customer_id, checking, card = _seed(client)
    res = client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": card, "amount": "42.50", "side": "debit",
             "booked_at": "2025-11-04T00:00:00Z", "description": "PUBLIX",
             "merchant_name": "publix", "category": "supermarket", "channel": "in_store"},
            {"account_id": checking, "amount": "4180.00", "side": "credit",
             "booked_at": "2025-11-01T00:00:00Z", "description": "PAYROLL",
             "merchant_name": "employer", "category": "income"},
        ]},
    )
    assert res.status_code == 201, res.text
    assert res.json() == {"imported": 2, "accounts": 2}

    txns = client.get(
        f"/openfinance/{bank_id}/v1/accounts/{card}/transactions", headers=AUTH
    ).json()["transactions"]
    assert len(txns) == 1
    t = txns[0]
    assert t["postedDate"] == "2025-11-04", "back-dating was lost on import"
    assert t["merchantName"] == "publix"
    assert t["category"] == "supermarket"
    assert t["channel"] == "in_store"
    assert t["amount"] == "-42.50", "a debit must be reported as money out"


def test_income_is_reported_as_a_positive_amount(client):
    bank_id, _customer, checking, _card = _seed(client)
    client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": checking, "amount": "4180.00", "side": "credit",
             "booked_at": "2025-11-01T00:00:00Z", "description": "PAYROLL"},
        ]},
    )
    txns = client.get(
        f"/openfinance/{bank_id}/v1/accounts/{checking}/transactions", headers=AUTH
    ).json()["transactions"]
    assert txns[0]["amount"] == "4180.00"


def test_customer_accounts_lists_cards_and_deposits(client):
    bank_id, customer_id, checking, card = _seed(client)
    body = client.get(
        f"/openfinance/{bank_id}/v1/customers/{customer_id}/accounts", headers=AUTH
    ).json()
    types = {a["accountId"]: a["accountType"] for a in body["accounts"]}
    assert types[checking] == "checking"
    assert types[card] == "creditCard"
    for account in body["accounts"]:
        assert account["balances"], "every account must report a balance"
        assert account["institutionId"] == bank_id


def test_credit_card_balance_is_reported_as_a_positive_amount_owed(client):
    """Core keeps a card negative when money is owed; aggregators report what is owed."""
    bank_id, customer_id, _checking, card = _seed(client)
    client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": card, "amount": "100.00", "side": "debit",
             "booked_at": "2025-11-04T00:00:00Z", "description": "SPEND"},
        ]},
    )
    account = client.get(
        f"/openfinance/{bank_id}/v1/accounts/{card}", headers=AUTH
    ).json()
    assert account["balances"][0]["amount"] == "100.00"


def test_internal_accounts_are_never_exposed(client):
    """The External world contra account must not surface as a customer account."""
    bank_id, customer_id, _checking, card = _seed(client)
    client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": card, "amount": "10.00", "side": "debit",
             "booked_at": "2025-11-04T00:00:00Z", "description": "SPEND"},
        ]},
    )
    body = client.get(
        f"/openfinance/{bank_id}/v1/customers/{customer_id}/accounts", headers=AUTH
    ).json()
    assert all(a["accountType"] != "other" for a in body["accounts"])
    assert len(body["accounts"]) == 2


def test_date_filtering(client):
    bank_id, _customer, checking, _card = _seed(client)
    client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": checking, "amount": "10.00", "side": "credit",
             "booked_at": "2025-10-01T00:00:00Z", "description": "A"},
            {"account_id": checking, "amount": "20.00", "side": "credit",
             "booked_at": "2025-12-01T00:00:00Z", "description": "B"},
        ]},
    )
    url = f"/openfinance/{bank_id}/v1/accounts/{checking}/transactions"
    assert len(client.get(url, headers=AUTH).json()["transactions"]) == 2
    windowed = client.get(
        url, params={"fromDate": "2025-11-01", "toDate": "2026-01-01"}, headers=AUTH
    ).json()["transactions"]
    assert len(windowed) == 1
    assert windowed[0]["description"] == "B"


def test_endpoints_require_a_bearer_token(client):
    bank_id, customer_id, checking, _card = _seed(client)
    for url in (
        f"/openfinance/{bank_id}/v1/customers/{customer_id}/accounts",
        f"/openfinance/{bank_id}/v1/accounts/{checking}/transactions",
    ):
        assert client.get(url).status_code == 401
        assert client.get(url, headers=AUTH).status_code == 200


def test_unknown_institution_and_account_are_404(client):
    bank_id, _customer, _checking, _card = _seed(client)
    assert client.get("/openfinance/bank_nope/v1/institution").status_code == 404
    assert client.get(
        f"/openfinance/{bank_id}/v1/accounts/acc_nope", headers=AUTH
    ).status_code == 404


def test_berlin_group_still_works_alongside(client):
    """Adding a protocol must not disturb the existing one."""
    assert client.get("/architecture").status_code == 200


# --- tenant logos -----------------------------------------------------------


def test_bank_logos_are_served_locally(client):
    """Logos are vendored, not hot-linked, so branding survives with no network."""
    for name in ("citi.svg", "chase.svg"):
        r = client.get(f"/logos/{name}")
        assert r.status_code == 200, name
        assert r.headers["content-type"].startswith("image/svg+xml")
        assert r.content


def test_logo_route_will_not_serve_files_outside_its_directory(client):
    """A crafted filename must not reach anything but ui/logos."""
    for attempt in ("..%2F..%2Fpyproject.toml", "..%2Fbanksym.png", "nope.svg"):
        assert client.get(f"/logos/{attempt}").status_code == 404


def test_vendored_logos_carry_no_active_content():
    """SVG can carry script. These are decoration and must stay inert."""
    import pathlib

    logos = pathlib.Path(__file__).resolve().parent.parent / "ui" / "logos"
    for svg in logos.glob("*.svg"):
        body = svg.read_text(errors="ignore").lower()
        for danger in ("<script", "javascript:", "onload=", "onerror=", "<foreignobject"):
            assert danger not in body, f"{svg.name} contains {danger}"


def test_a_bank_can_carry_a_logo_url(client):
    bank = client.post(
        "/banks",
        json={"display_name": "Logo Bank", "country": "US", "base_currency": "USD",
              "logo_url": "/logos/citi.svg"},
    ).json()
    assert bank["logo_url"] == "/logos/citi.svg"
    assert client.get(f"/banks/{bank['id']}").json()["logo_url"] == "/logos/citi.svg"
