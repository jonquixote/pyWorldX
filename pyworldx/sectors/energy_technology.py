"""Technology Energy sub-sector (Phase 1 Task 3).

Solar PV, wind, geothermal. EROI depends on Technology Metals
availability (Silver, Gallium, Indium, Neodymium, Lithium).

Key mechanism (Q47): Financial capital trapping — even with massive
financial capital from Liquid Funds, the RK4 engine prohibits
instantiation of solar/wind arrays if physical materials cannot be
supplied due to the 65% energy ceiling. Trapped capital either
remains unspent or is out-competed by lower-complexity systems.

Stock: technology_capital
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


_TECH_K0 = 1.0e10     # initial technology energy capital
_EROI_BASE = 15.0      # base EROI with full metals availability
_EROI_MIN = 3.0        # floor EROI when metals scarce
_DEPRECIATION = 0.04   # annual depreciation

# Technology Metals (Q47): Ag, Ga, In, Nd, Li
_METALS = ("silver", "gallium", "indium", "neodymium", "lithium")


class EnergyTechnologySector:
    """Technology energies (solar, wind, geothermal) with metals dependency.

    Stock: technology_capital
    Reads: industrial_output, supply_multiplier_technology,
           tech_metals_availability
    Writes: technology_capital, technology_output, technology_eroi,
            energy_demand_technology, tech_metals_demand
    """

    name = "energy_technology"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_capital: float = _TECH_K0,
        eroi_base: float = _EROI_BASE,
        eroi_min: float = _EROI_MIN,
    ) -> None:
        self.initial_capital = initial_capital
        self.eroi_base = eroi_base
        self.eroi_min = eroi_min

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "technology_capital": Quantity(
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
        tk = stocks["technology_capital"].magnitude
        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        supply_mult = inputs.get(
            "supply_multiplier_technology", Quantity(1.0, "dimensionless")
        ).magnitude

        # Technology metals availability (0.0-1.0, 1.0 = fully available)
        metals_avail = inputs.get(
            "tech_metals_availability", Quantity(1.0, "dimensionless")
        ).magnitude

        # EROI depends on metals availability
        eroi = self.eroi_min + (self.eroi_base - self.eroi_min) * metals_avail

        # Output constrained by supply multiplier AND metals
        output = tk * (eroi / 30.0) * supply_mult * metals_avail

        # Technology metals demand broadcast (for CentralRegistrar)
        tech_metals_demand = tk * 0.001  # proportional to installed capacity

        # Energy demand: self-consumption (energy cost of extraction = output/EROI)
        energy_demand = output / max(eroi, 1.0)

        # Investment: profitability-based allocation from IO
        profitability = eroi / 30.0 * metals_avail
        investment = io * 0.04 * profitability

        # Financial capital trapping (Q47):
        # If metals unavailable, investment allocated but cannot be deployed.
        # Trapped capital lowers effective Capital Output Ratio.
        trapped_capital = investment * max(0.0, 1.0 - metals_avail)
        effective_investment = investment - trapped_capital

        depreciation = tk * _DEPRECIATION

        return {
            "d_technology_capital": Quantity(
                effective_investment - depreciation, "capital_units"
            ),
            "technology_output": Quantity(output, "energy_units"),
            "technology_eroi": Quantity(eroi, "dimensionless"),
            "energy_demand_technology": Quantity(
                energy_demand, "energy_units"
            ),
            "tech_metals_demand": Quantity(
                tech_metals_demand, "dimensionless"
            ),
            "trapped_capital": Quantity(trapped_capital, "capital_units"),
            "tech_sector_investment": Quantity(investment, "capital_units"),
        }

    def declares_reads(self) -> list[str]:
        return [
            "industrial_output",
            "supply_multiplier_technology",
            "tech_metals_availability",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "technology_capital",
            "technology_output",
            "technology_eroi",
            "energy_demand_technology",
            "tech_metals_demand",
            "trapped_capital",
            "tech_sector_investment",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.DESIGN_CHOICE,
            "world7_alignment": WORLD7Alignment.APPROXIMATE,
            "approximations": [
                "Metals availability as single aggregate scalar",
                "Linear EROI-metals relationship",
                "Financial capital trapping simplified",
            ],
            "free_parameters": ["initial_capital", "eroi_base", "eroi_min"],
            "conservation_groups": [],
            "observables": [
                "technology_output",
                "technology_eroi",
                "trapped_capital",
            ],
            "unit_notes": (
                "Technology Metals: Ag, Ga, In, Nd, Li (Q47). "
                "energy_units, capital_units"
            ),
        }
