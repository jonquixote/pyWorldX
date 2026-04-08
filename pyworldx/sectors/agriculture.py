"""World3-03 Agriculture sector.

Simplified food production model:
  dAL/dt = land_development - land_erosion - land_urbanization
  food = AL * land_yield
  food_per_capita = food / POP
  land_yield = f(industrial_input_to_ag, pollution)
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Land yield multiplier from industrial input (table LYMC)
_LYMC_X = (0.0, 40.0, 80.0, 120.0, 160.0, 200.0, 240.0, 280.0, 320.0)
_LYMC_Y = (1.0, 3.0, 4.5, 5.0, 5.3, 5.6, 5.8, 5.9, 5.95)

# Land yield multiplier from pollution (table LYPM)
_LYPM_X = (0.0, 10.0, 20.0, 30.0, 40.0)
_LYPM_Y = (1.0, 0.97, 0.90, 0.75, 0.50)

# Land erosion rate multiplier from land yield
_LERM_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_LERM_Y = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05)

# Fraction of IO to agriculture (table FIOAA)
_FIOAA_X = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)
_FIOAA_Y = (0.40, 0.30, 0.22, 0.15, 0.10, 0.08)


class AgricultureSector:
    """World3-03 Agriculture sector.

    Stocks: AL (arable land)
    Reads: industrial_output, POP, pollution_index
    Writes: AL, food, food_per_capita, land_yield
    """

    name = "agriculture"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_arable_land: float = 0.9e9  # hectares (1900)
    potential_arable_land: float = 3.2e9  # hectares
    base_land_yield: float = 600.0  # kg/hectare/year (vegetable equiv)
    land_development_rate: float = 0.005  # fraction of remaining/year
    land_urbanization_rate: float = 0.001  # fraction of AL/year

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"AL": Quantity(self.initial_arable_land, "hectares")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        al = stocks["AL"].magnitude

        # Read inputs
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude

        # Industrial input to agriculture
        iopc = io / max(pop, 1.0)
        fioaa = table_lookup(iopc / 200.0, _FIOAA_X, _FIOAA_Y)
        ag_input = io * fioaa
        ag_input_per_hectare = ag_input / max(al, 1.0)

        # Land yield with multipliers
        lymc = table_lookup(ag_input_per_hectare / 1e6, _LYMC_X, _LYMC_Y)
        lypm = table_lookup(pi, _LYPM_X, _LYPM_Y)
        land_yield = self.base_land_yield * lymc * lypm

        # Food production
        food = al * land_yield
        fpc = food / max(pop, 1.0)

        # Land dynamics
        remaining = max(self.potential_arable_land - al, 0.0)
        land_dev = remaining * self.land_development_rate * (io / max(io + 1e9, 1.0))
        land_yield_ratio = land_yield / max(self.base_land_yield, 1.0)
        erosion_rate = table_lookup(land_yield_ratio, _LERM_X, _LERM_Y)
        land_erosion = al * erosion_rate
        land_urban = al * self.land_urbanization_rate * min(iopc / 200.0, 2.0)

        d_al = land_dev - land_erosion - land_urban

        return {
            "d_AL": Quantity(d_al, "hectares"),
            "food": Quantity(food, "food_units"),
            "food_per_capita": Quantity(fpc, "food_units_per_person"),
            "land_yield": Quantity(land_yield, "kg_per_hectare_year"),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "POP", "pollution_index"]

    def declares_writes(self) -> list[str]:
        return ["AL", "food", "food_per_capita", "land_yield"]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.REFERENCE_MATCHED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": ["simplified land development"],
            "free_parameters": [
                "base_land_yield",
                "land_development_rate",
                "potential_arable_land",
            ],
            "conservation_groups": [],
            "observables": ["AL", "food", "food_per_capita", "land_yield"],
            "unit_notes": "hectares, food_units, kg/hectare/year",
        }
