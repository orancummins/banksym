"""Pluggable capabilities.

Each sub-package owns one capability *interface family*: an abstract interface, a singleton
:class:`~banksym.core.kernel.registry.CapabilityRegistry`, and one or more implementations.
Capabilities depend on :class:`~banksym.core.service.CoreBankingService`; core never depends on
them.
"""
