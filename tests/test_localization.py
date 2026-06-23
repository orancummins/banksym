"""Tests for the localization capability and persona-flavoured generation."""

from banksym.capabilities.localization.base import default_provider
from banksym.capabilities.localization.packs import DefaultLocalizationProvider


def test_provider_returns_localized_pack():
    provider = DefaultLocalizationProvider()
    de = provider.get_pack("DE")
    assert de.currency == "EUR"
    assert de.income_label == "Gehalt"
    assert any("REWE" in m for m in de.merchant_categories)


def test_unknown_country_falls_back():
    provider = DefaultLocalizationProvider()
    pack = provider.get_pack("ZZ")
    assert pack.merchant_categories  # non-empty fallback
    assert pack.income_label == "Income"


def test_countries_listed():
    provider = DefaultLocalizationProvider()
    assert {"DE", "ES", "FR", "GB", "NL"}.issubset(set(provider.countries()))


def test_default_provider_singleton():
    assert default_provider() is default_provider()


def test_merchant_for_wraps():
    pack = DefaultLocalizationProvider().get_pack("GB")
    n = len(pack.merchant_categories)
    assert pack.merchant_for(0) == pack.merchant_for(n)
