"""FDX adapter tests.

FDX is the US open banking standard, and its modelling is genuinely different from
Berlin Group's: polymorphic account and transaction envelopes, direction carried by
debitCreditMemo rather than the sign of the amount, and credit cards as
line-of-credit accounts with a LIABILITY balance.
"""

import pytest
from fastapi.testclient import TestClient

from banksym.api.app import create_app
from banksym.api.container import reset_container

AUTH = {"Authorization": "Bearer fdx-test-token"}


@pytest.fixture
def client() -> TestClient:
    reset_container()
    return TestClient(create_app())


def _seed(client: TestClient):
    bank = client.post(
        "/banks",
        json={"display_name": "FDX Test Bank", "country": "US", "base_currency": "USD",
              "enabled_protocols": ["fdx"]},
    ).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Alex Morgan", "email": "alex@example.com"},
    ).json()
    checking = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "USD", "customer_id": customer["id"], "type": "current",
              "name": "Everyday Checking", "metadata": {"mask": "4412"}},
    ).json()
    card = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "USD", "customer_id": customer["id"], "type": "credit_card",
              "name": "Rewards Card", "metadata": {"mask": "9021"}},
    ).json()
    client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": card["id"], "amount": "85.20", "side": "debit",
             "booked_at": "2025-11-04T00:00:00Z", "description": "PUBLIX",
             "merchant_name": "publix", "category": "supermarket"},
            {"account_id": checking["id"], "amount": "4180.00", "side": "credit",
             "booked_at": "2025-11-01T00:00:00Z", "description": "NORTHWIND PAYROLL",
             "merchant_name": "employer", "category": "income"},
        ]},
    )
    return bank_id, customer["id"], checking["id"], card["id"]


def test_accounts_use_the_polymorphic_fdx_envelope(client):
    """A client dispatches on the wrapper key, so the right one must be populated."""
    bank_id, customer_id, checking, card = _seed(client)
    body = client.get(f"/fdx/{bank_id}/v6/accounts", headers=AUTH).json()
    assert body["page"]["totalElements"] == 2

    by_id = {}
    for entry in body["accounts"]:
        assert sum(1 for v in entry.values() if v) == 1, "exactly one typed account per entry"
        account = entry.get("depositAccount") or entry.get("locAccount")
        by_id[account["accountId"]] = entry

    assert by_id[checking]["depositAccount"] is not None
    assert by_id[checking]["locAccount"] is None
    assert by_id[checking]["depositAccount"]["accountType"] == "CHECKING"
    assert by_id[checking]["depositAccount"]["accountCategory"] == "DEPOSIT_ACCOUNT"

    # A credit card is a line of credit in FDX, not a deposit account.
    assert by_id[card]["locAccount"] is not None
    assert by_id[card]["depositAccount"] is None
    assert by_id[card]["locAccount"]["accountType"] == "CREDITCARD"
    assert by_id[card]["locAccount"]["accountCategory"] == "LINE_OF_CREDIT_ACCOUNT"


def test_card_balance_is_a_positive_liability(client):
    """The core holds a card negative when owed; FDX reports it positive, LIABILITY."""
    bank_id, _customer, _checking, card = _seed(client)
    loc = client.get(f"/fdx/{bank_id}/v6/accounts/{card}", headers=AUTH).json()["locAccount"]
    assert loc["balanceType"] == "LIABILITY"
    assert loc["currentBalance"] == pytest.approx(85.20)


def test_deposit_balance_is_an_asset(client):
    bank_id, _customer, checking, _card = _seed(client)
    dep = client.get(
        f"/fdx/{bank_id}/v6/accounts/{checking}", headers=AUTH
    ).json()["depositAccount"]
    assert dep["balanceType"] == "ASSET"
    assert dep["currentBalance"] == pytest.approx(4180.00)


def test_direction_is_carried_by_debit_credit_memo_not_the_sign(client):
    """FDX amounts are always positive; direction lives in debitCreditMemo."""
    bank_id, _customer, checking, card = _seed(client)

    spend = client.get(
        f"/fdx/{bank_id}/v6/accounts/{card}/transactions", headers=AUTH
    ).json()["transactions"][0]["locTransaction"]
    assert spend["debitCreditMemo"] == "DEBIT"
    assert spend["amount"] == pytest.approx(85.20), "amount must be positive"
    assert spend["payee"] == "publix"
    assert spend["category"] == "supermarket"

    income = client.get(
        f"/fdx/{bank_id}/v6/accounts/{checking}/transactions", headers=AUTH
    ).json()["transactions"][0]["depositTransaction"]
    assert income["debitCreditMemo"] == "CREDIT"
    assert income["amount"] == pytest.approx(4180.00)


def test_transactions_use_the_matching_polymorphic_envelope(client):
    bank_id, _customer, checking, card = _seed(client)
    card_txns = client.get(
        f"/fdx/{bank_id}/v6/accounts/{card}/transactions", headers=AUTH
    ).json()["transactions"]
    assert all(t["locTransaction"] and not t["depositTransaction"] for t in card_txns)
    dep_txns = client.get(
        f"/fdx/{bank_id}/v6/accounts/{checking}/transactions", headers=AUTH
    ).json()["transactions"]
    assert all(t["depositTransaction"] and not t["locTransaction"] for t in dep_txns)


def test_posted_timestamp_is_an_instant_and_back_dating_survives(client):
    bank_id, _customer, _checking, card = _seed(client)
    t = client.get(
        f"/fdx/{bank_id}/v6/accounts/{card}/transactions", headers=AUTH
    ).json()["transactions"][0]["locTransaction"]
    assert t["postedTimestamp"].startswith("2025-11-04")


