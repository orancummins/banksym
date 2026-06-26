"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from banksym.core.domain.account import AccountStatus, AccountType


# -- Banks -------------------------------------------------------------------------
class CreateBankRequest(BaseModel):
    display_name: str
    country: str
    locale: str = "en"
    base_currency: str = "EUR"
    secondary_color: str = "#f79e1b"
    supported_currencies: list[str] = Field(default_factory=list)
    supported_languages: list[str] = Field(default_factory=list)
    supported_customer_types: list[str] = Field(default_factory=list)
    open_banking_enabled: bool | None = None
    card_products: list[dict] = Field(default_factory=list)
    current_account_products: list[dict] = Field(default_factory=list)
    savings_account_products: list[dict] = Field(default_factory=list)
    loan_products: list[dict] = Field(default_factory=list)
    logo_url: str | None = None
    primary_color: str = "#0B5FFF"
    enabled_protocols: list[str] = Field(default_factory=list)
    capabilities: dict[str, str] = Field(default_factory=dict)


class BankResponse(BaseModel):
    id: str
    display_name: str
    country: str
    locale: str
    base_currency: str
    secondary_color: str
    supported_currencies: list[str]
    supported_languages: list[str]
    supported_customer_types: list[str]
    open_banking_enabled: bool
    card_products: list[dict]
    current_account_products: list[dict]
    savings_account_products: list[dict]
    loan_products: list[dict]
    logo_url: str | None
    primary_color: str
    enabled_protocols: list[str]
    capabilities: dict[str, str]


# -- Customers ---------------------------------------------------------------------
class CreateCustomerRequest(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    persona: str | None = None
    # A plausible address is auto-generated for the customer's country; override it here.
    address: str | None = None
    # Online-banking credentials are created automatically; override the defaults here.
    username: str | None = None
    password: str | None = None


class CustomerResponse(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None = None
    persona: str | None
    # The customer's (synthetic) postal address.
    address: str | None = None
    # The online-banking username the customer uses to log in to Open Banking.
    username: str
    # How this customer was created: "manual" (single POST) or "batch" (bulk seed).
    source: str = "manual"


# -- Batch customer creation -------------------------------------------------------
class BatchCreateCustomersRequest(BaseModel):
    count: int = Field(..., ge=1, le=10_000, description="Number of customers to create (1–10 000).")
    persona_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Persona ID → relative weight. Empty means equal weight across all personas.",
    )
    account_types: dict[str, float] = Field(
        default_factory=dict,
        description="Account type → relative weight. Empty means one current account per customer.",
    )
    accounts_per_customer: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Optional override. When omitted, account counts are derived from the selected customer/account weighting criteria.",
    )


class BatchCreateCustomersResponse(BaseModel):
    customers_created: int
    accounts_created: int
    persona_breakdown: dict[str, int]
    account_type_breakdown: dict[str, int]


# -- Bank stats --------------------------------------------------------------------
class BankStatsResponse(BaseModel):
    customers: int
    accounts: int
    manual_customers: int
    batch_customers: int
    persona_breakdown: dict[str, int]
    account_type_breakdown: dict[str, int]
    transaction_count: int


# -- Accounts ----------------------------------------------------------------------
class OpenAccountRequest(BaseModel):
    currency: str = "EUR"
    customer_id: str | None = None
    type: AccountType = AccountType.CURRENT
    iban: str | None = None
    name: str | None = None
    metadata: dict = Field(default_factory=dict)


class AccountResponse(BaseModel):
    id: str
    currency: str
    type: AccountType
    status: AccountStatus
    customer_id: str | None
    iban: str | None
    name: str | None
    balance: str
    metadata: dict = Field(default_factory=dict)


# -- Transactions ------------------------------------------------------------------
class TransactionResponse(BaseModel):
    journal_id: str
    amount: str
    balance_after: str
    side: str
    booked_at: datetime
    description: str
    reference: str | None
    merchant_name: str | None = None
    category: str | None = None
    payment_reference: str | None = None
    location: str | None = None
    channel: str | None = None


