"""WILIAM Economy pseudo-sector (Section 15).

Runs inside the pyWorldX engine as a sub-stepped sector.
timestep_hint is a computed property: master_dt / substep_ratio.
resolve_substep_ratio() is called on this value at engine init.

Recommended default: 4:1 ratio (0.25 yr substep beneath 1.0 yr master step).
Rationale: quarterly internal investment and depreciation flows.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


@dataclass
class WiliamAdapterConfig:
    """WILIAM adapter configuration (Section 15.1)."""

    substep_ratio: int = 4
    price_base_year: int = 2015
    price_base_currency: str = "EUR"


class WiliamEconomySector:
    """WILIAM-derived economy sector running as a pyWorldX sub-stepped sector.

    Stock: wiliam_K (capital stock in constant 2015 EUR)
    Reads: (none — standalone economic sector)
    Writes: wiliam_K, wiliam_output, wiliam_investment, wiliam_military_fraction

    The sector exposes timestep_hint as a computed property:
        timestep_hint = master_dt / config.substep_ratio
    This is resolved via resolve_substep_ratio() at engine init.
    """

    name = "wiliam_economy"
    version = "1.1.0"
    _master_dt: float | None = None

    def __init__(self, config: WiliamAdapterConfig | None = None) -> None:
        self.config = config or WiliamAdapterConfig()

        # Parameters (simplified WILIAM economic dynamics)
        self.initial_capital: float = 5000.0  # constant 2015 EUR (billions)
        self.depreciation_rate: float = 0.04  # annual
        self.investment_rate: float = 0.22  # fraction of output
        self.output_elasticity: float = 0.3  # capital elasticity
        self.military_fraction: float = 0.02  # fraction of output to military
        self.tfp: float = 1.0  # total factor productivity

    def set_master_dt(self, master_dt: float) -> None:
        """Called by engine at init to set master timestep."""
        self._master_dt = master_dt

    @property
    def timestep_hint(self) -> float | None:
        """Computed property: master_dt / substep_ratio (Section 15.1).

        resolve_substep_ratio() is still called on this value —
        the single validation path is never bypassed.
        """
        if self._master_dt is None:
            return None
        return self._master_dt / self.config.substep_ratio

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "wiliam_K": Quantity(self.initial_capital, "capital_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        k = stocks["wiliam_K"].magnitude

        # Simplified Cobb-Douglas output
        output = self.tfp * (k ** self.output_elasticity)

        # Investment and depreciation
        investment = self.investment_rate * output
        depreciation = self.depreciation_rate * k

        # Military allocation (Section 15.4)
        military = self.military_fraction * output

        return {
            "d_wiliam_K": Quantity(
                investment - depreciation, "capital_units"
            ),
            "wiliam_output": Quantity(output, "industrial_output_units"),
            "wiliam_investment": Quantity(investment, "capital_units"),
            "wiliam_military_fraction": Quantity(
                self.military_fraction, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return []

    def declares_writes(self) -> list[str]:
        return [
            "wiliam_K",
            "wiliam_output",
            "wiliam_investment",
            "wiliam_military_fraction",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": "EXPERIMENTAL",
            "equation_source": "ADAPTER_DERIVED",
            "world7_alignment": "APPROXIMATE",
            "approximations": [
                "Simplified Cobb-Douglas production function",
                "Fixed investment and military fractions",
                "No labor input (capital-only proxy)",
            ],
            "free_parameters": [
                "depreciation_rate",
                "investment_rate",
                "output_elasticity",
                "military_fraction",
                "tfp",
            ],
            "conservation_groups": [],
            "observables": ["wiliam_output", "wiliam_investment"],
            "unit_notes": (
                f"Price base: {self.config.price_base_year} "
                f"{self.config.price_base_currency}"
            ),
            "preferred_substep_integrator": "rk4",
        }
