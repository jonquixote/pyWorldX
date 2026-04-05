"""Base sector protocol and run context.

Defines the contract that all sectors must satisfy (Section 5.1)
and the RunContext passed through the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pyworldx.core.quantities import Quantity


@dataclass
class RunContext:
    """Shared context passed to sectors during each compute call.

    Carries configuration, master timestep, and inter-sector communication
    values (frozen last-known for multi-rate boundaries).
    """

    master_dt: float = 1.0
    t_start: float = 0.0
    t_end: float = 200.0
    shared_state: dict[str, Quantity] = field(default_factory=dict)

    def get_input(self, name: str) -> Quantity:
        """Retrieve a named value from the shared inter-sector state."""
        if name not in self.shared_state:
            raise KeyError(
                f"Required input '{name}' not found in shared state. "
                f"Available: {list(self.shared_state.keys())}"
            )
        return self.shared_state[name]


@runtime_checkable
class BaseSector(Protocol):
    """Protocol defining the sector contract (Section 5.1).

    Every sector must implement this interface.
    """

    name: str
    version: str
    timestep_hint: float | None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        """Return initial stock values with units."""
        ...

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        """Compute flows, auxiliaries, and observables for this timestep.

        Returns a dict of named Quantity outputs including derivatives
        of stocks (prefixed with 'd_' by convention) and auxiliary values.
        """
        ...

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        """Declare intra-sector algebraic loop expectations."""
        ...

    def metadata(self) -> dict[str, object]:
        """Return sector metadata per Section 5.4."""
        ...

    def declares_reads(self) -> list[str]:
        """Names of variables this sector reads from other sectors."""
        ...

    def declares_writes(self) -> list[str]:
        """Names of variables this sector writes to shared state."""
        ...
