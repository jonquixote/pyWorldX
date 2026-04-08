"""World3-03 Capital sector.

Two capital stocks (industrial and service) with investment and
depreciation flows driven by industrial output allocation.

  dIC/dt = ic_investment - ic_depreciation
  dSC/dt = sc_investment - sc_depreciation
  industrial_output = icor_adjusted * IC
  service_output = scor * SC
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Fraction of IO allocated to investment (table FIOAI)
_FIOAI_X = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
_FIOAI_Y = (0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30)

# Fraction of IO to services (table FIOAS)
_FIOAS_X = (0.0, 0.5, 1.0, 1.5, 2.0)
_FIOAS_Y = (0.30, 0.25, 0.22, 0.20, 0.18)

# ICOR multiplier from pollution (table)
_ICOR_PP_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0)
_ICOR_PP_Y = (1.0, 0.95, 0.85, 0.70, 0.50, 0.30)


class CapitalSector:
    """World3-03 Capital sector.

    Stocks: IC (industrial capital), SC (service capital)
    Reads: extraction_rate, pollution_index, POP, pollution_efficiency
    Writes: IC, SC, industrial_output, service_output, service_output_per_capita
    """

    name = "capital"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters (World3-03)
    initial_ic: float = 2.1e11  # industrial capital ($/1900)
    initial_sc: float = 1.44e11  # service capital
    icor: float = 3.0  # industrial capital-output ratio (years)
    scor: float = 1.0  # service capital-output ratio (years)
    ic_depreciation_rate: float = 0.05  # 1/average_lifetime (20 yrs)
    sc_depreciation_rate: float = 0.05

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "IC": Quantity(self.initial_ic, "capital_units"),
            "SC": Quantity(self.initial_sc, "capital_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        ic = stocks["IC"].magnitude
        sc = stocks["SC"].magnitude

        # Read inputs
        _er = inputs.get(
            "extraction_rate", Quantity(1.0, "resource_units")
        ).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        pe = inputs.get(
            "pollution_efficiency", Quantity(1.0, "dimensionless")
        ).magnitude

        # ICOR adjustment for pollution
        icor_mult = table_lookup(pi, _ICOR_PP_X, _ICOR_PP_Y)

        # Industrial output = IC / ICOR * pollution_efficiency * icor_mult
        effective_icor = self.icor / max(icor_mult * pe, 0.01)
        industrial_output = ic / effective_icor

        # Service output
        service_output = sc / self.scor
        spc = service_output / max(pop, 1.0)

        # Food allocation fraction (simplified — sent to agriculture)
        fpc_indicator = industrial_output / max(pop, 1.0)
        fioai = table_lookup(fpc_indicator / 200.0, _FIOAI_X, _FIOAI_Y)
        fioas = table_lookup(fpc_indicator / 200.0, _FIOAS_X, _FIOAS_Y)

        # Investment flows
        ic_investment = industrial_output * fioai
        sc_investment = industrial_output * fioas
        ic_depreciation = ic * self.ic_depreciation_rate
        sc_depreciation = sc * self.sc_depreciation_rate

        return {
            "d_IC": Quantity(ic_investment - ic_depreciation, "capital_units"),
            "d_SC": Quantity(sc_investment - sc_depreciation, "capital_units"),
            "industrial_output": Quantity(
                industrial_output, "industrial_output_units"
            ),
            "service_output": Quantity(service_output, "service_output_units"),
            "service_output_per_capita": Quantity(
                spc, "service_output_units"
            ),
            "frac_io_to_industry": Quantity(fioai, "dimensionless"),
            "frac_io_to_services": Quantity(fioas, "dimensionless"),
        }

    def declares_reads(self) -> list[str]:
        return [
            "extraction_rate",
            "pollution_index",
            "POP",
            "pollution_efficiency",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "IC",
            "SC",
            "industrial_output",
            "service_output",
            "service_output_per_capita",
            "frac_io_to_industry",
            "frac_io_to_services",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        """Capital<->Pollution algebraic loop (pollution_efficiency ↔ industrial_output)."""
        return [
            {
                "name": "capital_pollution_loop",
                "variables": [
                    "industrial_output",
                    "pollution_index",
                    "pollution_efficiency",
                ],
                "scope": "cross_sector",
                "solver": "fixed_point",
                "tol": 1e-10,
                "max_iter": 100,
            }
        ]

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.REFERENCE_MATCHED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": ["simplified ICOR table"],
            "free_parameters": ["icor", "scor", "ic_depreciation_rate"],
            "conservation_groups": [],
            "observables": ["IC", "SC", "industrial_output", "service_output"],
            "unit_notes": "capital_units, industrial_output_units",
        }
