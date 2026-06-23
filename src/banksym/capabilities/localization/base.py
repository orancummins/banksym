"""LocalizationProvider interface + registry."""

from __future__ import annotations

import abc
from dataclasses import dataclass

from banksym.core.kernel.registry import Capability, CapabilityRegistry

CAPABILITY_KIND = "localization"


@dataclass(frozen=True, slots=True)
class LocalePack:
    """Country-specific localization data used to flavour generated data."""

    country: str
    language: str
    currency: str
    income_label: str
    merchant_categories: list[str]
    iban_prefix: str = ""

    def merchant_for(self, index: int) -> str:
        return self.merchant_categories[index % len(self.merchant_categories)]


class LocalizationProvider(Capability, abc.ABC):
    """Resolves a :class:`LocalePack` for a country code."""

    capability_kind = CAPABILITY_KIND

    @abc.abstractmethod
    def get_pack(self, country: str) -> LocalePack:
        raise NotImplementedError

    @abc.abstractmethod
    def get_pack_for_language(self, language: str) -> LocalePack | None:
        """Return the pack whose language matches ``language`` (or ``None`` if none does)."""
        raise NotImplementedError

    @abc.abstractmethod
    def countries(self) -> list[str]:
        raise NotImplementedError


localization_registry: CapabilityRegistry[LocalizationProvider] = CapabilityRegistry(
    CAPABILITY_KIND
)


# Convenience default holder, populated when an implementation module is imported.
_default: list[LocalizationProvider] = []


def default_provider() -> LocalizationProvider:
    """Return a singleton instance of the first registered localization provider."""
    if not _default:
        if not localization_registry.names():
            # Ensure the bundled default packs are registered.
            import banksym.capabilities.localization.packs  # noqa: F401
        name = localization_registry.names()[0]
        _default.append(localization_registry.get(name)())
    return _default[0]


def resolve_pack(language: str | None, country: str | None) -> LocalePack:
    """Resolve the locale pack for a bank, preferring its chosen ``language`` over ``country``.

    A bank can be based in one country but operate in another language (e.g. a German bank serving
    Spanish-speaking customers); when that happens the customer-facing text — merchant names,
    income labels — should follow the language, falling back to the country pack when the language
    has no dedicated pack.

    When the bank's own country pack already speaks the requested language (e.g. an Irish bank in
    English), that country pack is preferred over the generic language pack so country-specific
    flavour (merchants, currency) is retained.
    """
    provider = default_provider()
    if country:
        country_pack = provider.get_pack(country)
        if language and country_pack.language == language.lower():
            return country_pack
    if language:
        pack = provider.get_pack_for_language(language)
        if pack is not None:
            return pack
    return provider.get_pack(country or "")
