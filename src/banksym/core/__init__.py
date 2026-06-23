"""Core banking domain — the single stateful domain of record.

Nothing in `banksym.core` may import from `banksym.capabilities`, `banksym.api`, or
`banksym.tenancy`. Dependencies point inward: plugins depend on core, never the reverse.
"""
