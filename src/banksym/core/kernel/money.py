"""Money value object.

Amounts are stored as integer **minor units** (e.g. cents) to avoid floating-point error.
A ``Money`` instance is immutable and tied to a single ISO-4217 currency code.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from banksym.core.kernel.errors import CurrencyMismatchError

# Minor-unit exponents for currencies that are not the default of 2.
_MINOR_UNIT_EXPONENTS: dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "ISK": 0,
    "HUF": 0,
    "CLP": 0,
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
}


def minor_unit_exponent(currency: str) -> int:
    """Return the number of minor-unit digits for a currency (default 2)."""
    return _MINOR_UNIT_EXPONENTS.get(currency.upper(), 2)


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable monetary amount in integer minor units."""

    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", self.currency.upper())
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError(f"Invalid ISO-4217 currency code: {self.currency!r}")

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(0, currency)

    @classmethod
    def from_decimal(cls, amount: Decimal | str | int, currency: str) -> Money:
        """Build ``Money`` from a major-unit decimal (e.g. ``"12.34"`` EUR)."""
        exponent = minor_unit_exponent(currency)
        quantum = Decimal(1).scaleb(-exponent)
        scaled = (Decimal(amount).quantize(quantum, rounding=ROUND_HALF_EVEN)).scaleb(exponent)
        return cls(int(scaled), currency)

    def to_decimal(self) -> Decimal:
        """Return the amount as a major-unit ``Decimal``."""
        exponent = minor_unit_exponent(self.currency)
        return Decimal(self.minor_units).scaleb(-exponent)

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot operate on {self.currency} and {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.minor_units + other.minor_units, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.minor_units - other.minor_units, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.minor_units, self.currency)

    @property
    def is_positive(self) -> bool:
        return self.minor_units > 0

    @property
    def is_negative(self) -> bool:
        return self.minor_units < 0

    @property
    def is_zero(self) -> bool:
        return self.minor_units == 0

    def __str__(self) -> str:
        return f"{self.to_decimal()} {self.currency}"
