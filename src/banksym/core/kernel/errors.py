"""Stable error hierarchy for the core domain."""

from __future__ import annotations


class BankSymError(Exception):
    """Base class for all BankSym domain errors."""

    code: str = "banksym_error"


class CurrencyMismatchError(BankSymError):
    code = "currency_mismatch"


class UnbalancedEntryError(BankSymError):
    """A journal entry whose debits and credits do not net to zero."""

    code = "unbalanced_entry"


class InsufficientFundsError(BankSymError):
    code = "insufficient_funds"


class AccountNotFoundError(BankSymError):
    code = "account_not_found"


class CustomerNotFoundError(BankSymError):
    code = "customer_not_found"


class CapabilityNotFoundError(BankSymError):
    code = "capability_not_found"
