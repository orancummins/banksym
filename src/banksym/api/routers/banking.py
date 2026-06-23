"""Per-bank core banking endpoints: customers, accounts, transactions, history generation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from banksym.api.deps import BankIdDep, ContainerDep, to_http_error
from banksym.api.schemas import (
    AccountResponse,
    CreateCustomerRequest,
    CustomerResponse,
    GenerateHistoryRequest,
    GenerateHistoryResponse,
    OpenAccountRequest,
    PostTransactionRequest,
    TransactionResponse,
)
from banksym.capabilities.localization.address import random_address, random_phone
from banksym.capabilities.txgen.base import GenerationRequest
from banksym.core.domain.account import Account
from banksym.core.kernel.errors import BankSymError

router = APIRouter(prefix="/banks/{bank_id}", tags=["banking"])


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
    responses: list[CustomerResponse] = []
    for c in customers:
        credential = container.credential_store.find_by_customer(bank_id, c.id)
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
    try:
        account = container.banking.open_account(
            bank_id,
            body.currency,
            customer_id=body.customer_id,
            type=body.type,
            iban=body.iban,
            name=body.name,
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
