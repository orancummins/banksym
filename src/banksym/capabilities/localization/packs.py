"""Default localization provider with a catalog of bundled country and language packs."""

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
    "US": LocalePack(
        country="US",
        language="en",
        currency="USD",
        income_label="Paycheck",
        iban_prefix="US",
        merchant_categories=[
            "Groceries (Trader Joe's)",
            "Restaurant",
            "Transport (Amtrak)",
            "Utilities",
            "Online shopping",
            "Entertainment",
            "Pharmacy (CVS)",
            "Subscription",
        ],
    ),
    "CA": LocalePack(
        country="CA",
        language="en",
        currency="CAD",
        income_label="Paycheque",
        iban_prefix="CA",
        merchant_categories=[
            "Groceries (Loblaws)",
            "Restaurant",
            "Transport (VIA Rail)",
            "Utilities",
            "Online shopping",
            "Entertainment",
            "Pharmacy (Shoppers Drug Mart)",
            "Subscription",
        ],
    ),
    "BR": LocalePack(
        country="BR",
        language="pt",
        currency="BRL",
        income_label="Salário",
        iban_prefix="BR",
        merchant_categories=[
            "Supermercado (Pão de Açúcar)",
            "Restaurante",
            "Transporte",
            "Contas domésticas",
            "Compra online",
            "Lazer",
            "Farmácia",
            "Assinatura",
        ],
    ),
    "CN": LocalePack(
        country="CN",
        language="zh",
        currency="CNY",
        income_label="工资",
        iban_prefix="CN",
        merchant_categories=[
            "超市",
            "餐饮",
            "交通",
            "水电煤",
            "网购",
            "娱乐",
            "药房",
            "订阅服务",
        ],
    ),
    "ZA": LocalePack(
        country="ZA",
        language="en",
        currency="ZAR",
        income_label="Salary",
        iban_prefix="ZA",
        merchant_categories=[
            "Groceries (Pick n Pay)",
            "Restaurant",
            "Transport (Gautrain)",
            "Utilities",
            "Online shopping",
            "Entertainment",
            "Pharmacy (Clicks)",
            "Subscription",
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
