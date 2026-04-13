"""Adaptive Technology sector (pyWorldX extension).

NOTE: This sector is a pyWorldX extension. It is NOT part of the
canonical World3-03 model. In W3-03, technology is implemented as
three separate embedded stocks:
  - Resource Conservation Technology (RCT) in the Resource sector
  - Persistent Pollution Technology (PPT) in the Pollution sector
  - Land Yield Technology (LYT) in the Agriculture sector
Each activates at POLICY_YEAR with its own change rate and SMOOTH3 delay.

This unified sector provides a single technology index that modulates
all three domains. It activates only when t >= POLICY_YEAR (default 4000,
meaning inactive in the base run).
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Technology development rate from R&D fraction
_TECH_DEV_X = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
_TECH_DEV_Y = (0.0, 0.5, 1.0, 1.4, 1.7, 1.8)

# Technology cost multiplier (diminishing returns)
_TECH_COST_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_TECH_COST_Y = (1.0, 0.95, 0.85, 0.70, 0.55, 0.40)

# Resource technology effectiveness
_RES_TECH_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_RES_TECH_Y = (1.0, 1.1, 1.25, 1.35, 1.4, 1.42)

# Pollution technology effectiveness
_POL_TECH_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_POL_TECH_Y = (1.0, 1.2, 1.5, 1.75, 1.9, 1.95)

# Agriculture technology effectiveness
_AG_TECH_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_AG_TECH_Y = (1.0, 1.15, 1.35, 1.5, 1.6, 1.65)

_POLICY_YEAR = 4000  # default: inactive in base run


class AdaptiveTechnologySector:
    """Adaptive Technology sector (pyWorldX extension, not in W3-03).

    Stock: TECH (technology index, dimensionless, initial=1.0)
    Reads: industrial_output, nr_fraction_remaining, pollution_index, food_per_capita
    Writes: TECH, resource_tech_mult, pollution_tech_mult, agriculture_tech_mult,
            tech_cost_fraction

    Before POLICY_YEAR, all multipliers output 1.0 (no effect).
    """

    name = "adaptive_technology"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_tech: float = 1.0
    rd_fraction_base: float = 0.02
    tech_delay: float = 20.0
    tech_depreciation: float = 0.05
    policy_year: float = _POLICY_YEAR

    # Thresholds for perceived problems
    nr_scarcity_threshold: float = 0.5
    pollution_concern_threshold: float = 1.0
    food_concern_threshold: float = 1.5

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

        # Before policy year: all outputs are inert (1.0)
        if t < self.policy_year:
            return {
                "d_TECH": Quantity(0.0, "dimensionless"),
                "resource_tech_mult": Quantity(1.0, "dimensionless"),
                "pollution_tech_mult": Quantity(1.0, "dimensionless"),
                "agriculture_tech_mult": Quantity(1.0, "dimensionless"),
                "tech_cost_fraction": Quantity(0.0, "dimensionless"),
            }

        _io = inputs.get(
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

        # Perceived problem intensity drives R&D
        resource_pressure = max(0.0, 1.0 - nr_frac / self.nr_scarcity_threshold)
        pollution_pressure = max(0.0, pi / self.pollution_concern_threshold - 1.0)
        food_pressure = max(0.0, 1.0 - fpc / self.food_concern_threshold)
        perceived_problems = (
            resource_pressure + pollution_pressure + food_pressure
        ) / 3.0

        rd_fraction = self.rd_fraction_base * (1.0 + perceived_problems)
        tech_dev_rate = table_lookup(rd_fraction, _TECH_DEV_X, _TECH_DEV_Y)

        tech_investment = tech_dev_rate / max(self.tech_delay, 1.0)
        tech_dep = tech * self.tech_depreciation
        d_tech = tech_investment - tech_dep

        tech_cost_fraction = table_lookup(tech, _TECH_COST_X, _TECH_COST_Y)
        tech_cost_out = rd_fraction * tech_cost_fraction

        resource_tech_mult = table_lookup(tech, _RES_TECH_X, _RES_TECH_Y)
        pollution_tech_mult = table_lookup(tech, _POL_TECH_X, _POL_TECH_Y)
        agriculture_tech_mult = table_lookup(tech, _AG_TECH_X, _AG_TECH_Y)

        return {
            "d_TECH": Quantity(d_tech, "dimensionless"),
            "resource_tech_mult": Quantity(resource_tech_mult, "dimensionless"),
            "pollution_tech_mult": Quantity(pollution_tech_mult, "dimensionless"),
            "agriculture_tech_mult": Quantity(agriculture_tech_mult, "dimensionless"),
            "tech_cost_fraction": Quantity(tech_cost_out, "dimensionless"),
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
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.EMPIRICAL_FIT,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Unified technology index (W3-03 uses 3 separate stocks: RCT, PPT, LYT)",
                "Inactive before POLICY_YEAR (default 4000 = base run)",
                "Fixed implementation delay",
                "Diminishing returns via table functions",
            ],
            "free_parameters": [
                "rd_fraction_base",
                "tech_delay",
                "tech_depreciation",
                "policy_year",
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
