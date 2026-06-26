"""Bank lifecycle / instantiation service."""

from __future__ import annotations

from banksym.core.kernel.errors import BankSymError
from banksym.capabilities.txgen.personas import PERSONAS
from banksym.tenancy.bank import Bank, BankBranding, CapabilitySelection
from banksym.tenancy.repository import BankRepository


class BankNotFoundError(BankSymError):
    code = "bank_not_found"


class DuplicateBankNameError(BankSymError):
    code = "duplicate_bank_name"


DEFAULT_CUSTOMER_TYPES: list[str] = [
    "student",
    "gig_worker",
    "young_professional",
    "affluent_family",
    "retiree",
]

DEFAULT_CARD_PRODUCTS: list[dict] = [
    {
        "id": "classic_mastercard",
        "name": "Classic Mastercard",
        "card_type": "credit",
        "scheme": "mastercard",
        "digital_properties": ["apple_pay", "google_pay", "contactless", "instant_notifications"],
        "properties": {"credit_limit": 2000, "apr": 19.9, "annual_fee": 0, "cashback": 0.0, "interest_free_days": 45},
    },
    {
        "id": "gold_mastercard",
        "name": "Gold Mastercard",
        "card_type": "credit",
        "scheme": "mastercard",
        "digital_properties": ["apple_pay", "google_pay", "contactless", "virtual_cards", "card_freezing", "instant_notifications"],
        "properties": {"credit_limit": 5000, "apr": 17.9, "annual_fee": 79, "cashback": 0.5, "interest_free_days": 50, "travel_insurance": True},
    },
    {
        "id": "platinum_mastercard",
        "name": "Platinum Mastercard",
        "card_type": "credit",
        "scheme": "mastercard",
        "digital_properties": ["apple_pay", "google_pay", "contactless", "virtual_cards", "card_freezing", "instant_notifications"],
        "properties": {"credit_limit": 12000, "apr": 14.9, "annual_fee": 180, "cashback": 1.0, "interest_free_days": 56, "travel_insurance": True},
    },
    {
        "id": "classic_visa",
        "name": "Classic Visa",
        "card_type": "credit",
        "scheme": "visa",
        "digital_properties": ["apple_pay", "google_pay", "contactless", "instant_notifications"],
        "properties": {"credit_limit": 2000, "apr": 19.9, "annual_fee": 0, "cashback": 0.0, "interest_free_days": 45},
    },
    {
        "id": "gold_visa",
        "name": "Gold Visa",
        "card_type": "credit",
        "scheme": "visa",
        "digital_properties": ["apple_pay", "google_pay", "contactless", "virtual_cards", "card_freezing", "instant_notifications"],
        "properties": {"credit_limit": 5000, "apr": 17.9, "annual_fee": 79, "cashback": 0.5, "interest_free_days": 50, "travel_insurance": True},
    },
    {
        "id": "platinum_visa",
        "name": "Platinum Visa",
        "card_type": "credit",
        "scheme": "visa",
        "digital_properties": ["apple_pay", "google_pay", "contactless", "virtual_cards", "card_freezing", "instant_notifications"],
        "properties": {"credit_limit": 12000, "apr": 14.9, "annual_fee": 180, "cashback": 1.0, "interest_free_days": 56, "travel_insurance": True},
    },
]

DEFAULT_CURRENT_ACCOUNT_PRODUCTS: list[dict] = [
    {"id": "everyday", "name": "Everyday Account", "properties": {"monthly_fee": 0, "overdraft_allowed": True, "overdraft_limit": -250, "interest_rate": 0.0}},
    {"id": "student", "name": "Student Account", "properties": {"monthly_fee": 0, "overdraft_allowed": True, "overdraft_limit": -1000, "interest_rate": 0.0, "minimum_age": 18}},
    {"id": "premium", "name": "Premium Account", "properties": {"monthly_fee": 18, "overdraft_allowed": True, "overdraft_limit": -2500, "interest_rate": 0.25}},
    {"id": "teen", "name": "Teen Account", "properties": {"monthly_fee": 0, "overdraft_allowed": False, "minimum_age": 13}},
    {"id": "basic", "name": "Basic Account", "properties": {"monthly_fee": 2, "overdraft_allowed": False, "interest_rate": 0.0}},
]

DEFAULT_SAVINGS_ACCOUNT_PRODUCTS: list[dict] = [
    {"id": "high_interest_saver", "name": "High Interest Saver", "segment": "personal", "properties": {"interest_rate": 4.5, "minimum_balance": 0}},
    {"id": "childrens_saver", "name": "Children's Saver", "segment": "child", "properties": {"interest_rate": 3.75, "minimum_balance": 0}},
    {"id": "christmas_club", "name": "Christmas Club", "segment": "personal", "properties": {"interest_rate": 3.0, "notice_period_days": 30}},
    {"id": "goal_saver", "name": "Goal Saver", "segment": "personal", "properties": {"interest_rate": 4.1, "minimum_balance": 0}},
]

