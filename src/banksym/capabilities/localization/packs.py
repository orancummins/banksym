"""Default localization provider with a small catalog of European country packs."""

from __future__ import annotations

from banksym.capabilities.localization.base import (
    LocalePack,
    LocalizationProvider,
    localization_registry,
)

_PACKS: dict[str, LocalePack] = {
    "DE": LocalePack(
        country="DE",
        language="de",
        currency="EUR",
        income_label="Gehalt",
        iban_prefix="DE",
        merchant_categories=[
            "Lebensmittel (REWE)",
            "Restaurant",
            "Deutsche Bahn",
            "Stadtwerke",
            "Online-Einkauf",
            "Kino",
            "Apotheke",
            "Abonnement",
        ],
    ),
    "ES": LocalePack(
        country="ES",
        language="es",
        currency="EUR",
        income_label="Nómina",
        iban_prefix="ES",
        merchant_categories=[
            "Supermercado (Mercadona)",
            "Restaurante",
            "Transporte (Renfe)",
            "Suministros",
            "Compra online",
            "Ocio",
            "Farmacia",
            "Suscripción",
        ],
    ),
    "FR": LocalePack(
        country="FR",
        language="fr",
        currency="EUR",
        income_label="Salaire",
        iban_prefix="FR",
        merchant_categories=[
            "Supermarché (Carrefour)",
            "Restaurant",
            "Transport (SNCF)",
            "Services publics",
            "Achat en ligne",
            "Loisirs",
            "Pharmacie",
            "Abonnement",
        ],
    ),
    "GB": LocalePack(
        country="GB",
        language="en",
        currency="GBP",
        income_label="Salary",
        iban_prefix="GB",
        merchant_categories=[
            "Groceries (Tesco)",
            "Restaurant",
            "Transport (TfL)",
            "Utilities",
            "Online shopping",
            "Entertainment",
            "Pharmacy",
            "Subscription",
        ],
    ),
    "IE": LocalePack(
        country="IE",
        language="en",
        currency="EUR",
        income_label="Salary",
        iban_prefix="IE",
        merchant_categories=[
            "Groceries (Dunnes Stores)",
            "Restaurant",
            "Transport (Irish Rail)",
            "Utilities (ESB)",
            "Online shopping",
            "Entertainment",
            "Pharmacy (Boots)",
            "Subscription",
        ],
    ),
    "NL": LocalePack(
        country="NL",
        language="nl",
        currency="EUR",
        income_label="Salaris",
        iban_prefix="NL",
        merchant_categories=[
            "Boodschappen (Albert Heijn)",
            "Restaurant",
            "Vervoer (NS)",
            "Nutsvoorzieningen",
            "Online winkelen",
            "Vermaak",
            "Apotheek",
            "Abonnement",
        ],
    ),
    "PL": LocalePack(
        country="PL",
        language="pl",
        currency="PLN",
        income_label="Wynagrodzenie",
        iban_prefix="PL",
        merchant_categories=[
            "Zakupy spożywcze (Biedronka)",
            "Restauracja",
            "Transport (PKP)",
            "Media i opłaty",
            "Zakupy online",
            "Rozrywka",
            "Apteka",
            "Subskrypcja",
        ],
    ),
}

_FALLBACK = LocalePack(
    country="ZZ",
    language="en",
    currency="EUR",
    income_label="Income",
    merchant_categories=[
        "Groceries",
        "Restaurants",
        "Transport",
        "Utilities",
        "Online shopping",
        "Entertainment",
        "Healthcare",
        "Subscriptions",
    ],
)


@localization_registry.register
class DefaultLocalizationProvider(LocalizationProvider):
    capability_name = "default"

    def get_pack(self, country: str) -> LocalePack:
        return _PACKS.get((country or "").upper(), _FALLBACK)

    def get_pack_for_language(self, language: str) -> LocalePack | None:
        lang = (language or "").lower()
        for pack in _PACKS.values():
            if pack.language == lang:
                return pack
        return None

    def countries(self) -> list[str]:
        return sorted(_PACKS)
