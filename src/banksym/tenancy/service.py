"""Bank lifecycle / instantiation service."""

from __future__ import annotations

from banksym.core.kernel.errors import BankSymError
from banksym.tenancy.bank import Bank, BankBranding, CapabilitySelection
from banksym.tenancy.repository import BankRepository


class BankNotFoundError(BankSymError):
    code = "bank_not_found"


class DuplicateBankNameError(BankSymError):
    code = "duplicate_bank_name"


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
        bank = Bank(
            branding=BankBranding(
                display_name=name,
                logo_url=logo_url,
                primary_color=primary_color,
            ),
            country=country,
            locale=locale,
            base_currency=base_currency,
            enabled_protocols=list(enabled_protocols or []),
            capabilities=CapabilitySelection(selected=dict(capabilities or {})),
        )
        self._repo.add(bank)
        return bank

    def update_bank(
        self,
        bank_id: str,
        *,
        display_name: str | None = None,
        country: str | None = None,
        locale: str | None = None,
        base_currency: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        enabled_protocols: list[str] | None = None,
        capabilities: dict[str, str] | None = None,
    ) -> Bank:
        """Update an existing bank tenant's branding, locale and capability configuration.

        Only the supplied fields are changed; ``None`` leaves a field untouched. Raises
        :class:`BankNotFoundError` if the bank does not exist and :class:`DuplicateBankNameError`
        if the new display name is empty or collides with another bank.
        """
        bank = self.get_bank(bank_id)
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise DuplicateBankNameError("Display name must not be empty")
            if any(
                b.id != bank_id and b.branding.display_name.casefold() == name.casefold()
                for b in self._repo.list()
            ):
                raise DuplicateBankNameError(f"A bank named {name!r} already exists")
            bank.branding.display_name = name
        if logo_url is not None:
            bank.branding.logo_url = logo_url
        if primary_color is not None:
            bank.branding.primary_color = primary_color
        if country is not None:
            bank.country = country
        if locale is not None:
            bank.locale = locale
        if base_currency is not None:
            bank.base_currency = base_currency
        if enabled_protocols is not None:
            bank.enabled_protocols = list(enabled_protocols)
        if capabilities is not None:
            bank.capabilities = CapabilitySelection(selected=dict(capabilities))
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
