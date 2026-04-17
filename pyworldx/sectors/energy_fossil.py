"""Fossil Energy sub-sector (Phase 1 Task 3).

Hydrocarbons + conventional nuclear. EROI declines with ore grade
(NR depletion). Competes for capital via endogenous profitability.

Stock: fossil_capital (capital dedicated to fossil extraction)
EROI: declines as NRFR (nonrenewable resource fraction remaining) drops
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


_FOSSIL_K0 = 1.0e11   # initial fossil capital
_EROI_MAX = 30.0       # peak EROI at full reserves
_EROI_MIN = 2.0        # floor EROI at depletion
_DEPRECIATION = 0.05   # annual depreciation rate


class EnergyFossilSector:
    """Fossil fuel extraction with declining EROI.

    Stock: fossil_capital
    Reads: NR, NRFR, industrial_output, supply_multiplier_fossil
    Writes: fossil_capital, fossil_output, fossil_eroi, energy_demand_fossil
    """

    name = "energy_fossil"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_capital: float = _FOSSIL_K0,
        eroi_max: float = _EROI_MAX,
        eroi_min: float = _EROI_MIN,
    ) -> None:
        self.initial_capital = initial_capital
        self.eroi_max = eroi_max
        self.eroi_min = eroi_min

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "fossil_capital": Quantity(self.initial_capital, "capital_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        fk = stocks["fossil_capital"].magnitude
        nrfr = inputs.get(
            "nr_fraction_remaining", Quantity(1.0, "dimensionless")
        ).magnitude
        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        supply_mult = inputs.get(
            "supply_multiplier_fossil", Quantity(1.0, "dimensionless")
        ).magnitude

        # EROI declines with depletion (ore grade effect)
        eroi = self.eroi_min + (self.eroi_max - self.eroi_min) * nrfr

        # Fossil output = capital * EROI factor * supply multiplier
        output = fk * (eroi / self.eroi_max) * supply_mult

        # Energy demand: self-consumption (energy cost of extraction = output/EROI)
        energy_demand = output / max(eroi, 1.0)

        # Investment: endogenous profitability-based (higher profit attracts more)
        profitability = eroi / self.eroi_max
        investment = io * 0.05 * profitability  # 5% of IO * profitability

        # Depreciation
        depreciation = fk * _DEPRECIATION

        return {
            "d_fossil_capital": Quantity(
                investment - depreciation, "capital_units"
            ),
            "fossil_output": Quantity(output, "energy_units"),
            "fossil_eroi": Quantity(eroi, "dimensionless"),
            "energy_demand_fossil": Quantity(energy_demand, "energy_units"),
        }

    def declares_reads(self) -> list[str]:
        return ["nr_fraction_remaining", "industrial_output", "supply_multiplier_fossil"]

    def declares_writes(self) -> list[str]:
        return [
            "fossil_capital",
            "fossil_output",
            "fossil_eroi",
            "energy_demand_fossil",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.DESIGN_CHOICE,
            "world7_alignment": WORLD7Alignment.APPROXIMATE,
            "approximations": [
                "Linear EROI decline with NRFR",
                "Fixed investment fraction of IO",
            ],
            "free_parameters": ["initial_capital", "eroi_max", "eroi_min"],
            "conservation_groups": [],
            "observables": ["fossil_output", "fossil_eroi"],
            "unit_notes": "energy_units, capital_units",
        }
