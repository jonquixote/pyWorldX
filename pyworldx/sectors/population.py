"""World3-03 Population sector.

Simplified 1-level population model based on World3-03:
  dPOP/dt = births - deaths
  births  = POP * cbr(food_per_capita, industrial_output_per_capita)
  deaths  = POP * cdr(life_expectancy)
  le      = f(pollution_index, food_per_capita, service_per_capita, crowding)

Uses table functions from Meadows et al. (1974/2004).
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── Table functions (World3-03 standard) ─────────────────────────────

# Lifetime multiplier from food (table LMFT)
_LMFT_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_LMFT_Y = (0.0, 1.0, 1.43, 1.5, 1.5, 1.5)

# Lifetime multiplier from health services (table LMHST)
_LMHS_X = (0.0, 20.0, 40.0, 60.0, 80.0, 100.0)
_LMHS_Y = (1.0, 1.4, 1.6, 1.8, 1.95, 2.0)

# Lifetime multiplier from persistent pollution (table LMPT)
_LMPP_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
_LMPP_Y = (1.0, 0.99, 0.97, 0.95, 0.90, 0.85, 0.75, 0.65, 0.55, 0.40, 0.20)

# Crude birth rate from industrial output per capita
_CBR_X = (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0, 1600.0)
_CBR_Y = (0.04, 0.035, 0.030, 0.025, 0.020, 0.017, 0.015, 0.014, 0.013)

# Desired family size from industrial output per capita
_DFS_X = (0.0, 200.0, 400.0, 600.0, 800.0)
_DFS_Y = (0.035, 0.025, 0.020, 0.015, 0.012)

# Normal life expectancy
_NORMAL_LE = 28.0  # years, base life expectancy


class PopulationSector:
    """World3-03 population sector (simplified 1-level aggregation).

    Stocks: POP (total population)
    Reads: food_per_capita, industrial_output, pollution_index,
           service_output_per_capita
    Writes: POP, birth_rate, death_rate, life_expectancy
    """

    name = "population"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_population: float = 1.65e9  # 1900 population

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"POP": Quantity(self.initial_population, "persons")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        pop = stocks["POP"].magnitude

        # Read inputs with defaults
        fpc = inputs.get(
            "food_per_capita", Quantity(1.0, "food_units_per_person")
        ).magnitude
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude
        spc = inputs.get(
            "service_output_per_capita", Quantity(0.0, "service_output_units")
        ).magnitude

        # Industrial output per capita
        iopc = io / max(pop, 1.0)

        # Life expectancy multipliers
        lmf = table_lookup(fpc, _LMFT_X, _LMFT_Y)
        lmhs = table_lookup(spc, _LMHS_X, _LMHS_Y)
        lmpp = table_lookup(pi, _LMPP_X, _LMPP_Y)

        life_expectancy = _NORMAL_LE * lmf * lmhs * lmpp

        # Crude death rate
        cdr = 1.0 / max(life_expectancy, 1.0)

        # Crude birth rate from iopc
        cbr = table_lookup(iopc, _CBR_X, _CBR_Y)

        # Flows
        births = pop * cbr
        deaths = pop * cdr

        return {
            "d_POP": Quantity(births - deaths, "persons"),
            "birth_rate": Quantity(births, "persons_per_year"),
            "death_rate": Quantity(deaths, "persons_per_year"),
            "life_expectancy": Quantity(life_expectancy, "years"),
            "industrial_output_per_capita": Quantity(
                iopc, "industrial_output_units"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "food_per_capita",
            "industrial_output",
            "pollution_index",
            "service_output_per_capita",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "POP",
            "birth_rate",
            "death_rate",
            "life_expectancy",
            "industrial_output_per_capita",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.REFERENCE_MATCHED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": ["1-level population aggregation"],
            "free_parameters": ["initial_population"],
            "conservation_groups": ["population_mass"],
            "observables": [
                "POP",
                "birth_rate",
                "death_rate",
                "life_expectancy",
            ],
            "unit_notes": "persons, persons/year, years",
        }
