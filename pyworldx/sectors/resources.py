"""World3-03 Non-Renewable Resources sector.

  dNR/dt = -extraction_rate
  extraction_rate = POP * pcnr_use * f(industrial_output_per_capita)
  nr_fraction_remaining = NR / NR_initial
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Per-capita resource usage multiplier from iopc
# X-axis scaled to match model's actual iopc values (~42 at t=0)
_PCRUM_X = (0.0, 10.0, 20.0, 40.0, 60.0, 80.0, 100.0, 150.0)
_PCRUM_Y = (0.0, 0.85, 2.6, 4.4, 5.4, 6.2, 6.8, 7.0)

# Resource fraction cost effect on capital
_FCAOR_X = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_FCAOR_Y = (1.0, 0.9, 0.7, 0.5, 0.3, 0.15, 0.08, 0.05, 0.03, 0.02, 0.01)


class ResourcesSector:
    """World3-03 Non-Renewable Resources sector.

    Stocks: NR (nonrenewable resource stock)
    Reads: POP, industrial_output
    Writes: NR, extraction_rate, nr_fraction_remaining, resource_use_factor
    """

    name = "resources"
    version = "3.03"
    timestep_hint: float | None = 0.25  # sub-stepped at 4:1

    # Parameters
    initial_nr: float = 1.0e12  # resource units (1900)
    pcnr_use_base: float = 1.0  # per-capita resource usage base

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

        iopc = io / max(pop, 1.0)

        # Per-capita resource usage rate
        pcrum = table_lookup(iopc, _PCRUM_X, _PCRUM_Y)
        extraction_rate = pop * pcrum * self.pcnr_use_base

        # Don't extract more than available
        extraction_rate = min(extraction_rate, max(nr, 0.0) * 10.0)

        # Fraction remaining
        nrfr = nr / self.initial_nr

        # Resource cost factor (fed back to capital sector)
        resource_use_factor = table_lookup(nrfr, _FCAOR_X, _FCAOR_Y)

        return {
            "d_NR": Quantity(-extraction_rate, "resource_units"),
            "extraction_rate": Quantity(extraction_rate, "resource_units"),
            "nr_fraction_remaining": Quantity(nrfr, "dimensionless"),
            "resource_use_factor": Quantity(
                resource_use_factor, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return ["POP", "industrial_output"]

    def declares_writes(self) -> list[str]:
        return [
            "NR",
            "extraction_rate",
            "nr_fraction_remaining",
            "resource_use_factor",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.REFERENCE_MATCHED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": ["simplified extraction table"],
            "free_parameters": ["initial_nr", "pcnr_use_base"],
            "conservation_groups": ["nonrenewable_resource_mass"],
            "observables": [
                "NR",
                "extraction_rate",
                "nr_fraction_remaining",
            ],
            "unit_notes": "resource_units",
            "preferred_substep_integrator": "rk4",
        }
