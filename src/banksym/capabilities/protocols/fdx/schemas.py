"""FDX (Financial Data Exchange) response shapes.

FDX is the US open banking standard, and its modelling differs from both Berlin
Group and a generic aggregation API in ways an integration has to handle:

* Accounts and transactions are *polymorphic*. The response wraps a single typed
  object -- ``depositAccount``, ``locAccount``, ``loanAccount`` -- rather than
  carrying a flat record with a type field, so a client dispatches on the key.
* Direction is carried by ``debitCreditMemo`` (DEBIT / CREDIT) with a positive
  ``amount``, not by the sign of the amount.
* Timestamps are ISO-8601 instants (``postedTimestamp``), not dates.
* A credit card is a line-of-credit account, not a deposit account.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FdxBalance(BaseModel):
    balanceType: str = Field(default="ASSET", description="ASSET or LIABILITY")


class FdxDepositAccount(BaseModel):
    """FDX DEPOSIT_ACCOUNT — checking and savings."""

    accountId: str
    accountCategory: str = "DEPOSIT_ACCOUNT"
    accountType: str = Field(description="CHECKING | SAVINGS | MONEYMARKET | CD")
    accountNumberDisplay: str
    productName: str | None = None
    nickname: str | None = None
    status: str = "OPEN"
    currency: dict = Field(default_factory=lambda: {"currencyCode": "USD"})
    balanceType: str = "ASSET"
    balanceAsOf: datetime | None = None
    currentBalance: float | None = None
    availableBalance: float | None = None
    fiAttributes: list[dict] = Field(default_factory=list)


class FdxLocAccount(BaseModel):
    """FDX LINE_OF_CREDIT_ACCOUNT — where a credit card lives.

    A card is a liability, so ``balanceType`` is LIABILITY and ``currentBalance``
    is the amount owed, expressed positive.
    """

    accountId: str
    accountCategory: str = "LINE_OF_CREDIT_ACCOUNT"
    accountType: str = "CREDITCARD"
    accountNumberDisplay: str
    productName: str | None = None
    nickname: str | None = None
    status: str = "OPEN"
    currency: dict = Field(default_factory=lambda: {"currencyCode": "USD"})
    balanceType: str = "LIABILITY"
    balanceAsOf: datetime | None = None
    currentBalance: float | None = None
    availableCredit: float | None = None
    fiAttributes: list[dict] = Field(default_factory=list)


class FdxAccountEntry(BaseModel):
    """One entry in an accounts list: exactly one typed account is populated."""

    depositAccount: FdxDepositAccount | None = None
    locAccount: FdxLocAccount | None = None


class FdxPage(BaseModel):
    nextOffset: str | None = None
    totalElements: int | None = None


class FdxAccountsResponse(BaseModel):
    accounts: list[FdxAccountEntry]
    page: FdxPage = FdxPage()


class FdxTransaction(BaseModel):
    accountId: str
    transactionId: str
    postedTimestamp: datetime
    transactionTimestamp: datetime | None = None
    description: str
    memo: str | None = None
    #: DEBIT is money out of the account, CREDIT is money in. The amount itself is
    #: always positive -- direction lives here, not in the sign.
    debitCreditMemo: str
    amount: float
    status: str = "POSTED"
    transactionType: str | None = None
    category: str | None = None
    payee: str | None = None
    reference: str | None = None


class FdxTransactionEntry(BaseModel):
    depositTransaction: FdxTransaction | None = None
    locTransaction: FdxTransaction | None = None


class FdxTransactionsResponse(BaseModel):
    transactions: list[FdxTransactionEntry]
    page: FdxPage = FdxPage()


class FdxCustomerName(BaseModel):
    first: str | None = None
    last: str | None = None


class FdxCustomer(BaseModel):
    customerId: str
    name: FdxCustomerName
    email: list[str] = Field(default_factory=list)


class FdxError(BaseModel):
    code: str
    message: str
