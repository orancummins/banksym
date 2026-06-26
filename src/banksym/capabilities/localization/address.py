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


@dataclass(frozen=True, slots=True)
class _NamePack:
    """Per-country name fragments used to generate plausible synthetic customer names."""

    given_names: list[str]
    family_names: list[str]
    family_name_first: bool = False


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
    "PL": _AddressPack(
        country_name="Polska",
        streets=[
            "ul. Marszałkowska",
            "ul. Długa",
            "ul. Kościuszki",
            "ul. Piłsudskiego",
            "ul. Mickiewicza",
            "ul. Słowackiego",
            "ul. Lipowa",
            "ul. Ogrodowa",
        ],
        cities=[
            "Warszawa",
            "Kraków",
            "Łódź",
            "Wrocław",
            "Poznań",
            "Gdańsk",
            "Szczecin",
            "Lublin",
    "US": _AddressPack(
        country_name="United States",
        streets=[
            "Main Street",
            "Maple Avenue",
            "Oak Street",
            "Cedar Lane",
            "Pine Road",
            "Washington Avenue",
            "Park Place",
            "Sunset Boulevard",
        ],
        cities=[
            "New York",
            "San Francisco",
            "Chicago",
            "Seattle",
            "Austin",
            "Boston",
            "Denver",
            "Atlanta",
        ],
    ),
    "CA": _AddressPack(
        country_name="Canada",
        streets=[
            "Queen Street",
            "King Street",
            "Yonge Street",
            "Granville Street",
            "Robson Street",
            "Whyte Avenue",
            "Main Street",
            "Bloor Street",
        ],
        cities=[
            "Toronto",
            "Vancouver",
            "Montréal",
            "Calgary",
            "Ottawa",
            "Edmonton",
            "Halifax",
            "Winnipeg",
        ],
    ),
    "BR": _AddressPack(
        country_name="Brasil",
        streets=[
            "Rua das Flores",
            "Avenida Paulista",
            "Rua XV de Novembro",
            "Rua do Comércio",
            "Avenida Atlântica",
            "Rua da Praia",
            "Rua Sete de Setembro",
            "Avenida Brasil",
        ],
        cities=[
            "São Paulo",
            "Rio de Janeiro",
            "Brasília",
            "Salvador",
            "Curitiba",
            "Recife",
            "Belo Horizonte",
            "Porto Alegre",
        ],
    ),
    "CN": _AddressPack(
        country_name="中国",
        streets=[
            "长安街",
            "人民路",
            "解放大道",
            "中山路",
            "和平路",
            "建设路",
            "新华路",
            "朝阳路",
        ],
        cities=[
            "北京",
            "上海",
            "广州",
            "深圳",
            "杭州",
            "成都",
            "武汉",
            "南京",
        ],
    ),
    "ZA": _AddressPack(
        country_name="South Africa",
        streets=[
            "Nelson Mandela Drive",
            "Church Street",
            "Long Street",
            "Main Road",
            "Jan Smuts Avenue",
            "Voortrekker Road",
            "Oxford Road",
            "Bree Street",
        ],
        cities=[
            "Johannesburg",
            "Cape Town",
            "Durban",
            "Pretoria",
            "Gqeberha",
            "Bloemfontein",
            "Polokwane",
            "Stellenbosch",
        ],
    ),
}

_FALLBACK = _AddressPack(
    country_name="Europe",
    streets=["Main Street", "Market Square", "Park Road", "Station Road", "Church Street"],
    cities=["Capital City", "Riverside", "Lakeside", "Greenfield", "Newport"],
)

_NAME_PACKS: dict[str, _NamePack] = {
    "DE": _NamePack(
        given_names=["Anna", "Lukas", "Mia", "Leon", "Sophie", "Paul", "Emilia", "Jonas"],
        family_names=["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker"],
    ),
    "ES": _NamePack(
        given_names=["Lucía", "Mateo", "Sofía", "Hugo", "Martina", "Daniel", "Valeria", "Pablo"],
        family_names=["García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Fernández", "Ruiz"],
    ),
    "FR": _NamePack(
        given_names=["Emma", "Louis", "Jade", "Gabriel", "Alice", "Raphaël", "Chloé", "Lucas"],
        family_names=["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand"],
    ),
    "GB": _NamePack(
        given_names=["Olivia", "George", "Amelia", "Arthur", "Isla", "Leo", "Grace", "Freddie"],
        family_names=["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Evans", "Thomas"],
    ),
    "IE": _NamePack(
        given_names=["Aoife", "Cian", "Saoirse", "Oisín", "Clodagh", "Darragh", "Niamh", "Tadhg"],
        family_names=["Murphy", "Kelly", "Byrne", "Ryan", "O'Connor", "Walsh", "McCarthy", "O'Sullivan"],
    ),
    "NL": _NamePack(
        given_names=["Sanne", "Daan", "Julia", "Sem", "Lotte", "Milan", "Tess", "Finn"],
        family_names=["De Jong", "Jansen", "De Vries", "Van den Berg", "Bakker", "Janssen", "Visser", "Smit"],
    ),
    "US": _NamePack(
        given_names=["Ava", "Noah", "Charlotte", "Liam", "Harper", "Elijah", "Evelyn", "James"],
        family_names=["Johnson", "Smith", "Brown", "Miller", "Davis", "Wilson", "Moore", "Taylor"],
    ),
    "CA": _NamePack(
        given_names=["Olivia", "Liam", "Emma", "Noah", "Sophie", "Benjamin", "Mia", "Logan"],
        family_names=["Martin", "Roy", "Tremblay", "Lee", "Wilson", "Anderson", "Chen", "Campbell"],
    ),
    "BR": _NamePack(
        given_names=["Ana", "Miguel", "Helena", "Theo", "Laura", "Davi", "Beatriz", "Enzo"],
        family_names=["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa", "Rodrigues", "Almeida"],
    ),
    "CN": _NamePack(
        given_names=["伟", "芳", "娜", "敏", "静", "丽", "强", "磊"],
        family_names=["王", "李", "张", "刘", "陈", "杨", "黄", "赵"],
        family_name_first=True,
    ),
    "ZA": _NamePack(
        given_names=["Amahle", "Lethabo", "Sipho", "Naledi", "Thabo", "Zanele", "Aiden", "Mia"],
        family_names=["Nkosi", "Dlamini", "Mokoena", "Naidoo", "Pillay", "Smith", "Botha", "Khumalo"],
    ),
}

_FALLBACK_NAMES = _NamePack(
    given_names=["Alex", "Jamie", "Taylor", "Jordan", "Casey", "Morgan"],
    family_names=["Smith", "Brown", "Taylor", "Martin", "Wilson", "Moore"],
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
    if code == "PL":
        postcode = f"{_digits(rng, 2)}-{_digits(rng, 3)}"
        return f"{street} {number}\n{postcode} {city}\n{pack.country_name}"
    if code == "US":
        state = rng.choice(["CA", "NY", "TX", "WA", "IL", "MA", "CO", "GA"])
        zipcode = _digits(rng, 5)
        return f"{number} {street}\n{city}, {state} {zipcode}\n{pack.country_name}"
    if code == "CA":
        province = rng.choice(["ON", "BC", "QC", "AB", "NS", "MB"])
        postal = f"{_letters(rng, 1)}{_digits(rng, 1)}{_letters(rng, 1)} {_digits(rng, 1)}{_letters(rng, 1)}{_digits(rng, 1)}"
        return f"{number} {street}\n{city}, {province} {postal}\n{pack.country_name}"
    if code == "BR":
        cep = f"{_digits(rng, 5)}-{_digits(rng, 3)}"
        return f"{street}, {number}\n{city} - {rng.choice(['SP', 'RJ', 'MG', 'PR', 'BA', 'RS'])}\nCEP {cep}\n{pack.country_name}"
    if code == "CN":
        district = rng.choice(["朝阳区", "海淀区", "浦东新区", "天河区", "南山区", "武侯区"])
        postcode = _digits(rng, 6)
        return f"{pack.country_name}{city}{district}{street}{number}号\n邮编 {postcode}"
    if code == "ZA":
        postcode = _digits(rng, 4)
        return f"{number} {street}\n{city}\n{postcode}\n{pack.country_name}"
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
    "PL": ("+48", ["501", "503", "505", "510", "512", "600", "601", "660", "720", "790"], 6, [3, 3]),
    "US": ("+1", ["201", "212", "310", "415", "512", "617"], 7, [3, 4]),
    "CA": ("+1", ["204", "236", "403", "416", "514", "604"], 7, [3, 4]),
    "BR": ("+55", ["11 9", "21 9", "31 9", "41 9"], 8, [4, 4]),
    "CN": ("+86", ["13", "15", "17", "18", "19"], 9, [3, 4, 2]),
    "ZA": ("+27", ["71", "72", "73", "74", "76", "82", "83"], 7, [3, 4]),
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


def random_full_name(country: str | None, rng: random.Random | None = None) -> str:
    """Return a plausible synthetic full name for ``country``.

    Uses a small local name catalogue and falls back to a generic western-style name when the
    country has no dedicated pack.
    """
    rng = rng or random.Random()
    pack = _NAME_PACKS.get((country or "").upper(), _FALLBACK_NAMES)
    given = rng.choice(pack.given_names)
    family = rng.choice(pack.family_names)
    if pack.family_name_first:
        return f"{family}{given}"
    return f"{given} {family}"
