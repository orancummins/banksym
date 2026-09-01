"""Open Finance API adapter.

A US-style open finance / account-aggregation surface, sitting alongside the Berlin
Group XS2A adapter and serving the same core bank. Berlin Group is PSD2-shaped:
IBANs, consent resources, SCA authorisation sub-resources. A consumer-finance
aggregator in the US works differently, and an integration built against one will
not work against the other -- hence a separate adapter rather than a reskin.

Deliberately simple where PSD2 is ceremonious: access is a bearer token scoped to a
customer, not a multi-step consent resource. Everything still goes through
``CoreBankingService``; no state lives here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Header, HTTPException, Path, Query

from banksym.capabilities.protocols.base.adapter import APIAdapter, api_registry
from banksym.capabilities.protocols.openfinance import schemas as s
from banksym.core.domain.account import Account, AccountType
from banksym.tenancy.service import BankNotFoundError

#: Core account types -> the vocabulary an aggregation API exposes.
_ACCOUNT_TYPE = {
    AccountType.CURRENT: "checking",
    AccountType.SAVINGS: "savings",
    AccountType.CREDIT_CARD: "creditCard",
    AccountType.LOAN: "loan",
}


def _mask(account: Account) -> str:
    """A last-four style mask. Prefers an explicitly seeded mask over the opaque id."""
    seeded = (account.metadata or {}).get("mask")
    if seeded:
        return str(seeded)
    digits = "".join(c for c in account.id if c.isdigit())
    return (digits or account.id)[-4:].rjust(4, "0")


@api_registry.register
class OpenFinanceAdapter(APIAdapter):
    capability_name = "open_finance"
    protocol_title = "Open Finance (US account aggregation)"

    def build_router(self) -> APIRouter:
        router = APIRouter(
            prefix="/openfinance/{bank_id}/v1", tags=["open finance"]
        )
        banking = self.banking
        banks = self.banks

        def require_bank(bank_id: str):
            try:
                return banks.get_bank(bank_id)
            except BankNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Institution not found") from exc

        def require_token(authorization: str | None) -> None:
            """Bearer token gate.

            Any bearer token is accepted: this is a test bank, and rejecting tokens
            would only obstruct the integrations it exists to support. The header is
            still required so client code has to carry credentials the way it would
            against a real aggregator.
            """
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing bearer token. Send: Authorization: Bearer <token>",
                )

        def to_account(bank_id: str, bank, account: Account) -> s.OFAccount:
            balance = banking.balance(bank_id, account.id)
            # A credit card's core balance is negative when money is owed; aggregation
            # APIs report the outstanding balance as a positive number, so flip it.
            reported = -balance if account.type == AccountType.CREDIT_CARD else balance
            return s.OFAccount(
                accountId=account.id,
                accountNumberMask=_mask(account),
                accountType=_ACCOUNT_TYPE.get(account.type, "other"),
                name=account.name or account.type.value,
                currency=account.currency,
                institutionId=bank_id,
                institutionName=bank.branding.display_name,
                customerId=account.customer_id,
                balances=[
                    s.OFBalance(
                        type="current",
                        amount=str(reported.to_decimal()),
                        currency=account.currency,
                    )
                ],
            )

        def customer_accounts(bank_id: str, customer_id: str) -> list[Account]:
            return [
                a
                for a in banking.list_accounts(bank_id)
                if not a.is_internal and a.customer_id == customer_id
            ]

        @router.get(
            "/institution",
            response_model=s.OFInstitution,
            summary="Institution metadata",
        )
        def get_institution(bank_id: str = Path(...)) -> s.OFInstitution:
            bank = require_bank(bank_id)
            return s.OFInstitution(
                institutionId=bank_id,
                name=bank.branding.display_name,
                country=bank.country,
                currency=bank.base_currency,
            )

        @router.get(
            "/customers",
            response_model=s.OFCustomersResponse,
            summary="List customers at this institution",
        )
        def list_customers(
            bank_id: str = Path(...),
            authorization: str | None = Header(default=None),
        ) -> s.OFCustomersResponse:
            require_token(authorization)
            bank = require_bank(bank_id)
            return s.OFCustomersResponse(
                customers=[
                    s.OFCustomer(
                        customerId=c.id,
                        name=c.full_name,
                        institutionId=bank_id,
                        institutionName=bank.branding.display_name,
                    )
                    for c in banking.list_customers(bank_id)
                ]
            )

        @router.get(
            "/customers/{customer_id}/accounts",
            response_model=s.OFAccountsResponse,
            summary="List a customer's accounts with balances",
        )
        def get_customer_accounts(
            customer_id: str,
            bank_id: str = Path(...),
            authorization: str | None = Header(default=None),
        ) -> s.OFAccountsResponse:
            require_token(authorization)
            bank = require_bank(bank_id)
            accounts = customer_accounts(bank_id, customer_id)
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts for customer")
            return s.OFAccountsResponse(
                accounts=[to_account(bank_id, bank, a) for a in accounts]
            )

        @router.get(
            "/accounts/{account_id}",
            response_model=s.OFAccount,
            summary="Account detail with balance",
        )
        def get_account(
            account_id: str,
            bank_id: str = Path(...),
            authorization: str | None = Header(default=None),
        ) -> s.OFAccount:
            require_token(authorization)
            bank = require_bank(bank_id)
            try:
                account = banking.get_account(bank_id, account_id)
            except Exception as exc:
                raise HTTPException(status_code=404, detail="Account not found") from exc
            return to_account(bank_id, bank, account)

        @router.get(
            "/accounts/{account_id}/transactions",
            response_model=s.OFTransactionsResponse,
            summary="List account transactions, newest last",
        )
        def get_transactions(
            account_id: str,
            bank_id: str = Path(...),
            fromDate: date | None = Query(default=None),
            toDate: date | None = Query(default=None),
            authorization: str | None = Header(default=None),
        ) -> s.OFTransactionsResponse:
            require_token(authorization)
            require_bank(bank_id)
            try:
                banking.get_account(bank_id, account_id)
            except Exception as exc:
                raise HTTPException(status_code=404, detail="Account not found") from exc

            out: list[s.OFTransaction] = []
            for record in banking.transaction_history(bank_id, account_id):
                booked = record.booked_at.date()
                if fromDate and booked < fromDate:
                    continue
                if toDate and booked > toDate:
                    continue
                out.append(
                    s.OFTransaction(
                        transactionId=record.journal_id,
                        accountId=account_id,
                        postedDate=booked,
                        amount=str(record.amount.to_decimal()),
                        currency=record.amount.currency,
                        description=record.description,
                        merchantName=record.merchant_name,
                        category=record.category,
                        channel=record.channel,
                        location=record.location,
                        runningBalance=str(record.balance_after.to_decimal()),
                        reference=record.reference,
                    )
                )
            return s.OFTransactionsResponse(
                accountId=account_id, fromDate=fromDate, toDate=toDate, transactions=out
            )

        @router.get("/health", summary="Adapter health")
        def health() -> dict:
            return {"status": "ok", "protocol": "open_finance",
                    "timestamp": datetime.now(UTC).isoformat()}

        return router