def test_time_window_filtering(client):
    bank_id, _customer, checking, _card = _seed(client)
    url = f"/fdx/{bank_id}/v6/accounts/{checking}/transactions"
    assert len(client.get(url, headers=AUTH).json()["transactions"]) == 1
    empty = client.get(
        url, params={"startTime": "2026-01-01T00:00:00Z"}, headers=AUTH
    ).json()["transactions"]
    assert empty == []


def test_accounts_can_be_scoped_to_a_customer(client):
    bank_id, customer_id, _checking, _card = _seed(client)
    body = client.get(
        f"/fdx/{bank_id}/v6/accounts", params={"customerId": customer_id}, headers=AUTH
    ).json()
    assert body["page"]["totalElements"] == 2


def test_current_customer(client):
    bank_id, customer_id, _checking, _card = _seed(client)
    body = client.get(f"/fdx/{bank_id}/v6/customers/current", headers=AUTH).json()
    assert body["customerId"] == customer_id
    assert body["name"] == {"first": "Alex", "last": "Morgan"}
    assert body["email"] == ["alex@example.com"]


def test_oauth_bearer_token_is_required(client):
    bank_id, _customer, checking, _card = _seed(client)
    for url in (
        f"/fdx/{bank_id}/v6/accounts",
        f"/fdx/{bank_id}/v6/accounts/{checking}/transactions",
        f"/fdx/{bank_id}/v6/customers/current",
    ):
        assert client.get(url).status_code == 401
        assert client.get(url, headers=AUTH).status_code == 200


def test_internal_accounts_are_never_exposed(client):
    """The External world contra account must not appear as a customer account."""
    bank_id, _customer, _checking, _card = _seed(client)
    body = client.get(f"/fdx/{bank_id}/v6/accounts", headers=AUTH).json()
    assert body["page"]["totalElements"] == 2

    internal = [
        a for a in client.get(f"/banks/{bank_id}/accounts").json()
        if a["type"] == "internal"
    ]
    assert internal, "expected an internal contra account to exist"
    assert client.get(
        f"/fdx/{bank_id}/v6/accounts/{internal[0]['id']}", headers=AUTH
    ).status_code == 404


def test_unknown_bank_and_account_are_404(client):
    bank_id, *_ = _seed(client)
    assert client.get("/fdx/bank_nope/v6/accounts", headers=AUTH).status_code == 404
    assert client.get(
        f"/fdx/{bank_id}/v6/accounts/acc_nope", headers=AUTH
    ).status_code == 404


def test_all_three_protocols_coexist(client):
    """Adding FDX must not disturb Berlin Group or Open Finance."""
    from banksym.capabilities.protocols.base import api_registry

    assert {"berlin_group", "fdx", "open_finance"} <= set(api_registry.names())


def _seed_card_with_limit(client: TestClient, credit_limit: str):
    """A dedicated bank/customer/card, with credit_limit set at creation.

    There is no account-update endpoint in BankSym, so a limit set via metadata
    has to be present on the POST that creates the account -- mutating a fetched
    Account object in-process does not persist, since the repository loads a
    fresh copy on every request.
    """
    bank = client.post(
        "/banks",
        json={"display_name": "FDX Limit Test Bank", "country": "US",
              "base_currency": "USD", "enabled_protocols": ["fdx"]},
    ).json()
    bank_id = bank["id"]
    customer = client.post(
        f"/banks/{bank_id}/customers",
        json={"full_name": "Alex Morgan", "email": "alex@example.com"},
    ).json()
    card = client.post(
        f"/banks/{bank_id}/accounts",
        json={"currency": "USD", "customer_id": customer["id"], "type": "credit_card",
              "name": "Limited Card", "metadata": {"mask": "1234", "credit_limit": credit_limit}},
    ).json()
    return bank_id, card["id"]


def test_available_credit_is_computed_from_a_credit_limit_in_metadata(client):
    """Credit limit is underwriting data for one cardholder, not a core ledger
    concept BankSym models natively, so it rides in account metadata. A client
    that only ever sees currentBalance cannot tell whether a purchase will
    actually be approved -- availableCredit is the reason to ask for this account
    at all.
    """
    bank_id, card = _seed_card_with_limit(client, "1000.00")
    body = client.get(f"/fdx/{bank_id}/v6/accounts/{card}", headers=AUTH).json()
    assert body["locAccount"]["availableCredit"] == pytest.approx(1000.00)


def test_available_credit_nets_against_the_owed_balance(client):
    bank_id, card = _seed_card_with_limit(client, "1000.00")
    client.post(
        f"/banks/{bank_id}/transactions/import",
        json={"transactions": [
            {"account_id": card, "amount": "300.00", "side": "debit",
             "booked_at": "2025-11-10T00:00:00Z", "description": "SPEND"},
        ]},
    )
    body = client.get(f"/fdx/{bank_id}/v6/accounts/{card}", headers=AUTH).json()
    loc = body["locAccount"]
    assert loc["currentBalance"] == pytest.approx(300.00)
    assert loc["availableCredit"] == pytest.approx(700.00)


def test_available_credit_is_none_without_a_credit_limit(client):
    """No limit set means no claim is made -- never a fabricated default."""
    bank_id, _customer, _checking, card = _seed(client)
    body = client.get(f"/fdx/{bank_id}/v6/accounts/{card}", headers=AUTH).json()
    assert body["locAccount"]["availableCredit"] is None
