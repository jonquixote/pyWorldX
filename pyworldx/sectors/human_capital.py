"""Human Capital sector (Phase 2 Task 1, from q64).

Stock: H (human capital index, 0-1 scale)
ODE: dH/dt = EducationRate - SkillDegradationRate - MortalityLoss
EducationRate = table_lookup(SOPC) * LaborForce
SkillDegradationRate = H * ln(2) / skill_half_life
MortalityLoss = H * DeathRate

Production coupling: Capital sector uses H as multiplier on labor
effectiveness.
"""

from __future__ import annotations

import numpy as np

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup


# Education rate as function of service output per capita
# Higher SOPC -> higher education investment
_EDU_RATE_X = (0.0, 50.0, 100.0, 200.0, 400.0, 800.0)
_EDU_RATE_Y = (0.0, 0.01, 0.024587, 0.06, 0.10, 0.15)

_SKILL_HALF_LIFE = 10.0  # years
_H0 = 0.3  # Pre-industrial baseline


class HumanCapitalSector:
    """Human Capital stock with education-driven accumulation.

    Stock: H (0-1 scale, initial=0.3)
    Reads: service_output_per_capita, death_rate, labor_force
    Writes: H, education_rate, skill_degradation_rate, mortality_loss,
            human_capital_multiplier
    """

    name = "human_capital"
    version = "1.0.0"
    timestep_hint: float | None = 0.015625

    def __init__(
        self,
        initial_h: float = _H0,
        skill_half_life: float = _SKILL_HALF_LIFE,
    ) -> None:
        self.initial_h = initial_h
        self.skill_half_life = skill_half_life

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"H": Quantity(self.initial_h, "dimensionless")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        H = stocks["H"].magnitude

        sopc = inputs.get(
            "service_output_per_capita",
            Quantity(87.0, "service_output_units"),
        ).magnitude
        
        pop = inputs.get("POP", Quantity(1.0, "persons")).magnitude
        deaths = inputs.get(
            "death_rate", Quantity(0.02 * pop, "persons_per_year"),
        ).magnitude
        
        fractional_death_rate = deaths / max(pop, 1.0)

        # Education rate from SOPC table lookup
        # SOPC already captures the scale of education investment per person;
        # no additional labor_force multiplication needed.
        edu_rate = table_lookup(sopc, _EDU_RATE_X, _EDU_RATE_Y)

        # Skill degradation (exponential decay with half-life)
        decay_rate = float(np.log(2)) / self.skill_half_life
        skill_degradation = H * decay_rate

        # Mortality loss
        mortality_loss = H * fractional_death_rate

        # Net change
        dH = edu_rate - skill_degradation - mortality_loss

        # Clamp H to [0, 1] via derivative bounding
        if H <= 0.0 and dH < 0:
            dH = 0.0
        elif H >= 1.0 and dH > 0:
            dH = 0.0

        # Human capital multiplier for production function (0-1 scale)
        h_multiplier = max(H, 0.0)

        return {
            "d_H": Quantity(dH, "dimensionless"),
            "education_rate": Quantity(edu_rate, "dimensionless"),
            "skill_degradation_rate": Quantity(
                skill_degradation, "per_year"
            ),
            "mortality_loss": Quantity(mortality_loss, "per_year"),
            "human_capital_multiplier": Quantity(
                h_multiplier, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "service_output_per_capita",
            "death_rate",
            "POP",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "H",
            "education_rate",
            "skill_degradation_rate",
            "mortality_loss",
            "human_capital_multiplier",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": (
                EquationSource.SYNTHESIZED_FROM_PRIMARY_LITERATURE
            ),
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Education rate proxied by SOPC table lookup",
                "Skill degradation as exponential decay with fixed half-life",
                "H bounded to [0, 1] via derivative clamping",
            ],
            "free_parameters": ["initial_h", "skill_half_life"],
            "conservation_groups": [],
            "observables": ["H", "human_capital_multiplier"],
            "unit_notes": "H is dimensionless index (0-1)",
        }
