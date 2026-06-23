"""Storage for Bank tenants."""

from __future__ import annotations

from typing import Protocol

from banksym.tenancy.bank import Bank


class BankRepository(Protocol):
    def add(self, bank: Bank) -> None: ...

    def get(self, bank_id: str) -> Bank | None: ...

    def list(self) -> list[Bank]: ...

    def remove(self, bank_id: str) -> None: ...


class InMemoryBankRepository:
    def __init__(self) -> None:
        self._banks: dict[str, Bank] = {}

    def add(self, bank: Bank) -> None:
        self._banks[bank.id] = bank

    def get(self, bank_id: str) -> Bank | None:
        return self._banks.get(bank_id)

    def list(self) -> list[Bank]:
        return list(self._banks.values())

    def remove(self, bank_id: str) -> None:
        self._banks.pop(bank_id, None)
