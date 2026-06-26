"""Per-bank core banking endpoints: customers, accounts, transactions, history generation."""

from __future__ import annotations

import math
import random
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from banksym.api.deps import BankIdDep, ContainerDep, to_http_error
from banksym.api.schemas import (
    AccountResponse,
    BatchCreateCustomersRequest,
    BatchCreateCustomersResponse,
    BankStatsResponse,
    CreateCustomerRequest,
    CustomerResponse,
    GenerateHistoryRequest,
    GenerateHistoryResponse,
    OpenAccountRequest,
    PostTransactionRequest,
    TransactionResponse,
)
from banksym.capabilities.localization.address import random_address, random_full_name, random_phone
from banksym.capabilities.txgen.base import GenerationRequest
from banksym.capabilities.txgen.personas import PERSONAS
from banksym.core.domain.account import Account, AccountType
from banksym.core.domain.customer import Customer
from banksym.core.kernel.errors import BankSymError
from banksym.core.kernel.ids import new_id  # noqa: F401  (available for future use)

router = APIRouter(prefix="/banks/{bank_id}", tags=["banking"])


# ---------------------------------------------------------------------------
# Account metadata helpers
# ---------------------------------------------------------------------------

def _rand_opened_at() -> str:
    """Random open date within the last 3 years, as an ISO date string."""
    days_ago = random.randint(0, 3 * 365)
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _account_metadata(acct_type: AccountType, currency: str) -> dict:
    """Return a dict of realistic, type-specific account attributes."""
    opened = _rand_opened_at()
    if acct_type == AccountType.CURRENT:
        return {
            "opened_at": opened,
            "overdraft_limit": round(random.choice([0, -200, -500, -1000, -2000]), 2),
            "interest_rate": 0.0,
            "monthly_fee": random.choice([0.0, 0.0, 0.0, 5.0, 10.0]),
        }
    if acct_type == AccountType.SAVINGS:
        rate = round(random.uniform(0.03, 0.06), 4)
        return {
            "opened_at": opened,
            "interest_rate": rate,
            "interest_paid_at": random.choice(["monthly", "annual"]),
            "notice_period_days": random.choice([0, 0, 30, 60, 90]),
        }
    if acct_type == AccountType.CREDIT_CARD:
        limit = round(random.choice([500, 1000, 1500, 2000, 3000, 5000, 7500, 10000]), 2)
        apr = round(random.uniform(0.19, 0.39), 4)
        return {
            "opened_at": opened,
            "credit_limit": limit,
            "interest_rate": apr,
            "statement_day": random.randint(1, 28),
            "payment_due_days": random.choice([14, 28]),
            "minimum_payment_pct": round(random.choice([0.01, 0.02, 0.025, 0.03]), 3),
        }
    if acct_type == AccountType.LOAN:
        principal = round(random.choice([5000, 10000, 15000, 20000, 25000, 30000, 40000, 50000]), 2)
        annual_rate = round(random.uniform(0.05, 0.15), 4)
        term = random.choice([12, 24, 36, 48, 60])
        # Monthly instalment via standard annuity formula.
        r = annual_rate / 12
        monthly = round(principal * r / (1 - (1 + r) ** -term), 2) if r > 0 else round(principal / term, 2)
        return {
            "opened_at": opened,
            "principal": principal,
            "interest_rate": annual_rate,
            "term_months": term,
            "monthly_payment": monthly,
        }
    return {"opened_at": opened}


def _account_response(container: ContainerDep, bank_id: str, account: Account) -> AccountResponse:
    balance = container.banking.balance(bank_id, account.id)
    return AccountResponse(
        id=account.id,
        currency=account.currency,
        type=account.type,
        status=account.status,
        customer_id=account.customer_id,
        iban=account.iban,
        name=account.name,
        balance=str(balance),
        metadata=account.metadata,
    )


