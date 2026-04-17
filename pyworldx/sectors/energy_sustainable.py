"""Sustainable Energy sub-sector (Phase 1 Task 3).

Hydropower, biofuels. EROI relatively stable (not dependent on
finite resource depletion). Lower variance, steady contribution.

Stock: sustainable_capital
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


_SUST_K0 = 2.0e10     # initial sustainable capital
_EROI_STABLE = 12.0    # stable EROI for renewables
_DEPRECIATION = 0.03   # annual depreciation (longer-lived infrastructure)


class EnergySustainableSector:
    """Sustainable energy (hydro, biofuels) with stable EROI.

    Stock: sustainable_capital
    Reads: industrial_output, supply_multiplier_sustainable
    Writes: sustainable_capital, sustainable_output, sustainable_eroi
    """

    name = "energy_sustainable"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_capital: float = _SUST_K0,
        eroi: float = _EROI_STABLE,
    ) -> None:
        self.initial_capital = initial_capital
        self.eroi = eroi

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "sustainable_capital": Quantity(
                self.initial_capital, "capital_units"
            ),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        sk = stocks["sustainable_capital"].magnitude
        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        supply_mult = inputs.get(
            "supply_multiplier_sustainable", Quantity(1.0, "dimensionless")
        ).magnitude

        output = sk * (self.eroi / 30.0) * supply_mult
        # Energy demand: self-consumption (energy cost of extraction = output/EROI)
        energy_demand = output / max(self.eroi, 1.0)

        # Investment proportional to IO * profitability
        profitability = self.eroi / 30.0
        investment = io * 0.03 * profitability

        depreciation = sk * _DEPRECIATION

        return {
            "d_sustainable_capital": Quantity(
                investment - depreciation, "capital_units"
            ),
            "sustainable_output": Quantity(output, "energy_units"),
            "sustainable_eroi": Quantity(self.eroi, "dimensionless"),
            "energy_demand_sustainable": Quantity(
                energy_demand, "energy_units"
            ),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "supply_multiplier_sustainable"]

    def declares_writes(self) -> list[str]:
        return [
            "sustainable_capital",
            "sustainable_output",
            "sustainable_eroi",
            "energy_demand_sustainable",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.DESIGN_CHOICE,
            "world7_alignment": WORLD7Alignment.APPROXIMATE,
            "approximations": ["Fixed EROI (no depletion dependency)"],
            "free_parameters": ["initial_capital", "eroi"],
            "conservation_groups": [],
            "observables": ["sustainable_output", "sustainable_eroi"],
            "unit_notes": "energy_units, capital_units",
        }