class PostTransactionRequest(BaseModel):
    """A single immediate transaction posted against one account.

    ``side`` ``"credit"`` moves money into the account (from the bank's internal "External world"
    account); ``"debit"`` moves money out. ``currency`` defaults to the account's own currency and
    must match it.
    """

    amount: Decimal = Field(gt=0)
    currency: str | None = None
    side: Literal["debit", "credit"] = "credit"
    description: str | None = None
    reference: str | None = None


# -- Generation ---------------------------------------------------------------------
class GenerateHistoryRequest(BaseModel):
    generator: str = "rule_based"
    start: date
    end: date
    seed: int | None = None


class GenerateHistoryResponse(BaseModel):
    entries_booked: int
    balance: str


# -- Auth --------------------------------------------------------------------------
class RegisterCredentialRequest(BaseModel):
    username: str
    password: str
    customer_id: str


class CredentialResponse(BaseModel):
    id: str
    username: str
    customer_id: str


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionResponse(BaseModel):
    token: str
    customer_id: str
    username: str


# -- OAuth (redirect SCA) ----------------------------------------------------------
class OAuthAuthorizeRequest(BaseModel):
    """Credentials + consent submitted on the bank-hosted authorisation page."""

    consent_id: str
    username: str
    password: str
    redirect_uri: str
    state: str | None = None
    # Accounts the PSU ticked on the authorisation page. ``None`` permits every eligible account;
    # an explicit list limits the consent to exactly those account ids.
    account_ids: list[str] | None = None


class OAuthAccountsRequest(BaseModel):
    """Credentials submitted to preview the PSU's accounts before they pick which to share."""

    consent_id: str
    username: str
    password: str


class OAuthAccountItem(BaseModel):
    """A single selectable account shown on the bank's authorisation page."""

    id: str
    iban: str
    name: str | None = None
    type: AccountType
    currency: str
    balance: str


class OAuthAccountsResponse(BaseModel):
    accounts: list[OAuthAccountItem]


class OAuthAuthorizeResponse(BaseModel):
    """Where the bank tells the browser to return once the PSU has authenticated."""

    redirect_to: str


class OAuthTokenRequest(BaseModel):
    grant_type: str = "authorization_code"
    code: str
    redirect_uri: str


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    consent_id: str
    expires_in: int = 3600


# -- Settlement --------------------------------------------------------------------
class SettlementCycleResult(BaseModel):
    instruction_id: str
    status: str
    journal_id: str | None = None
    detail: str = ""


class SettlementCycleResponse(BaseModel):
    settled: list[SettlementCycleResult]


# -- Live simulation ---------------------------------------------------------------
class SimulationTarget(BaseModel):
    """One account that should receive simulated transactions."""

    bank_id: str
    account_id: str


class SimulationStartRequest(BaseModel):
    """Start (or reconfigure) the server-side live transaction simulator."""

    avg_seconds: float = Field(gt=0, le=3600)
    targets: list[SimulationTarget] = Field(default_factory=list)


class SimulationStatusResponse(BaseModel):
    running: bool
    avg_seconds: float
    target_count: int
    generated: int
    last_seq: int


class SimulationEventResponse(BaseModel):
    seq: int
    kind: str
    bank_id: str
    bank_name: str
    bank_color: str
    country: str
    account_id: str
    iban: str | None = None
    customer_name: str
    amount: str
    side: str
    balance_after: str
    description: str
    booked_at: datetime


class SimulationFeedResponse(BaseModel):
    running: bool
    generated: int
    last_seq: int
    events: list[SimulationEventResponse]


class SimulationParticipantResponse(BaseModel):
    bank_id: str
    bank_name: str
    bank_color: str
    country: str
    customer_id: str | None = None
    customer_name: str = ""
    account_id: str
    account_name: str
    iban: str | None = None
    currency: str
    type: str


class SimulationParticipantsResponse(BaseModel):
    participants: list[SimulationParticipantResponse]

