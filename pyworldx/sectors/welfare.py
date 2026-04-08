"""World3-03 Welfare sector (Section 14 / 13.3).

Computes two composite indicators:
  - Human Welfare Index (HWI) — analog of UNDP HDI
  - Human Ecological Footprint (HEF) — analog of Global Footprint Network EF

These are purely observational aggregates. They have no stocks and
do not feed back into other sectors — they summarize model state
for validation against empirical welfare indicators.

HWI = f(life_expectancy, education_proxy, income_proxy)
HEF = f(industrial_output, food, pollution_index, arable_land, POP)
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Life expectancy contribution to HWI (table — normalized to [0,1])
_LE_HWI_X = (0.0, 20.0, 40.0, 60.0, 80.0, 100.0)
_LE_HWI_Y = (0.0, 0.2, 0.5, 0.75, 0.9, 1.0)

# Industrial output per capita contribution to HWI (income proxy)
_IOPC_HWI_X = (0.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0)
_IOPC_HWI_Y = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

# Education proxy from service output per capita
_SPC_EDU_X = (0.0, 50.0, 100.0, 200.0, 400.0, 800.0)
_SPC_EDU_Y = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

# Ecological footprint components
# Industrial footprint per unit output
_IND_EF_X = (0.0, 1e9, 5e9, 1e10, 5e10, 1e11)
_IND_EF_Y = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)

# Food footprint per capita
_FOOD_EF_X = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)
_FOOD_EF_Y = (0.0, 0.3, 0.5, 0.8, 1.0, 1.2)

# Pollution absorption footprint
_POL_EF_X = (0.0, 1.0, 5.0, 10.0, 20.0, 50.0)
_POL_EF_Y = (0.0, 0.2, 0.5, 0.8, 1.2, 2.0)


class WelfareSector:
    """World3-03 Welfare indicator sector.

    No stocks — pure auxiliary/observable computation.
    Reads: life_expectancy, industrial_output, service_output_per_capita,
           food_per_capita, pollution_index, POP, AL (arable land)
    Writes: human_welfare_index, ecological_footprint,
            hwi_life_exp_component, hwi_income_component, hwi_education_component
    """

    name = "welfare"
    version = "3.03"
    timestep_hint: float | None = None

    # HWI component weights (HDI-style geometric mean weights)
    w_life_exp: float = 1.0 / 3.0
    w_income: float = 1.0 / 3.0
    w_education: float = 1.0 / 3.0

    # Ecological footprint normalization
    ef_reference_pop: float = 1.0e9  # reference population for per-capita normalization

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        # No stocks — pure auxiliary sector
        return {}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        le = inputs.get(
            "life_expectancy", Quantity(28.0, "years")
        ).magnitude
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        spc = inputs.get(
            "service_output_per_capita", Quantity(0.0, "service_output_units")
        ).magnitude
        fpc = inputs.get(
            "food_per_capita", Quantity(1.0, "food_units_per_person")
        ).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude
        pop = inputs.get(
            "POP", Quantity(1.65e9, "persons")
        ).magnitude

        iopc = io / max(pop, 1.0)

        # ── Human Welfare Index (HDI analog) ────────────────────────
        le_component = table_lookup(le, _LE_HWI_X, _LE_HWI_Y)
        income_component = table_lookup(iopc, _IOPC_HWI_X, _IOPC_HWI_Y)
        education_component = table_lookup(spc, _SPC_EDU_X, _SPC_EDU_Y)

        # Geometric mean (HDI-style)
        le_c = max(le_component, 1e-10)
        inc_c = max(income_component, 1e-10)
        edu_c = max(education_component, 1e-10)
        hwi = (
            le_c ** self.w_life_exp
            * inc_c ** self.w_income
            * edu_c ** self.w_education
        )

        # ── Ecological Footprint ────────────────────────────────────
        ind_footprint = table_lookup(io, _IND_EF_X, _IND_EF_Y)
        food_footprint = table_lookup(fpc, _FOOD_EF_X, _FOOD_EF_Y)
        pol_footprint = table_lookup(pi, _POL_EF_X, _POL_EF_Y)

        # Per-capita ecological footprint
        ef_per_capita = ind_footprint + food_footprint + pol_footprint
        # Total EF normalized to reference
        ecological_footprint = ef_per_capita * (pop / self.ef_reference_pop)

        return {
            "human_welfare_index": Quantity(hwi, "dimensionless"),
            "ecological_footprint": Quantity(
                ecological_footprint, "dimensionless"
            ),
            "hwi_life_exp_component": Quantity(le_component, "dimensionless"),
            "hwi_income_component": Quantity(income_component, "dimensionless"),
            "hwi_education_component": Quantity(
                education_component, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "life_expectancy",
            "industrial_output",
            "service_output_per_capita",
            "food_per_capita",
            "pollution_index",
            "POP",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "human_welfare_index",
            "ecological_footprint",
            "hwi_life_exp_component",
            "hwi_income_component",
            "hwi_education_component",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.REFERENCE_MATCHED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "HDI-style geometric mean for HWI",
                "Education proxied by service output per capita",
                "Ecological footprint aggregation simplified",
            ],
            "free_parameters": [
                "w_life_exp",
                "w_income",
                "w_education",
                "ef_reference_pop",
            ],
            "conservation_groups": [],
            "observables": [
                "human_welfare_index",
                "ecological_footprint",
            ],
            "unit_notes": "dimensionless indices",
        }
