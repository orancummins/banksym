"""Persona archetypes — reusable customer profiles that drive transaction generation.

A persona captures the coarse financial shape of a customer type. Generators consume the profile
to size income and spending; the catalog is also surfaced to the UI so a bank can be seeded with a
realistic population.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    """Financial shape of a persona, in major currency units per month."""

    id: str
    label: str
    description: str
    monthly_income: float
    monthly_spend_ratio: float  # fraction of income spent
    spend_volatility: float  # 0..1, higher = more variable transaction sizes


PERSONAS: dict[str, PersonaProfile] = {
    p.id: p
    for p in [
        PersonaProfile(
            "gig_worker",
            "Gig worker",
            "Irregular platform payouts, tight cash flow, frequent small spends.",
            2100,
            0.85,
            0.6,
        ),
        PersonaProfile(
            "affluent_family",
            "Affluent family",
            "High dual income, mortgage and family spending, stable.",
            7800,
            0.7,
            0.35,
        ),
        PersonaProfile(
            "student",
            "Student",
            "Low stipend income, budget spending, occasional larger costs.",
            950,
            0.95,
            0.5,
        ),
        PersonaProfile(
            "retiree",
            "Retiree",
            "Steady pension income, conservative and predictable spending.",
            2400,
            0.6,
            0.25,
        ),
        PersonaProfile(
            "young_professional",
            "Young professional",
            "Single salary, discretionary spend on leisure and subscriptions.",
            3600,
            0.8,
            0.4,
        ),
    ]
}

DEFAULT_PROFILE = PersonaProfile(
    "default", "General", "Average retail customer.", 2800, 0.75, 0.4
)


def profile_for(persona: str | None) -> PersonaProfile:
    if persona is None:
        return DEFAULT_PROFILE
    return PERSONAS.get(persona, DEFAULT_PROFILE)
