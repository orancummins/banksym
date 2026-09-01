"""FDX (Financial Data Exchange) API adapter.

FDX is the US open banking standard. It sits alongside Berlin Group XS2A (the EU
PSD2 standard) as a third API surface over the same core bank.

The mapping work here is real rather than cosmetic. FDX models accounts and
transactions polymorphically -- a client dispatches on ``depositAccount`` vs
``locAccount`` -- so a credit card is a line-of-credit account with a LIABILITY
balance, not a deposit account with a negative one. Direction is carried by
``debitCreditMemo`` with a positive amount, so the core's signed postings have to
be decomposed into (direction, magnitude) rather than passed through.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Path, Query

from banksym.capabilities.protocols.base.adapter import APIAdapter, api_registry
from banksym.capabilities.protocols.fdx import schemas as s
from banksym.core.domain.account import Account, AccountType
from banksym.core.domain.transaction import TransactionRecord
from banksym.tenancy.service import BankNotFoundError

#: Core account types -> FDX accountType, and which typed wrapper carries them.
_DEPOSIT_TYPES = {
    AccountType.CURRENT: "CHECKING",
    AccountType.SAVINGS: "SAVINGS",
}

#: FDX transactionType, inferred from what the posting looks like. FDX expects a
#: coarse classification; anything we cannot place stays OTHER rather than being
#: guessed into a specific type.
def _transaction_type(record: TransactionRecord, is_card: bool) -> str:
    text = (record.description or "").upper()
    if "ATM" in text:
        return "ATMWITHDRAWAL"
    if "PAYROLL" in text or record.amount.is_positive and not is_card:
        return "DEPOSIT" if not is_card else "PAYMENT"
    if "AUTOPAY" in text or "PAYMENT" in text:
        return "PAYMENT"
    if is_card:
        return "PURCHASE"
    return "WITHDRAWAL" if record.amount.is_negative else "DEPOSIT"


def _display(account: Account) -> str:
    seeded = (account.metadata or {}).get("mask")
    if seeded:
        return f"xxxx{seeded}"
    digits = "".join(c for c in account.id if c.isdigit())
    return f"xxxx{(digits or account.id)[-4:].rjust(4, '0')}"


@api_registry.register
class FdxAdapter(APIAdapter):
    capability_name = "fdx"
    protocol_title = "FDX (Financial Data Exchange) v6"

    def build_router(self) -> APIRouter:
        router = APIRouter(prefix="/fdx/{bank_id}/v6", tags=["fdx"])
        banking = self.banking
        banks = self.banks

        def require_bank(bank_id: str):
            try:
                return banks.get_bank(bank_id)
            except BankNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Institution not found") from exc

        def require_token(authorization: str | None) -> None:
            """FDX is OAuth2-based; any bearer token is accepted here.

            This is a test bank, so rejecting tokens would obstruct the integrations
            it exists to support -- but the header is required so client code has to
            carry credentials the way it would against a real FDX provider.
            """
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(
                    status_code=401,
                    detail={"code": "401", "message": "Missing OAuth2 bearer token"},
                )

        def customer_accounts(bank_id: str, customer_id: str | None) -> list[Account]:
            accounts = [
                a for a in banking.list_accounts(bank_id)
                if not a.is_internal and a.customer_id is not None
            ]
            if customer_id:
                accounts = [a for a in accounts if a.customer_id == customer_id]
            return accounts

        def to_entry(bank_id: str, account: Account) -> s.FdxAccountEntry:
            balance = banking.balance(bank_id, account.id)
            now = datetime.now(UTC)
            currency = {"currencyCode": account.currency}

            if account.type == AccountType.CREDIT_CARD:
                # A card is a liability: FDX reports the amount owed as a positive
                # number on a LINE_OF_CREDIT_ACCOUNT, while the core holds it as a
                # negative deposit-style balance.
                owed = -balance.to_decimal()
                # Credit limit is underwriting data for this specific cardholder,
                # not a core ledger concept BankSym models natively -- it rides in
                # account metadata the same way the display mask already does.
                # availableCredit is the whole reason a client asks for this
                # account at all: whether a purchase can actually be charged to it.
                limit_raw = (account.metadata or {}).get("credit_limit")
                available_credit = None
                if limit_raw is not None:
                    available_credit = float(limit_raw) - float(owed)
                return s.FdxAccountEntry(
                    locAccount=s.FdxLocAccount(
                        accountId=account.id,
                        accountNumberDisplay=_display(account),
                        productName=account.name,
                        nickname=account.name,
                        currency=currency,
                        balanceAsOf=now,
                        currentBalance=float(owed),
                        availableCredit=available_credit,
                    )
                )
            return s.FdxAccountEntry(
                depositAccount=s.FdxDepositAccount(
                    accountId=account.id,
                    accountType=_DEPOSIT_TYPES.get(account.type, "CHECKING"),
                    accountNumberDisplay=_display(account),
                    productName=account.name,
                    nickname=account.name,
                    currency=currency,
                    balanceAsOf=now,
                    currentBalance=float(balance.to_decimal()),
                    availableBalance=float(balance.to_decimal()),
                )
            )

        def find_account(bank_id: str, account_id: str) -> Account:
            try:
                account = banking.get_account(bank_id, account_id)
            except Exception as exc:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "404", "message": "Account not found"},
                ) from exc
            if account.is_internal:
                raise HTTPException(
                    status_code=404, detail={"code": "404", "message": "Account not found"}
                )
            return account

        @router.get("/accounts", response_model=s.FdxAccountsResponse, summary="Get accounts")
        def get_accounts(
            bank_id: str = Path(...),
            customerId: str | None = Query(default=None),
            authorization: str | None = Header(default=None),
        ) -> s.FdxAccountsResponse:
            require_token(authorization)
            require_bank(bank_id)
            entries = [to_entry(bank_id, a) for a in customer_accounts(bank_id, customerId)]
            return s.FdxAccountsResponse(
                accounts=entries, page=s.FdxPage(totalElements=len(entries))
            )

        @router.get(
            "/accounts/{account_id}",
            response_model=s.FdxAccountEntry,
            summary="Get account details",
        )
        def get_account(
            account_id: str,
            bank_id: str = Path(...),
            authorization: str | None = Header(default=None),
        ) -> s.FdxAccountEntry:
            require_token(authorization)
            require_bank(bank_id)
            return to_entry(bank_id, find_account(bank_id, account_id))

        @router.get(
            "/accounts/{account_id}/transactions",
            response_model=s.FdxTransactionsResponse,
            summary="Get account transactions",
        )
        def get_transactions(
            account_id: str,
            bank_id: str = Path(...),
            startTime: datetime | None = Query(default=None),
            endTime: datetime | None = Query(default=None),
            authorization: str | None = Header(default=None),
        ) -> s.FdxTransactionsResponse:
            require_token(authorization)
            require_bank(bank_id)
            account = find_account(bank_id, account_id)
            is_card = account.type == AccountType.CREDIT_CARD

            entries: list[s.FdxTransactionEntry] = []
            for record in banking.transaction_history(bank_id, account_id):
                posted = record.booked_at
                if posted.tzinfo is None:
                    posted = posted.replace(tzinfo=UTC)
                if startTime and posted < startTime:
                    continue
                if endTime and posted > endTime:
                    continue

                signed = record.amount.to_decimal()
                transaction = s.FdxTransaction(
                    accountId=account_id,
                    transactionId=record.journal_id,
                    postedTimestamp=posted,
                    transactionTimestamp=posted,
                    description=record.description,
                    memo=record.category,
                    # FDX carries direction separately from magnitude: the amount is
                    # always positive and debitCreditMemo says which way it went.
                    debitCreditMemo="CREDIT" if signed > 0 else "DEBIT",
                    amount=float(abs(signed)),
                    transactionType=_transaction_type(record, is_card),
                    category=record.category,
                    payee=record.merchant_name,
                    reference=record.reference,
                )
                entries.append(
                    s.FdxTransactionEntry(locTransaction=transaction)
                    if is_card
                    else s.FdxTransactionEntry(depositTransaction=transaction)
                )

            return s.FdxTransactionsResponse(
                transactions=entries, page=s.FdxPage(totalElements=len(entries))
            )

        @router.get(
            "/customers/current", response_model=s.FdxCustomer, summary="Get current customer"
        )
        def get_current_customer(
            bank_id: str = Path(...),
            customerId: str | None = Query(default=None),
            authorization: str | None = Header(default=None),
        ) -> s.FdxCustomer:
            require_token(authorization)
            require_bank(bank_id)
            customers = banking.list_customers(bank_id)
            if customerId:
                customers = [c for c in customers if c.id == customerId]
            if not customers:
                raise HTTPException(
                    status_code=404, detail={"code": "404", "message": "Customer not found"}
                )
            customer = customers[0]
            first, _, last = (customer.full_name or "").partition(" ")
            return s.FdxCustomer(
                customerId=customer.id,
                name=s.FdxCustomerName(first=first or None, last=last or None),
                email=[customer.email] if customer.email else [],
            )

        return router
