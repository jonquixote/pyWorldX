"""Multi-rate co-simulation master scheduler (Section 6.4).

Manages sub-stepping of fast sectors at fixed integer subdivisions
of the master step.  Slow sectors provide frozen last-known values
to fast sectors between communication points.

The scheduler validates all substep ratios at init via
resolve_substep_ratio() and fails loud on non-integer ratios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyworldx.core.integrators import DerivativeFn, rk4_step, euler_step
from pyworldx.core.quantities import Quantity


class IncompatibleTimestepError(Exception):
    """Raised when master_dt / timestep_hint is not an integer."""


def resolve_substep_ratio(
    master_dt: float, timestep_hint: float, tol: float = 1e-9
) -> int:
    """Convert timestep_hint to integer substep ratio (Section 5.3).

    Raises IncompatibleTimestepError if the ratio is not integer within tol.
    """
    ratio = master_dt / timestep_hint
    ratio_int = int(round(ratio))
    if abs(ratio - ratio_int) > tol:
        raise IncompatibleTimestepError(
            f"master_dt={master_dt} / timestep_hint={timestep_hint} = {ratio:.6f}, "
            f"which is not an integer within tolerance {tol}. "
            f"Adjust master_dt or timestep_hint so that their ratio is a whole number."
        )
    return ratio_int


@dataclass
class SubstepRecord:
    """Record of a sub-stepped sector's execution within one master step."""

    sector_name: str
    substep_ratio: int
    sub_dt: float
    final_stocks: dict[str, Quantity] = field(default_factory=dict)
    auxiliaries: dict[str, Quantity] = field(default_factory=dict)


@dataclass
class MultirateScheduler:
    """Manages multi-rate sub-stepping for sectors with timestep_hint.

    Attributes:
        master_dt: master timestep
        sector_ratios: dict mapping sector name -> substep ratio
        sector_integrators: dict mapping sector name -> integrator name
    """

    master_dt: float
    sector_ratios: dict[str, int] = field(default_factory=dict)
    sector_integrators: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_sectors(
        cls, sectors: list[Any], master_dt: float
    ) -> MultirateScheduler:
        """Build scheduler from a list of sectors, validating all ratios.

        Raises IncompatibleTimestepError on non-integer ratios.
        """
        ratios: dict[str, int] = {}
        integrators: dict[str, str] = {}

        for s in sectors:
            hint = s.timestep_hint
            if hint is not None:
                ratios[s.name] = resolve_substep_ratio(master_dt, hint)
            else:
                ratios[s.name] = 1

            # Check preferred sub-step integrator from metadata
            meta = s.metadata()
            integrators[s.name] = str(
                meta.get("preferred_substep_integrator", "rk4")
            )

        return cls(
            master_dt=master_dt,
            sector_ratios=ratios,
            sector_integrators=integrators,
        )

    def is_sub_stepped(self, sector_name: str) -> bool:
        """True if the sector runs at a finer rate than master."""
        return self.sector_ratios.get(sector_name, 1) > 1

    def get_sub_stepped_sectors(self, sectors: list[Any]) -> list[Any]:
        """Return sectors with substep_ratio > 1."""
        return [s for s in sectors if self.is_sub_stepped(s.name)]

    def get_single_rate_sectors(self, sectors: list[Any]) -> list[Any]:
        """Return sectors running at master rate."""
        return [s for s in sectors if not self.is_sub_stepped(s.name)]

    def advance_sector(
        self,
        sector: Any,
        t: float,
        stocks: dict[str, Quantity],
        frozen_inputs: dict[str, Quantity],
        ctx: Any,
        sector_stock_names: list[str],
    ) -> SubstepRecord:
        """Advance a sub-stepped sector across one full master step.

        Uses frozen_inputs (last-known values from master boundary) for
        all inter-sector reads.  The sector's stocks are integrated at
        the sub-step level using the configured integrator.

        Args:
            sector: the sector to advance
            t: time at start of master step
            stocks: current stock values for this sector
            frozen_inputs: frozen shared state at master boundary
            ctx: RunContext
            sector_stock_names: stock names owned by this sector

        Returns:
            SubstepRecord with final stocks and end-of-step auxiliaries
        """
        ratio = self.sector_ratios[sector.name]
        sub_dt = self.master_dt / ratio
        integrator_name = self.sector_integrators.get(sector.name, "rk4")

        # Select integrator
        step_fn = rk4_step if integrator_name == "rk4" else euler_step

        # Extract this sector's stocks
        sub_stocks = {k: stocks[k] for k in sector_stock_names if k in stocks}
        sub_t = t

        for _ in range(ratio):
            def _make_deriv(
                s: Any, inputs: dict[str, Quantity], context: Any
            ) -> DerivativeFn:
                def deriv(
                    t_: float, st: dict[str, Quantity]
                ) -> dict[str, Quantity]:
                    result = s.compute(t_, st, inputs, context)
                    return {
                        k.replace("d_", ""): v
                        for k, v in result.items()
                        if k.startswith("d_")
                    }
                return deriv

            deriv_fn = _make_deriv(sector, frozen_inputs, ctx)
            sub_stocks = step_fn(deriv_fn, sub_t, sub_stocks, sub_dt)
            sub_t += sub_dt

        # Compute auxiliaries at end of master step
        final_out = sector.compute(
            t + self.master_dt, sub_stocks, frozen_inputs, ctx
        )
        auxiliaries = {
            k: v for k, v in final_out.items() if not k.startswith("d_")
        }

        return SubstepRecord(
            sector_name=sector.name,
            substep_ratio=ratio,
            sub_dt=sub_dt,
            final_stocks=sub_stocks,
            auxiliaries=auxiliaries,
        )
