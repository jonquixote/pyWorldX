"""World3-03 Non-Renewable Resources sector.

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).

Stocks: NR (nonrenewable resources)
Flows:  NRUR (nonrenewable resource usage rate)
Key auxiliaries: PCRUM, FCAOR, NRUF, NRFR

  dNR/dt  = -NRUR
  NRUR    = POP * PCRUM(IOPC) * NRUF
  NRFR    = NR / NRI
  FCAOR   = clip(FCAOR2, FCAOR1, t, FCAOR_SWITCH_TIME)(NRFR)

Resource Conservation Technology (RCT) is embedded here per W3-03.
In the base run (POLICY_YEAR=4000) it stays inert (NRUF=1).
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── W3-03 canonical tables ────────────────────────────────────────────

# Per-capita resource usage multiplier: PCRUM(IOPC)
# MDL: PCRUM#130.1  X=IOPC ($/person/year)
_PCRUM_X = (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0, 1600.0)
_PCRUM_Y = (0.0, 0.85, 2.6, 3.4, 3.8, 4.1, 4.4, 4.7, 5.0)

# Fraction of capital allocated to obtaining resources: FCAOR1(NRFR)
# MDL: FCAOR1#136.1  X=NR fraction remaining (0..1)
_FCAOR1_X = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_FCAOR1_Y = (1.0, 0.9, 0.7, 0.5, 0.2, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05)

# FCAOR2: post-policy-year table (more aggressive early conservation)
# MDL: FCAOR2#136.2
_FCAOR2_X = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_FCAOR2_Y = (1.0, 0.2, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05)

# ── W3-03 constants ───────────────────────────────────────────────────

_NRI_DEFAULT = 1.0e12       # initial NR stock (resource units)
_POLICY_YEAR = 4000         # technology policy year (inactive in base run)
_FCAOR_SWITCH_TIME = 4000   # FCAOR table switch time (inactive in base run)
_NRUF1 = 1.0               # NR usage factor before policy year


class ResourcesSector:
    """World3-03 Non-Renewable Resources sector.

    Stocks: NR (nonrenewable resource stock)
    Reads:  POP, industrial_output_per_capita
    Writes: NR, extraction_rate, nr_fraction_remaining, fcaor, nrur
    """

    name = "resources"
    version = "3.03"
    timestep_hint: float | None = 0.25  # sub-stepped at 4:1

    # Parameters
    initial_nr: float = _NRI_DEFAULT
    policy_year: float = _POLICY_YEAR
    fcaor_switch_time: float = _FCAOR_SWITCH_TIME

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"NR": Quantity(self.initial_nr, "resource_units")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        nr = stocks["NR"].magnitude

        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        iopc = inputs.get(
            "industrial_output_per_capita",
            Quantity(io / max(pop, 1.0), "industrial_output_units"),
        ).magnitude

        # Per-capita resource usage rate: PCRUM(IOPC)
        pcrum = table_lookup(iopc, _PCRUM_X, _PCRUM_Y)

        # NR usage factor (NRUF): 1.0 in base run, technology-driven after policy year
        # In base run POLICY_YEAR=4000, so NRUF=NRUF1=1.0 always
        if t >= self.policy_year:
            # Post-policy: NRUF2 would come from SMOOTH3(RCT, TDD)
            # Simplified: use 1.0 (full RCT system requires separate stock integration)
            nruf = _NRUF1
        else:
            nruf = _NRUF1

        # Technology efficiency: higher resource_tech_mult → less extraction per capita
        res_tech = inputs.get(
            "resource_tech_mult", Quantity(1.0, "dimensionless")
        ).magnitude
        res_tech = max(res_tech, 1e-6)

        # NR usage rate
        nrur = pop * pcrum * nruf / res_tech

        # Don't extract more than available
        nrur = min(nrur, max(nr, 0.0) / max(ctx.master_dt, 0.0625))

        # Fraction remaining
        nrfr = nr / self.initial_nr

        # FCAOR: fraction of capital allocated to obtaining resources
        if t >= self.fcaor_switch_time:
            fcaor = table_lookup(nrfr, _FCAOR2_X, _FCAOR2_Y)
        else:
            fcaor = table_lookup(nrfr, _FCAOR1_X, _FCAOR1_Y)

        return {
            "d_NR": Quantity(-nrur, "resource_units"),
            "extraction_rate": Quantity(nrur, "resource_units"),
            "nrur": Quantity(nrur, "resource_units"),
            "nr_fraction_remaining": Quantity(nrfr, "dimensionless"),
            "fcaor": Quantity(fcaor, "dimensionless"),
            "resource_use_factor": Quantity(fcaor, "dimensionless"),
        }

    def declares_reads(self) -> list[str]:
        return ["POP", "industrial_output", "industrial_output_per_capita", "resource_tech_mult"]

    def declares_writes(self) -> list[str]:
        return [
            "NR",
            "extraction_rate",
            "nrur",
            "nr_fraction_remaining",
            "fcaor",
            "resource_use_factor",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EMPIRICALLY_ANCHORED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "NRUF simplified (RCT stock not yet integrated as SMOOTH3)",
                "FCAOR1/FCAOR2 switching implemented",
            ],
            "free_parameters": ["initial_nr", "policy_year"],
            "conservation_groups": ["nonrenewable_resource_mass"],
            "observables": [
                "NR",
                "extraction_rate",
                "nrur",
                "nr_fraction_remaining",
                "fcaor",
            ],
            "unit_notes": "resource_units",
            "preferred_substep_integrator": "rk4",
        }
