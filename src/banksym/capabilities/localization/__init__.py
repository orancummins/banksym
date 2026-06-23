"""Localization capability.

A :class:`LocalizationProvider` supplies country-specific banking flavour: language, currency,
localized merchant/transaction categories and income labels. Capabilities such as transaction
generators consult it so a simulated bank in Spain produces Spanish merchant names and EUR amounts,
while one in the UK uses GBP and English.
"""

from banksym.capabilities.localization.base import (
    LocalePack,
    LocalizationProvider,
    localization_registry,
)

__all__ = ["LocalePack", "LocalizationProvider", "localization_registry"]
