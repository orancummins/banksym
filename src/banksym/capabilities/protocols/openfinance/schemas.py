"""Open Finance response shapes.

Modelled on US-style open finance / account aggregation APIs (the Mastercard Open
Finance family), which differ from Berlin Group XS2A in ways that matter to a
consumer-finance integration:

* accounts are addressed by opaque id and account/routing masks, not IBAN;
* credit cards are first-class alongside deposit accounts, each with their own
  balance semantics;
* transactions carry enrichment -- merchant, category, channel -- because the
  consumer-facing use case is understanding spend, not just listing postings.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class OFBalance(BaseModel):
    type: str = Field(description="'available' or 'current'")
    amount: str
    currency: str


class OFAccount(BaseModel):
    accountId: str
    accountNumberMask: str
    accountType: str = Field(description="checking | savings | creditCard | loan")
    name: str
    currency: str
    institutionId: str
    institutionName: str
    customerId: str | None = None
    balances: list[OFBalance] = []


class OFAccountsResponse(BaseModel):
    accounts: list[OFAccount]


class OFTransaction(BaseModel):
    transactionId: str
    accountId: str
    postedDate: date
    amount: str = Field(
        description="Signed. Negative is money out of the account, positive is money in."
    )
    currency: str
    description: str
    merchantName: str | None = None
    category: str | None = None
    channel: str | None = None
    location: str | None = None
    runningBalance: str | None = None
    reference: str | None = None


class OFTransactionsResponse(BaseModel):
    accountId: str
    fromDate: date | None = None
    toDate: date | None = None
    transactions: list[OFTransaction]


class OFCustomer(BaseModel):
    customerId: str
    name: str
    institutionId: str
    institutionName: str


class OFCustomersResponse(BaseModel):
    customers: list[OFCustomer]


class OFInstitution(BaseModel):
    institutionId: str
    name: str
    country: str
    currency: str


class OFError(BaseModel):
    code: str
    message: str
    timestamp: datetime