@router.post(
    "/customers", response_model=CustomerResponse, status_code=201, summary="Create a customer"
)
def create_customer(
    body: CreateCustomerRequest, bank_id: BankIdDep, container: ContainerDep
) -> CustomerResponse:
    """Create a customer within a bank and issue online-banking credentials.

    Every customer is automatically given credentials so they can authenticate in the Open Banking
    flow: the username defaults to their email (or an explicit ``username``) and the password
    defaults to ``foobar!`` unless one is supplied. The chosen ``persona`` influences generated
    transaction history. A plausible postal address is generated for the customer's country (or the
    bank's country if none is given) unless an explicit ``address`` is supplied.
    """
    country = body.country or container.bank_service.get_bank(bank_id).country
    address = body.address or random_address(country)
    phone = body.phone or random_phone(country)
    customer = container.banking.create_customer(
        bank_id,
        body.full_name,
        email=body.email,
        phone=phone,
        country=body.country,
        address=address,
        persona=body.persona,
    )
    # Every customer gets online-banking credentials (username defaults to email, password
    # "foobar!") so they can authenticate in Open Banking.
    username = container.register_customer_credential(
        bank_id, customer.id, username=body.username, password=body.password
    )
    return CustomerResponse(
        id=customer.id,
        full_name=customer.full_name,
        email=customer.email,
        phone=customer.phone,
        persona=customer.persona,
        address=customer.address,
        username=username,
    )


@router.get("/customers", response_model=list[CustomerResponse], summary="List customers")
def list_customers(bank_id: BankIdDep, container: ContainerDep) -> list[CustomerResponse]:
    """List every customer of a bank together with their online-banking username."""
    customers = container.banking.list_customers(bank_id)
    credentials_by_id = container.credential_store.list_by_bank(bank_id)
    responses: list[CustomerResponse] = []
    for c in customers:
        credential = credentials_by_id.get(c.id)
        username = credential.username if credential else (c.email or c.id)
        responses.append(
            CustomerResponse(
                id=c.id,
                full_name=c.full_name,
                email=c.email,
                phone=c.phone,
                persona=c.persona,
                address=c.address,
                username=username,
                source=c.source,
            )
        )
    return responses


@router.post(
    "/accounts", response_model=AccountResponse, status_code=201, summary="Open an account"
)
def open_account(
    body: OpenAccountRequest, bank_id: BankIdDep, container: ContainerDep
) -> AccountResponse:
    """Open a new account for a customer in the given currency.

    An IBAN and display name may be supplied, otherwise sensible defaults are used. The response
    includes the opening balance.
    """
    bank = container.bank_service.get_bank(bank_id)
    currency = (body.currency or "").upper()
    allowed = set(bank.supported_currencies or [bank.base_currency])
    if currency not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Currency {currency} is not enabled for this bank",
        )
    try:
        account = container.banking.open_account(
            bank_id,
            currency,
            customer_id=body.customer_id,
            type=body.type,
            iban=body.iban,
            name=body.name,
            metadata=body.metadata,
        )
    except BankSymError as exc:
        raise to_http_error(exc) from exc
    return _account_response(container, bank_id, account)


@router.get("/accounts", response_model=list[AccountResponse], summary="List accounts")
def list_accounts(
    bank_id: BankIdDep, container: ContainerDep, customer_id: str | None = None
) -> list[AccountResponse]:
    """List accounts in a bank, optionally filtered to a single ``customer_id``."""
    return [
        _account_response(container, bank_id, a)
        for a in container.banking.list_accounts(bank_id, customer_id)
    ]


@router.get("/accounts/{account_id}", response_model=AccountResponse, summary="Get account details")
def get_account(
    account_id: str, bank_id: BankIdDep, container: ContainerDep
) -> AccountResponse:
    """Fetch a single account by ID."""
    try:
        account = container.banking.get_account(bank_id, account_id)
    except BankSymError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _account_response(container, bank_id, account)


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=list[TransactionResponse],
    summary="List account transactions",
)
def account_transactions(
    account_id: str, bank_id: BankIdDep, container: ContainerDep
) -> list[TransactionResponse]:
    """Return the booked transaction history for an account, newest entries last."""
    try:
        history = container.banking.transaction_history(bank_id, account_id)
    except BankSymError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        TransactionResponse(
            journal_id=r.journal_id,
            amount=str(r.amount),
            balance_after=str(r.balance_after),
            side=r.side.value,
            booked_at=r.booked_at,
            description=r.description,
            reference=r.reference,
            merchant_name=r.merchant_name,
            category=r.category,
            payment_reference=r.payment_reference,
            location=r.location,
            channel=r.channel,
        )
        for r in history
    ]


