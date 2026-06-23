"""Customer entity — a person or organisation holding accounts at a bank."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from banksym.core.kernel.ids import new_id


@dataclass(slots=True)
class Customer:
    """A bank customer (the natural/legal person, distinct from login credentials)."""

    bank_id: str
    full_name: str
    id: str = field(default_factory=lambda: new_id("cus_"))
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    country: str | None = None
    address: str | None = None
    """Plausible synthetic postal address, auto-generated for the customer's country."""
    persona: str | None = None
    """Optional archetype label this customer was generated from (e.g. ``"gig_worker"``)."""
