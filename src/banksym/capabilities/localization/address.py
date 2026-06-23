"""Plausible random postal-address generation for supported countries.

Used to give every customer a believable home address when they are created. Addresses are
purely synthetic — street/city names are drawn from small per-country catalogues and numbers /
postcodes are randomised, so they never correspond to a real person.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _AddressPack:
    """Per-country building blocks used to compose a postal address."""

    country_name: str
    streets: list[str]
    cities: list[str]


_ADDRESS_PACKS: dict[str, _AddressPack] = {
    "DE": _AddressPack(
        country_name="Deutschland",
        streets=[
            "Hauptstraße",
            "Bahnhofstraße",
            "Schillerstraße",
            "Goethestraße",
            "Lindenweg",
            "Gartenstraße",
            "Bergstraße",
            "Kirchgasse",
        ],
        cities=[
            "Berlin",
            "München",
            "Hamburg",
            "Köln",
            "Frankfurt am Main",
            "Stuttgart",
            "Düsseldorf",
            "Leipzig",
        ],
    ),
    "ES": _AddressPack(
        country_name="España",
        streets=[
            "Calle Mayor",
            "Avenida de la Constitución",
            "Calle de Alcalá",
            "Gran Vía",
            "Paseo de Gracia",
            "Calle del Carmen",
            "Calle Real",
            "Avenida de América",
        ],
        cities=[
            "Madrid",
            "Barcelona",
            "Valencia",
            "Sevilla",
            "Zaragoza",
            "Málaga",
            "Bilbao",
            "Granada",
        ],
    ),
    "FR": _AddressPack(
        country_name="France",
        streets=[
            "Rue de la République",
            "Avenue des Champs-Élysées",
            "Boulevard Saint-Germain",
            "Rue Victor Hugo",
            "Rue de la Paix",
            "Rue du Faubourg",
            "Place de la Mairie",
            "Allée des Tilleuls",
        ],
        cities=[
            "Paris",
            "Lyon",
            "Marseille",
            "Toulouse",
            "Nice",
            "Nantes",
            "Bordeaux",
            "Lille",
        ],
    ),
    "GB": _AddressPack(
        country_name="United Kingdom",
        streets=[
            "High Street",
            "Station Road",
            "Church Lane",
            "Victoria Road",
            "King Street",
            "Queen Street",
            "Mill Lane",
            "Park Avenue",
        ],
        cities=[
            "London",
            "Manchester",
            "Birmingham",
            "Leeds",
            "Glasgow",
            "Bristol",
            "Liverpool",
            "Edinburgh",
        ],
    ),
    "IE": _AddressPack(
        country_name="Ireland",
        streets=[
            "O'Connell Street",
            "Grafton Street",
            "Patrick Street",
            "Henry Street",
            "Dame Street",
            "Shop Street",
            "Eyre Square",
            "The Quays",
        ],
        cities=[
            "Dublin",
            "Cork",
            "Galway",
            "Limerick",
            "Waterford",
            "Drogheda",
            "Kilkenny",
            "Sligo",
        ],
    ),
    "NL": _AddressPack(
        country_name="Nederland",
        streets=[
            "Kerkstraat",
            "Dorpsstraat",
            "Hoofdstraat",
            "Schoolstraat",
            "Molenweg",
            "Stationsweg",
            "Nieuwstraat",
            "Julianalaan",
        ],
        cities=[
            "Amsterdam",
            "Rotterdam",
            "Den Haag",
            "Utrecht",
            "Eindhoven",
            "Groningen",
            "Haarlem",
            "Maastricht",
        ],
    ),
}

_FALLBACK = _AddressPack(
    country_name="Europe",
    streets=["Main Street", "Market Square", "Park Road", "Station Road", "Church Street"],
    cities=["Capital City", "Riverside", "Lakeside", "Greenfield", "Newport"],
)


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def _gb_postcode(rng: random.Random) -> str:
    area = rng.choice(["SW", "EC", "NW", "SE", "E", "N", "M", "B", "LS", "G", "BS"])
    return f"{area}{rng.randint(1, 19)} {rng.randint(1, 9)}{_letters(rng, 2)}"


def _ie_eircode(rng: random.Random) -> str:
    """Plausible Irish Eircode: a 3-character routing key plus a 4-character unique identifier."""
    routing = rng.choice(["D02", "D04", "D08", "T12", "T23", "H91", "V94", "R95", "F92", "P31"])
    chars = string.ascii_uppercase + string.digits
    unique = "".join(rng.choice(chars) for _ in range(4))
    return f"{routing} {unique}"


def _letters(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def random_address(country: str | None, rng: random.Random | None = None) -> str:
    """Return a plausible, fully synthetic multi-line postal address for ``country``.

    Falls back to a generic European address when the country has no dedicated pack. Pass a seeded
    :class:`random.Random` for deterministic output (e.g. in tests).
    """
    rng = rng or random.Random()
    code = (country or "").upper()
    pack = _ADDRESS_PACKS.get(code, _FALLBACK)
    street = rng.choice(pack.streets)
    city = rng.choice(pack.cities)
    number = rng.randint(1, 199)

    if code == "GB":
        return f"{number} {street}\n{city}\n{_gb_postcode(rng)}\n{pack.country_name}"
    if code == "IE":
        return f"{number} {street}\n{city}\n{_ie_eircode(rng)}\n{pack.country_name}"
    if code == "NL":
        postcode = f"{_digits(rng, 4)} {_letters(rng, 2)}"
        return f"{street} {number}\n{postcode} {city}\n{pack.country_name}"
    if code == "ES":
        postcode = _digits(rng, 5)
        return f"{street}, {number}\n{postcode} {city}\n{pack.country_name}"
    if code == "FR":
        postcode = _digits(rng, 5)
        return f"{number} {street}\n{postcode} {city}\n{pack.country_name}"
    # DE and the generic fallback both use "Street Number / Postcode City".
    postcode = _digits(rng, 5)
    return f"{street} {number}\n{postcode} {city}\n{pack.country_name}"


# Per-country mobile phone formats. Each entry is (dialling code, list of mobile prefixes,
# number of remaining subscriber digits, grouping of those digits for display).
_PHONE_PACKS: dict[str, tuple[str, list[str], int, list[int]]] = {
    "DE": ("+49", ["151", "152", "157", "160", "170", "171", "175"], 7, [3, 4]),
    "ES": ("+34", ["6", "7"], 8, [2, 3, 3]),
    "FR": ("+33", ["6", "7"], 8, [2, 2, 2, 2]),
    "GB": ("+44", ["7400", "7700", "7800", "7900", "7911"], 6, [3, 3]),
    "IE": ("+353", ["83", "85", "86", "87", "89"], 7, [3, 4]),
    "NL": ("+31", ["6"], 8, [4, 4]),
}

_FALLBACK_PHONE = ("+44", ["7700"], 6, [3, 3])


def _grouped(digits: str, groups: list[int]) -> str:
    """Split ``digits`` into space-separated chunks following ``groups`` (remainder kept whole)."""
    out: list[str] = []
    i = 0
    for size in groups:
        out.append(digits[i : i + size])
        i += size
    if i < len(digits):
        out.append(digits[i:])
    return " ".join(p for p in out if p)


def random_phone(country: str | None, rng: random.Random | None = None) -> str:
    """Return a plausible, fully synthetic mobile phone number for ``country``.

    Numbers use the country's international dialling code and a realistic mobile prefix, with the
    remaining subscriber digits randomised. Falls back to a generic format for unsupported
    countries. Pass a seeded :class:`random.Random` for deterministic output (e.g. in tests).
    """
    rng = rng or random.Random()
    code = (country or "").upper()
    dial, prefixes, subscriber_len, groups = _PHONE_PACKS.get(code, _FALLBACK_PHONE)
    prefix = rng.choice(prefixes)
    body = _digits(rng, subscriber_len)
    return f"{dial} {prefix} {_grouped(body, groups)}"
