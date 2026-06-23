"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path

from banksym.api.container import Container, get_container
from banksym.core.kernel.errors import BankSymError
from banksym.tenancy.service import BankNotFoundError


def container_dep() -> Container:
    return get_container()


ContainerDep = Annotated[Container, Depends(container_dep)]


def resolve_bank_id(
    container: ContainerDep,
    bank_id: Annotated[str, Path()],
) -> str:
    """Ensure the bank exists and return its id (tenant scoping guard)."""
    try:
        container.bank_service.get_bank(bank_id)
    except BankNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return bank_id


BankIdDep = Annotated[str, Depends(resolve_bank_id)]


def to_http_error(exc: BankSymError) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