@router.post(
    "/accounts/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=201,
    summary="Post a single transaction",
)
def post_transaction(
    account_id: str,
    body: PostTransactionRequest,
    bank_id: BankIdDep,
    container: ContainerDep,
) -> TransactionResponse:
    """Post a single immediate transaction against an account.

    ``side="credit"`` moves money into the account from the bank's internal "External world"
    account; ``side="debit"`` moves it out. The amount is booked in the account's own currency
    (the optional ``currency`` must match it). Returns the resulting booked entry.
    """
    try:
        record = container.post_external_transaction(
            bank_id,
            account_id,
            amount=body.amount,
            currency=body.currency,
            side=body.side,
            description=body.description,
            reference=body.reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BankSymError as exc:
        raise to_http_error(exc) from exc
    # Surface manual transactions in the live feed too, so it survives page navigation.
    container.simulation.record_manual(bank_id, account_id, record)
    return TransactionResponse(
        journal_id=record.journal_id,
        amount=str(record.amount),
        balance_after=str(record.balance_after),
        side=record.side.value,
        booked_at=record.booked_at,
        description=record.description,
        reference=record.reference,
        merchant_name=record.merchant_name,
        category=record.category,
        payment_reference=record.payment_reference,
        location=record.location,
        channel=record.channel,
    )


@router.post(
    "/accounts/{account_id}/generate-history",
    response_model=GenerateHistoryResponse,
    summary="Generate transaction history",
)
def generate_history(
    account_id: str,
    body: GenerateHistoryRequest,
    bank_id: BankIdDep,
    container: ContainerDep,
) -> GenerateHistoryResponse:
    """Generate realistic transaction history for an account over a date range.

    Uses the selected transaction generator (defaulting to the bank's configured one) and the
    owning customer's persona to synthesise booked entries between ``start`` and ``end``. An
    optional ``seed`` makes the output deterministic. Returns the number of entries booked and the
    resulting balance.
    """
    try:
        account = container.banking.get_account(bank_id, account_id)
        customer = (
            container.banking.get_customer(bank_id, account.customer_id)
            if account.customer_id
            else None
        )
        generator = container.make_txgen(body.generator)
        bank = container.bank_service.get_bank(bank_id)
        request = GenerationRequest(
            bank_id=bank_id,
            customer=customer,  # type: ignore[arg-type]
            account=account,
            start=body.start,
            end=body.end,
            persona=customer.persona if customer else None,
            currency=account.currency,
            country=bank.country,
            language=bank.locale,
            seed=body.seed,
        )
        entries = generator.generate(request)  # type: ignore[attr-defined]
    except BankSymError as exc:
        raise to_http_error(exc) from exc
    balance = container.banking.balance(bank_id, account_id)
    return GenerateHistoryResponse(entries_booked=len(entries), balance=str(balance))


# ---------------------------------------------------------------------------
# Batch customer seeding
# ---------------------------------------------------------------------------

def _weighted_choice(weights: dict[str, float], population: list[str]) -> str:
    if not weights:
        return random.choice(population)
    keys = [k for k in weights if k in population or k in {k for k in population}]
    if not keys:
        return random.choice(population)
    w = [weights[k] for k in keys]
    return random.choices(keys, weights=w, k=1)[0]


def _normalized_shares(weights: dict[str, float], population: list[str]) -> dict[str, float]:
    filtered = {k: float(v) for k, v in weights.items() if k in population and float(v) > 0}
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in filtered.items()}


def _derived_account_types_for_customer(
    persona: str,
    acct_weights: dict[str, float],
    acct_type_pool: list[str],
) -> list[str]:
    if not acct_weights:
        return [AccountType.CURRENT.value]

    shares = _normalized_shares(acct_weights, acct_type_pool)
    if not shares:
        return [AccountType.CURRENT.value]

    primary = _weighted_choice(acct_weights, list(shares.keys()))
    selected: list[str] = [primary]
    max_accounts = 3 if persona in {"young_professional", "affluent_family"} else 2

    def maybe_add(acct_type: str, threshold: float, allowed_personas: set[str] | None = None) -> None:
        if acct_type in selected or acct_type not in shares or len(selected) >= max_accounts:
            return
        if allowed_personas is not None and persona not in allowed_personas:
            return
        if shares[acct_type] >= threshold:
            selected.append(acct_type)

    maybe_add(AccountType.CURRENT.value, 0.20)
    maybe_add(AccountType.SAVINGS.value, 0.18)
    maybe_add(AccountType.CREDIT_CARD.value, 0.16, {"student", "gig_worker", "young_professional", "affluent_family"})
    maybe_add(AccountType.LOAN.value, 0.12, {"young_professional", "affluent_family"})

    return selected[:max_accounts]


