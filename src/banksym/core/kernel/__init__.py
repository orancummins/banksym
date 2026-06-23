"""Kernel primitives shared across the core domain."""

from banksym.core.kernel.errors import (
    AccountNotFoundError,
    BankSymError,
    CurrencyMismatchError,
    InsufficientFundsError,
    UnbalancedEntryError,
)
from banksym.core.kernel.ids import new_id
from banksym.core.kernel.money import Money
from banksym.core.kernel.registry import Capability, CapabilityRegistry

__all__ = [
    "AccountNotFoundError",
    "BankSymError",
    "Capability",
    "CapabilityRegistry",
    "CurrencyMismatchError",
    "InsufficientFundsError",
    "Money",
    "UnbalancedEntryError",
    "new_id",
]
