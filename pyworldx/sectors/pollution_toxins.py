"""Micro-Toxin Pollution Module (Phase 1 Task 4).

Endocrine disruptors, POPs, heavy metals. Uses 111.8-year 3rd-order
cascaded ODE delay. Drives health/mortality/fertility effects.

Dynamic split (not fixed fraction): Independent sector-specific
intensity coefficients per industrial activity. As Green Capital
expands: GHG inflow declines BUT Toxin inflow RISES (rare earth
extraction/processing for solar/wind/EV).

Stocks: toxin_s1, toxin_s2, toxin_s3 (3-stage cascade delay)
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


_TOXIN0 = 1.0          # initial toxin index
_PPTD = 111.8          # persistent pollution transmission delay (Nebel 2024)
_AI_EWASTE_INTENSITY = 3.5e-4  # AI e-waste intensity (Q55)


class PollutionToxinModule:
    """Micro-toxin pollution module — 3rd-order cascaded delay.

    Stocks: toxin_s1, toxin_s2, toxin_s3 (3-stage cascade with PPTD/3)
    Reads: industrial_output, technology_output
    Writes: toxin_s1, toxin_s2, toxin_s3, toxin_index,
            toxin_health_multiplier, toxin_fertility_multiplier
    """

    name = "pollution_toxins"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_toxin: float = _TOXIN0,
        pptd: float = _PPTD,
    ) -> None:
        self.initial_toxin = initial_toxin
        self.pptd = pptd

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        stage_init = self.initial_toxin / 3.0
        return {
            "toxin_s1": Quantity(stage_init, "pollution_units"),
            "toxin_s2": Quantity(stage_init, "pollution_units"),
            "toxin_s3": Quantity(stage_init, "pollution_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        s1 = stocks["toxin_s1"].magnitude
        s2 = stocks["toxin_s2"].magnitude
        s3 = stocks["toxin_s3"].magnitude

        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        tech_output = inputs.get(
            "technology_output", Quantity(0.0, "energy_units")
        ).magnitude

        # Dynamic split: toxin intensity rises WITH green capital (Q55)
        # "Decarbonization scales faster than material circularity
        #  (bounded by thermodynamics) → material toxicity ultimately
        #  dominates the long-lived pollution stock"
        industrial_toxins = io * 0.001 * 1e-11  # base industrial toxicity
        tech_toxins = tech_output * 0.01 * 1e-11  # rare earth processing toxicity

        total_inflow = industrial_toxins + tech_toxins

        # 3rd-order cascaded delay (3 stages, each with delay = PPTD/3)
        stage_delay = self.pptd / 3.0

        d_s1 = (total_inflow - s1) / max(stage_delay, 1e-6)
        d_s2 = (s1 - s2) / max(stage_delay, 1e-6)
        d_s3 = (s2 - s3) / max(stage_delay, 1e-6)

        # Toxin index = output of the 3rd stage
        toxin_index = s3

        # Health effects: toxin_index drives mortality and fertility
        # Mortality multiplier: increases with toxin exposure
        health_mult = 1.0 + max(toxin_index - 1.0, 0.0) * 0.1

        # Fertility multiplier: decreases with toxin exposure (endocrine disruption)
        fertility_mult = max(1.0 - max(toxin_index - 1.0, 0.0) * 0.05, 0.5)

        return {
            "d_toxin_s1": Quantity(d_s1, "pollution_units"),
            "d_toxin_s2": Quantity(d_s2, "pollution_units"),
            "d_toxin_s3": Quantity(d_s3, "pollution_units"),
            "toxin_index": Quantity(toxin_index, "pollution_units"),
            "toxin_health_multiplier": Quantity(
                health_mult, "dimensionless"
            ),
            "toxin_fertility_multiplier": Quantity(
                fertility_mult, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "technology_output"]

    def declares_writes(self) -> list[str]:
        return [
            "toxin_s1",
            "toxin_s2",
            "toxin_s3",
            "toxin_index",
            "toxin_health_multiplier",
            "toxin_fertility_multiplier",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.DESIGN_CHOICE,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Aggregate toxin index (not individual pollutant tracking)",
                "Linear health/fertility response to toxin index",
                "Dynamic intensity coefficients simplified",
            ],
            "free_parameters": ["initial_toxin", "pptd"],
            "conservation_groups": [],
            "observables": [
                "toxin_index",
                "toxin_health_multiplier",
                "toxin_fertility_multiplier",
            ],
            "unit_notes": (
                "3rd-order cascaded delay at 111.8 years (Nebel 2024). "
                "Toxin sources: industrial processes + rare earth extraction. "
                "pollution_units"
            ),
        }
