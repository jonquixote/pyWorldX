"""Simulation state container.

SimState holds stock values per timestep as an immutable snapshot.
The engine creates a new SimState at each integration step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from pyworldx.core.quantities import Quantity


@dataclass(frozen=True)
class SimState:
    """Immutable snapshot of all stock values at a point in time.

    Keyed by canonical stock name, values are Quantity objects.
    """

    _stocks: dict[str, Quantity] = field(default_factory=dict)

    def __getitem__(self, name: str) -> Quantity:
        return self._stocks[name]

    def __contains__(self, name: str) -> bool:
        return name in self._stocks

    def __iter__(self) -> Iterator[str]:
        return iter(self._stocks)

    def __len__(self) -> int:
        return len(self._stocks)

    def keys(self) -> list[str]:
        """Return stock names."""
        return list(self._stocks.keys())

    def items(self) -> list[tuple[str, Quantity]]:
        """Return (name, quantity) pairs."""
        return list(self._stocks.items())

    def to_dict(self) -> dict[str, Quantity]:
        """Return a mutable copy of the internal stock dictionary."""
        return dict(self._stocks)

    @classmethod
    def from_dict(cls, stocks: dict[str, Quantity]) -> SimState:
        """Create SimState from a stock dictionary (defensive copy)."""
        return cls(_stocks=dict(stocks))

    def updated(self, new_stocks: dict[str, Quantity]) -> SimState:
        """Return a new SimState with the given stocks replaced/added."""
        merged = dict(self._stocks)
        merged.update(new_stocks)
        return SimState(_stocks=merged)
