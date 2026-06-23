"""Tests for the Money value object."""

from decimal import Decimal

import pytest

from banksym.core.kernel.errors import CurrencyMismatchError
from banksym.core.kernel.money import Money


def test_from_decimal_and_back():
    m = Money.from_decimal("12.34", "EUR")
    assert m.minor_units == 1234
    assert m.to_decimal() == Decimal("12.34")
    assert str(m) == "12.34 EUR"


def test_zero_decimal_currency_jpy():
    m = Money.from_decimal("1500", "JPY")
    assert m.minor_units == 1500
    assert m.to_decimal() == Decimal("1500")


def test_addition_and_subtraction():
    assert Money(100, "EUR") + Money(50, "EUR") == Money(150, "EUR")
    assert Money(100, "EUR") - Money(150, "EUR") == Money(-50, "EUR")


def test_currency_mismatch_raises():
    with pytest.raises(CurrencyMismatchError):
        Money(100, "EUR") + Money(100, "USD")


def test_invalid_currency_code():
    with pytest.raises(ValueError):
        Money(100, "EU")
