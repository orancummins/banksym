"""Identifier helpers.

IDs are opaque strings (UUID4 hex) so they are safe to expose over protocol APIs without
leaking sequential/internal information.
"""

from __future__ import annotations

import uuid


def new_id(prefix: str = "") -> str:
    """Return a new opaque identifier, optionally prefixed (e.g. ``acc_``)."""
    raw = uuid.uuid4().hex
    return f"{prefix}{raw}" if prefix else raw