DEFAULT_LOAN_PRODUCTS: list[dict] = [
    {"id": "personal_loan", "name": "Personal Loan", "dummy": True, "properties": ["interest_rate", "minimum_amount", "maximum_amount", "term", "early_repayment_fee", "eligibility"]},
    {"id": "mortgage", "name": "Mortgage", "dummy": True, "properties": ["loan_to_value_ratio", "fixed_or_variable", "deposit_requirement", "maximum_term", "offset_mortgage", "first_time_buyer_options"]},
    {"id": "car_loan", "name": "Car Loan", "dummy": True, "properties": ["maximum_vehicle_age", "dealer_finance", "balloon_payment", "deposit"]},
    {"id": "business_loan", "name": "Business Loan", "dummy": True, "properties": ["working_capital", "equipment_finance", "commercial_mortgage", "invoice_finance"]},
]


class BankService:
    """Create and resolve simulated banks (tenants)."""

    def __init__(self, repository: BankRepository) -> None:
        self._repo = repository

    def create_bank(
        self,
        *,
        display_name: str,
        country: str,
        locale: str = "en",
        base_currency: str = "EUR",
        secondary_color: str = "#f79e1b",
        supported_currencies: list[str] | None = None,
        supported_languages: list[str] | None = None,
        supported_customer_types: list[str] | None = None,
        open_banking_enabled: bool | None = None,
        card_products: list[dict] | None = None,
        current_account_products: list[dict] | None = None,
        savings_account_products: list[dict] | None = None,
        loan_products: list[dict] | None = None,
        logo_url: str | None = None,
        primary_color: str = "#0B5FFF",
        enabled_protocols: list[str] | None = None,
        capabilities: dict[str, str] | None = None,
    ) -> Bank:
        name = display_name.strip()
        if not name:
            raise DuplicateBankNameError("Display name must not be empty")
        if any(b.branding.display_name.casefold() == name.casefold() for b in self._repo.list()):
            raise DuplicateBankNameError(
                f"A bank named {name!r} already exists"
            )
        base = (base_currency or "EUR").upper()
        currencies = [c.upper() for c in (supported_currencies or []) if c]
        if base not in currencies:
            currencies.insert(0, base)
        # Preserve order but remove duplicates.
        seen: set[str] = set()
        currencies = [c for c in currencies if not (c in seen or seen.add(c))]
        languages = [l.lower() for l in (supported_languages or []) if l]
        if locale.lower() not in languages:
            languages.insert(0, locale.lower())
        lang_seen: set[str] = set()
        languages = [l for l in languages if not (l in lang_seen or lang_seen.add(l))]
        customer_types = [t for t in (supported_customer_types or DEFAULT_CUSTOMER_TYPES) if t]
        ct_seen: set[str] = set()
        customer_types = [t for t in customer_types if not (t in ct_seen or ct_seen.add(t))]
        if not customer_types:
            customer_types = list(PERSONAS.keys())
        protocols = list(enabled_protocols or [])
        requested_open_banking = bool(protocols) if open_banking_enabled is None else bool(open_banking_enabled)
        is_open_banking = bool(protocols) and requested_open_banking

        bank = Bank(
            branding=BankBranding(
                display_name=name,
                logo_url=logo_url,
                primary_color=primary_color,
                secondary_color=secondary_color,
            ),
            country=country,
            locale=locale,
            base_currency=base,
            supported_currencies=currencies,
            supported_languages=languages,
            supported_customer_types=customer_types,
            open_banking_enabled=is_open_banking,
            card_products=list(card_products or DEFAULT_CARD_PRODUCTS),
            current_account_products=list(current_account_products or DEFAULT_CURRENT_ACCOUNT_PRODUCTS),
            savings_account_products=list(savings_account_products or DEFAULT_SAVINGS_ACCOUNT_PRODUCTS),
            loan_products=list(loan_products or DEFAULT_LOAN_PRODUCTS),
            enabled_protocols=protocols,
            capabilities=CapabilitySelection(selected=dict(capabilities or {})),
        )
        self._repo.add(bank)
        return bank

    def get_bank(self, bank_id: str) -> Bank:
        bank = self._repo.get(bank_id)
        if bank is None:
            raise BankNotFoundError(bank_id)
        return bank

    def list_banks(self) -> list[Bank]:
        return self._repo.list()

    def delete_bank(self, bank_id: str) -> None:
        """Remove a bank tenant. Raises if it does not exist."""
        self.get_bank(bank_id)
        self._repo.remove(bank_id)
