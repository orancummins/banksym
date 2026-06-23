"""Capability registry — the backbone of the pluggable architecture.

A *capability* is any swappable mechanism (a protocol adapter, a transaction generator, an auth
provider, a settlement engine, ...). Each capability **interface** lives with its plugin package;
core only provides the generic registration machinery here. Core defines the contract for *what a
registered capability looks like*, never the concrete implementations.

Implementations register themselves against a ``(kind, name)`` key and are resolved per-bank by
configuration.
"""

from __future__ import annotations

from typing import ClassVar, TypeVar

from banksym.core.kernel.errors import CapabilityNotFoundError


class Capability:
    """Base class for every pluggable capability implementation.

    Subclasses set two class attributes:

    * ``capability_kind`` — the interface family, e.g. ``"protocol"`` or ``"txgen"``.
    * ``capability_name`` — the unique implementation name within that family,
      e.g. ``"berlin_group"``.
    """

    capability_kind: ClassVar[str] = ""
    capability_name: ClassVar[str] = ""


C = TypeVar("C", bound=Capability)


class CapabilityRegistry[C: Capability]:
    """A registry for one capability *kind* (one interface family).

    Each capability interface package owns a singleton registry instance and exposes a
    ``register`` decorator. Banks then select an implementation by name.
    """

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._impls: dict[str, type[C]] = {}

    @property
    def kind(self) -> str:
        return self._kind

    def register(self, impl: type[C]) -> type[C]:
        """Register a capability implementation class. Usable as a decorator."""
        name = impl.capability_name
        if not name:
            raise ValueError(f"{impl.__name__} must set capability_name")
        if impl.capability_kind not in ("", self._kind):
            raise ValueError(
                f"{impl.__name__} declares kind {impl.capability_kind!r}, "
                f"expected {self._kind!r}"
            )
        impl.capability_kind = self._kind
        self._impls[name] = impl
        return impl

    def get(self, name: str) -> type[C]:
        try:
            return self._impls[name]
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"No {self._kind!r} capability named {name!r}. "
                f"Available: {sorted(self._impls)}"
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._impls)

    def __contains__(self, name: object) -> bool:
        return name in self._impls
