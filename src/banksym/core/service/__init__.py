"""The core banking service — the single public interface plugins depend on."""

from banksym.core.service.banking import CoreBankingService
from banksym.core.service.repository import (
    CoreBankingRepository,
    InMemoryCoreBankingRepository,
)

__all__ = [
    "CoreBankingRepository",
    "CoreBankingService",
    "InMemoryCoreBankingRepository",
]
