"""Bank instantiation/admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from banksym.api.deps import ContainerDep
from banksym.api.schemas import BankResponse, CreateBankRequest
from banksym.capabilities.auth.base import auth_registry, sca_registry
from banksym.capabilities.localization.base import localization_registry
from banksym.capabilities.protocols.base import protocol_registry
from banksym.capabilities.settlement.base import settlement_registry
from banksym.capabilities.txgen.base import txgen_registry
from banksym.capabilities.txgen.personas import PERSONAS
from banksym.tenancy.bank import Bank
from banksym.tenancy.service import (
    BankNotFoundError,
    DEFAULT_CARD_PRODUCTS,
    DEFAULT_CURRENT_ACCOUNT_PRODUCTS,
    DEFAULT_CUSTOMER_TYPES,
    DEFAULT_LOAN_PRODUCTS,
    DEFAULT_SAVINGS_ACCOUNT_PRODUCTS,
)

router = APIRouter(prefix="/banks", tags=["banks"])


def _to_response(bank: Bank) -> BankResponse:
    return BankResponse(
        id=bank.id,
        display_name=bank.branding.display_name,
        country=bank.country,
        locale=bank.locale,
        base_currency=bank.base_currency,
        secondary_color=bank.branding.secondary_color,
        supported_currencies=bank.supported_currencies,
        supported_languages=bank.supported_languages,
        supported_customer_types=bank.supported_customer_types,
        open_banking_enabled=bank.open_banking_enabled,
        card_products=bank.card_products,
        current_account_products=bank.current_account_products,
        savings_account_products=bank.savings_account_products,
        loan_products=bank.loan_products,
        logo_url=bank.branding.logo_url,
        primary_color=bank.branding.primary_color,
        enabled_protocols=bank.enabled_protocols,
        capabilities=bank.capabilities.selected,
    )


@router.post("", response_model=BankResponse, status_code=201, summary="Create a bank tenant")
def create_bank(body: CreateBankRequest, container: ContainerDep) -> BankResponse:
    """Instantiate a new bank tenant.

    The bank is created with the supplied branding (display name, colour, logo), locale settings
    and the chosen capability implementations (protocol, transaction generator, settlement engine,
    authentication provider). The returned object includes the generated tenant ``id`` used to
    scope all subsequent per-bank calls.
    """
    bank = container.bank_service.create_bank(
        display_name=body.display_name,
        country=body.country,
        locale=body.locale,
        base_currency=body.base_currency,
        secondary_color=body.secondary_color,
        supported_currencies=body.supported_currencies,
        supported_languages=body.supported_languages,
        supported_customer_types=body.supported_customer_types,
        open_banking_enabled=body.open_banking_enabled,
        card_products=body.card_products,
        current_account_products=body.current_account_products,
        savings_account_products=body.savings_account_products,
        loan_products=body.loan_products,
        logo_url=body.logo_url,
        primary_color=body.primary_color,
        enabled_protocols=body.enabled_protocols,
        capabilities=body.capabilities,
    )
    return _to_response(bank)


@router.get("", response_model=list[BankResponse], summary="List all bank tenants")
def list_banks(container: ContainerDep) -> list[BankResponse]:
    """Return every bank tenant that exists, with its branding and selected capabilities."""
    return [_to_response(b) for b in container.bank_service.list_banks()]


@router.get("/{bank_id}", response_model=BankResponse, summary="Get a single bank tenant")
def get_bank(bank_id: str, container: ContainerDep) -> BankResponse:
    """Return the branding and capability configuration for one bank. Responds 404 if unknown."""
    try:
        return _to_response(container.bank_service.get_bank(bank_id))
    except BankNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{bank_id}", status_code=204, summary="Delete a bank tenant")
def delete_bank(bank_id: str, container: ContainerDep) -> None:
    """Delete a bank tenant and permanently purge all of its data.

    Removes the bank along with its customers, accounts, transactions and credentials. Responds
    404 if the bank does not exist.
    """
    try:
        container.delete_bank(bank_id)
    except BankNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/_meta/capabilities", tags=["capabilities"], summary="List available capabilities")
def list_capabilities() -> dict[str, list[str]]:
    """List available capability implementations the UI can offer when building a bank.

    Returns the registered names grouped by extension point: ``txgen``, ``api``,
    ``settlement``, ``localization``, ``auth`` and ``sca``.
    """
    api_names = protocol_registry.names()
    return {
        "txgen": txgen_registry.names(),
        "api": api_names,
        "protocol": api_names,
        "settlement": settlement_registry.names(),
        "localization": localization_registry.names(),
        "auth": auth_registry.names(),
        "sca": sca_registry.names(),
    }


@router.get("/_meta/personas", tags=["capabilities"], summary="List customer personas")
def list_personas() -> list[dict[str, str]]:
    """List persona archetypes the UI can assign to generated customers.

    Personas shape the realistic transaction history produced for a customer's accounts.
    """
    return [
        {"id": p.id, "label": p.label, "description": p.description}
        for p in PERSONAS.values()
    ]


@router.get("/_meta/customer-types", tags=["capabilities"], summary="List supported customer types")
def list_customer_types() -> list[dict[str, str]]:
    persona_map = {p.id: p for p in PERSONAS.values()}
    out: list[dict[str, str]] = []
    for customer_type in DEFAULT_CUSTOMER_TYPES:
        p = persona_map.get(customer_type)
        if p:
            out.append({"id": p.id, "label": p.label, "description": p.description})
        else:
            out.append(
                {
                    "id": customer_type,
                    "label": customer_type.replace("_", " ").title(),
                    "description": "Customer-type profile supported by bank configuration.",
                }
            )
    return out


@router.get("/_meta/card-products", tags=["capabilities"], summary="List preconfigured card products")
def list_card_products() -> list[dict]:
    return DEFAULT_CARD_PRODUCTS


@router.get("/_meta/current-account-products", tags=["capabilities"], summary="List preconfigured current account products")
def list_current_account_products() -> list[dict]:
    return DEFAULT_CURRENT_ACCOUNT_PRODUCTS


@router.get("/_meta/savings-account-products", tags=["capabilities"], summary="List preconfigured savings account products")
def list_savings_account_products() -> list[dict]:
    return DEFAULT_SAVINGS_ACCOUNT_PRODUCTS


@router.get("/_meta/loan-products", tags=["capabilities"], summary="List illustrative loan products")
def list_loan_products() -> list[dict]:
    return DEFAULT_LOAN_PRODUCTS
