"""World3-03 Adaptive Technology sector (Section 14 / 13.3).

Represents technology development that can modify resource usage
efficiency, pollution generation intensity, and agricultural yield.

In World3-03, technology is modeled as a delayed adaptive response
to perceived problems (resource scarcity, pollution, food shortage),
with implementation delays and costs drawn from industrial output.

  technology_index = f(perceived_problems, R&D_investment)
  resource_tech    = tech_multiplier on extraction efficiency
  pollution_tech   = tech_multiplier on pollution absorption
  agriculture_tech = tech_multiplier on land yield

This is a policy-lever sector: it amplifies or dampens feedback
loops in other sectors through technology multipliers.
"""

from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Technology development rate from R&D fraction (table)
_TECH_DEV_X = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
_TECH_DEV_Y = (0.0, 0.5, 1.0, 1.4, 1.7, 1.8)

# Technology cost multiplier (diminishing returns)
_TECH_COST_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_TECH_COST_Y = (1.0, 0.95, 0.85, 0.70, 0.55, 0.40)

# Resource technology effectiveness (table)
_RES_TECH_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_RES_TECH_Y = (1.0, 1.1, 1.25, 1.35, 1.4, 1.42)

# Pollution technology effectiveness (table)
_POL_TECH_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_POL_TECH_Y = (1.0, 1.2, 1.5, 1.75, 1.9, 1.95)

# Agriculture technology effectiveness (table)
_AG_TECH_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_AG_TECH_Y = (1.0, 1.15, 1.35, 1.5, 1.6, 1.65)


class AdaptiveTechnologySector:
    """World3-03 Adaptive Technology sector.

    Stock: TECH (technology index, dimensionless, initial=1.0)
    Reads: industrial_output, nr_fraction_remaining, pollution_index, food_per_capita
    Writes: TECH, resource_tech_mult, pollution_tech_mult, agriculture_tech_mult,
            tech_cost_fraction
    """

    name = "adaptive_technology"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_tech: float = 1.0
    rd_fraction_base: float = 0.02  # base R&D fraction of IO
    tech_delay: float = 20.0  # years — implementation delay
    tech_depreciation: float = 0.05  # 1/lifetime

    # Thresholds for perceived problems that trigger R&D
    nr_scarcity_threshold: float = 0.5  # fraction remaining
    pollution_concern_threshold: float = 1.0  # pollution index
    food_concern_threshold: float = 1.5  # food per capita

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"TECH": Quantity(self.initial_tech, "dimensionless")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        tech = stocks["TECH"].magnitude

        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        nr_frac = inputs.get(
            "nr_fraction_remaining", Quantity(1.0, "dimensionless")
        ).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude
        fpc = inputs.get(
            "food_per_capita", Quantity(1.0, "food_units_per_person")
        ).magnitude

        # Perceived problem intensity drives R&D effort
        resource_pressure = max(0.0, 1.0 - nr_frac / self.nr_scarcity_threshold)
        pollution_pressure = max(0.0, pi / self.pollution_concern_threshold - 1.0)
        food_pressure = max(0.0, 1.0 - fpc / self.food_concern_threshold)
        perceived_problems = (
            resource_pressure + pollution_pressure + food_pressure
        ) / 3.0

        # R&D fraction of industrial output
        rd_fraction = self.rd_fraction_base * (1.0 + perceived_problems)
        tech_dev_rate = table_lookup(rd_fraction, _TECH_DEV_X, _TECH_DEV_Y)

        # Technology development (with delay and depreciation)
        tech_investment = tech_dev_rate / max(self.tech_delay, 1.0)
        tech_depreciation = tech * self.tech_depreciation
        d_tech = tech_investment - tech_depreciation

        # Technology cost as fraction of IO (diminishing returns)
        tech_cost_fraction = table_lookup(tech, _TECH_COST_X, _TECH_COST_Y)
        tech_cost_fraction_out = rd_fraction * tech_cost_fraction

        # Technology multipliers applied to other sectors
        resource_tech_mult = table_lookup(tech, _RES_TECH_X, _RES_TECH_Y)
        pollution_tech_mult = table_lookup(tech, _POL_TECH_X, _POL_TECH_Y)
        agriculture_tech_mult = table_lookup(tech, _AG_TECH_X, _AG_TECH_Y)

        return {
            "d_TECH": Quantity(d_tech, "dimensionless"),
            "resource_tech_mult": Quantity(
                resource_tech_mult, "dimensionless"
            ),
            "pollution_tech_mult": Quantity(
                pollution_tech_mult, "dimensionless"
            ),
            "agriculture_tech_mult": Quantity(
                agriculture_tech_mult, "dimensionless"
            ),
            "tech_cost_fraction": Quantity(
                tech_cost_fraction_out, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "industrial_output",
            "nr_fraction_remaining",
            "pollution_index",
            "food_per_capita",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "TECH",
            "resource_tech_mult",
            "pollution_tech_mult",
            "agriculture_tech_mult",
            "tech_cost_fraction",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": "REFERENCE_MATCHED",
            "equation_source": "MEADOWS_SPEC",
            "world7_alignment": "NONE",
            "approximations": [
                "Aggregated technology index",
                "Fixed implementation delay",
                "Diminishing returns via table functions",
            ],
            "free_parameters": [
                "rd_fraction_base",
                "tech_delay",
                "tech_depreciation",
                "nr_scarcity_threshold",
                "pollution_concern_threshold",
                "food_concern_threshold",
            ],
            "conservation_groups": [],
            "observables": [
                "TECH",
                "resource_tech_mult",
                "pollution_tech_mult",
                "agriculture_tech_mult",
                "tech_cost_fraction",
            ],
            "unit_notes": "dimensionless multipliers",
        }