@router.post(
    "/customers/batch",
    response_model=BatchCreateCustomersResponse,
    status_code=201,
    summary="Batch-create customers",
)
def batch_create_customers(
    body: BatchCreateCustomersRequest,
    bank_id: BankIdDep,
    container: ContainerDep,
) -> BatchCreateCustomersResponse:
    """Create up to 10 000 customers with weighted persona and account-type distribution.

    ``persona_weights`` maps persona IDs to relative weights (e.g. ``{"student": 3, "retiree": 1}``);
    omit or leave empty for equal weighting. ``account_types`` maps account type names to weights.
    When ``accounts_per_customer`` is omitted, the number of accounts per customer is derived from
    the selected customer/account weighting criteria. All customers are flagged as ``source="batch"``
    and are collapsed in the Live feed tree rather than listed individually.
    """
    bank = container.bank_service.get_bank(bank_id)
    country = bank.country
    currency = bank.base_currency

    persona_pool = list(bank.supported_customer_types or PERSONAS.keys())
    acct_type_pool = [t.value for t in AccountType if t != AccountType.INTERNAL]

    # Normalise account-type weights — keep only valid types.
    acct_weights: dict[str, float] = {
        k: v for k, v in body.account_types.items() if k in acct_type_pool
    } if body.account_types else {}
    persona_weights: dict[str, float] = {
        k: v for k, v in body.persona_weights.items() if k in persona_pool
    } if body.persona_weights else {}

    customers: list[Customer] = []
    accounts: list[Account] = []
    persona_tally: Counter = Counter()
    acct_type_tally: Counter = Counter()

    for i in range(body.count):
        full_name = random_full_name(country)
        idx = str(i + 1)
        email_base = "".join(ch.lower() for ch in full_name if ch.isascii() and (ch.isalnum() or ch in {" ", "-", "_"})).strip().replace(" ", ".")
        if not email_base:
            email_base = f"customer{idx}"
        email = f"{email_base}{idx}@example.com"
        persona = _weighted_choice(persona_weights, persona_pool)
        address = random_address(country)
        phone = random_phone(country)
        customer = Customer(
            bank_id=bank_id,
            full_name=full_name,
            email=email,
            phone=phone,
            country=country,
            address=address,
            persona=persona,
            source="batch",
        )
        customers.append(customer)
        persona_tally[persona] += 1

        acct_targets = (
            _derived_account_types_for_customer(persona, acct_weights, acct_type_pool)
            if body.accounts_per_customer is None
            else [
                _weighted_choice(acct_weights, list(acct_weights.keys()) or acct_type_pool)
                if acct_weights else AccountType.CURRENT.value
                for _ in range(body.accounts_per_customer)
            ]
        )

        for acct_type_str in acct_targets:
            acct_type = AccountType(acct_type_str)
            account = Account(
                bank_id=bank_id,
                currency=currency,
                type=acct_type,
                customer_id=customer.id,
                metadata=_account_metadata(acct_type, currency),
            )
            accounts.append(account)
            acct_type_tally[acct_type_str] += 1

    # Persist all in one transaction.
    container.banking_repository.add_customers_and_accounts_bulk(customers, accounts)

    # Register credentials for every batch customer.
    auth_provider = container.resolve_auth_provider(bank_id)
    for customer in customers:
        try:
            auth_provider.register(
                bank_id, customer.email, "foobar!", customer.id
            )
        except Exception:
            pass  # skip duplicates (email collisions in very small batches)

    return BatchCreateCustomersResponse(
        customers_created=len(customers),
        accounts_created=len(accounts),
        persona_breakdown=dict(persona_tally),
        account_type_breakdown=dict(acct_type_tally),
    )


# ---------------------------------------------------------------------------
# Bank population stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=BankStatsResponse, summary="Bank population statistics")
def bank_stats(bank_id: BankIdDep, container: ContainerDep) -> BankStatsResponse:
    """Return aggregate counts and breakdowns for customers, accounts and transactions."""
    customers = container.banking.list_customers(bank_id)
    accounts = [
        a for a in container.banking.list_accounts(bank_id) if not a.is_internal
    ]
    persona_tally: Counter = Counter(c.persona or "(none)" for c in customers)
    acct_tally: Counter = Counter(a.type.value for a in accounts)
    tx_count = container.banking_repository.count_journal_entries(bank_id)
    manual = sum(1 for c in customers if getattr(c, "source", "manual") == "manual")
    return BankStatsResponse(
        customers=len(customers),
        accounts=len(accounts),
        manual_customers=manual,
        batch_customers=len(customers) - manual,
        persona_breakdown=dict(persona_tally),
        account_type_breakdown=dict(acct_tally),
        transaction_count=tx_count,
    )
