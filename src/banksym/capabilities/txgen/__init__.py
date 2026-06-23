"""Transaction generation capability.

A :class:`TransactionGenerator` synthesizes realistic transaction history for a customer by
writing balanced journal entries through :class:`~banksym.core.service.CoreBankingService`. The
core domain is agnostic to *how* postings were produced, so generators (rule-based, LLM-assisted,
replay, statistical) are fully interchangeable.
"""

from banksym.capabilities.txgen.base import (
    GenerationRequest,
    TransactionGenerator,
    txgen_registry,
)

__all__ = ["GenerationRequest", "TransactionGenerator", "txgen_registry"]
