"""XS2A wire schemas (subset) following the Berlin Group NextGenPSD2 conventions.

These intentionally cover the AIS consent + account-information flows. Field names use the Berlin
Group camelCase vocabulary so responses look authentic to a TPP integrating against the test bank.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# -- Consents ----------------------------------------------------------------------
class AccountReference(_Camel):
    iban: str | None = None
    currency: str | None = None


class AccessObject(_Camel):
    accounts: list[AccountReference] | None = None
    balances: list[AccountReference] | None = None
    transactions: list[AccountReference] | None = None
    availableAccounts: str | None = None
    allPsd2: str | None = None


class ConsentRequest(_Camel):
    access: AccessObject
    recurringIndicator: bool = True
    validUntil: date | None = None
    frequencyPerDay: int = 4
    combinedServiceIndicator: bool = False


class HrefObject(_Camel):
    href: str


class ConsentResponse(_Camel):
    consentStatus: str
    consentId: str
    links: dict[str, HrefObject] = Field(alias="_links")


class ConsentStatusResponse(_Camel):
    consentStatus: str


class ConsentInformationResponse(_Camel):
    access: AccessObject
    recurringIndicator: bool
    validUntil: date | None
    frequencyPerDay: int
    consentStatus: str


# -- Authorisation (SCA) -----------------------------------------------------------
class StartScaResponse(_Camel):
    scaStatus: str
    authorisationId: str
    links: dict[str, HrefObject] = Field(alias="_links")


class UpdateAuthorisationRequest(_Camel):
    # A test bank auto-approves; PSU data is accepted but not validated.
    psuData: dict | None = None
    scaAuthenticationData: str | None = None


class ScaStatusResponse(_Camel):
    scaStatus: str


# -- Accounts / balances / transactions --------------------------------------------
class AmountObject(_Camel):
    currency: str
    amount: str


class BalanceObject(_Camel):
    balanceType: str
    balanceAmount: AmountObject


class AccountDetails(_Camel):
    resourceId: str
    iban: str | None = None
    currency: str
    name: str | None = None
    cashAccountType: str
    links: dict[str, HrefObject] = Field(default_factory=dict, alias="_links")


class AccountList(_Camel):
    accounts: list[AccountDetails]


class AccountDetailsResponse(_Camel):
    account: AccountDetails


class BalancesResponse(_Camel):
    account: AccountReference
    balances: list[BalanceObject]


class TransactionEntry(_Camel):
    transactionId: str
    bookingDate: date
    valueDate: date
    transactionAmount: AmountObject
    remittanceInformationUnstructured: str | None = None


class TransactionsBody(_Camel):
    booked: list[TransactionEntry]
    pending: list[TransactionEntry] = Field(default_factory=list)


class TransactionsResponse(_Camel):
    account: AccountReference
    transactions: TransactionsBody


# -- Payment initiation (PIS) ------------------------------------------------------
class PaymentInitiation(_Camel):
    instructedAmount: AmountObject
    debtorAccount: AccountReference
    creditorAccount: AccountReference
    creditorName: str | None = None
    remittanceInformationUnstructured: str | None = None
    endToEndIdentification: str | None = None


class PaymentInitiationResponse(_Camel):
    transactionStatus: str
    paymentId: str
    links: dict[str, HrefObject] = Field(alias="_links")


class PaymentStatusResponse(_Camel):
    transactionStatus: str


class PaymentInformationResponse(_Camel):
    transactionStatus: str
    instructedAmount: AmountObject
    debtorAccount: AccountReference
    creditorAccount: AccountReference
    creditorName: str | None = None
    remittanceInformationUnstructured: str | None = None
