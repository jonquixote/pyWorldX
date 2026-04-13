"""World3-03 Capital sector.

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).

Stocks: IC (industrial capital), SC (service capital)
Flows:  IC investment/depreciation, SC investment/depreciation

  IO   = IC * (1 - FCAOR) * CUF / ICOR
  SO   = SC * CUF / SCOR
  FIOAI = 1 - FIOAA - FIOAS - FIOAC   (residual)

Key W3-03 corrections:
  - ALIC1 = 14 years  ->  depreciation = 1/14
  - IO includes (1-FCAOR) resource cost feedback
  - FIOAS table corrected to W3-03 values
  - FIOAI is a residual, not a separate table
  - FIOAC (consumption fraction) via ISOPC table
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── W3-03 canonical tables ────────────────────────────────────────────

# Fraction of IO to services: FIOAS1(SOPC/ISOPC)
# MDL: FIOAS1  X = SOPC/ISOPC ratio
_FIOAS_X = (0.0, 0.5, 1.0, 1.5, 2.0)
_FIOAS_Y = (0.3, 0.2, 0.1, 0.05, 0.0)

# Fraction of IO to agriculture: FIOAA1(FPC/SFPC)
# MDL: FIOAA1  X = food_per_capita / subsistence_fpc
_FIOAA_X = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)
_FIOAA_Y = (0.4, 0.2, 0.1, 0.025, 0.0, 0.0)

# Fraction of IO to consumption: FIOACV(IOPC/IOPC_DESIRED)
# MDL: FIOACV  (indicator autonomous consumption)
_FIOACV_X = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
_FIOACV_Y = (0.3, 0.32, 0.34, 0.36, 0.38, 0.43, 0.73, 0.77, 0.81, 0.82, 0.83)

# ── W3-03 constants ───────────────────────────────────────────────────

_IC0 = 2.1e11       # initial industrial capital (1900)
_SC0 = 1.44e11      # initial service capital (1900)
_ICOR1 = 3.0        # industrial capital-output ratio (years)
_SCOR1 = 1.0        # service capital-output ratio (years)
_ALIC1 = 14.0       # average life of industrial capital (years)
_ALSC1 = 20.0       # average life of service capital (years)
_CUF = 1.0          # capacity utilization fraction (simplified; full CUF needs jobs)
_SFPC = 230.0       # subsistence food per capita (kg veg equiv / person / year)
_ISOPC = 120.0      # indicated service output per capita reference


class CapitalSector:
    """World3-03 Capital sector.

    Stocks: IC (industrial capital), SC (service capital)
    Reads:  fcaor, POP, food_per_capita, service_output_per_capita
    Writes: IC, SC, industrial_output, industrial_output_per_capita,
            service_output, service_output_per_capita,
            frac_io_to_industry, frac_io_to_services, frac_io_to_agriculture
    """

    name = "capital"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters (W3-03)
    initial_ic: float = _IC0
    initial_sc: float = _SC0
    icor: float = _ICOR1
    scor: float = _SCOR1
    alic: float = _ALIC1
    alsc: float = _ALSC1

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
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        fcaor = inputs.get(
            "fcaor", Quantity(0.05, "dimensionless")
        ).magnitude
        fpc = inputs.get(
            "food_per_capita", Quantity(230.0, "food_units_per_person")
        ).magnitude
        # ── Industrial output ─────────────────────────────────────────
        # IO = IC * (1 - FCAOR) * CUF / ICOR
        io = ic * (1.0 - fcaor) * _CUF / self.icor
        iopc = io / max(pop, 1.0)

        # ── Service output ────────────────────────────────────────────
        so = sc * _CUF / self.scor
        sopc = so / max(pop, 1.0)

        # ── IO allocation fractions ───────────────────────────────────
        # FIOAA: agriculture allocation based on food adequacy
        fpc_ratio = fpc / _SFPC
        fioaa = table_lookup(fpc_ratio, _FIOAA_X, _FIOAA_Y)

        # FIOAS: services allocation based on service adequacy
        sopc_ratio = sopc / _ISOPC
        fioas = table_lookup(sopc_ratio, _FIOAS_X, _FIOAS_Y)

        # FIOAC: consumption allocation based on income level
        iopc_ratio = iopc / 400.0  # normalize to reference IOPC
        fioac = table_lookup(iopc_ratio, _FIOACV_X, _FIOACV_Y)

        # FIOAI: industrial investment is the residual
        fioai = max(1.0 - fioaa - fioas - fioac, 0.0)

        # ── Investment and depreciation flows ─────────────────────────
        ic_investment = io * fioai
        sc_investment = io * fioas
        ic_depreciation = ic / self.alic
        sc_depreciation = sc / self.alsc

        return {
            "d_IC": Quantity(ic_investment - ic_depreciation, "capital_units"),
            "d_SC": Quantity(sc_investment - sc_depreciation, "capital_units"),
            "industrial_output": Quantity(io, "industrial_output_units"),
            "industrial_output_per_capita": Quantity(
                iopc, "industrial_output_units"
            ),
            "service_output": Quantity(so, "service_output_units"),
            "service_output_per_capita": Quantity(sopc, "service_output_units"),
            "frac_io_to_industry": Quantity(fioai, "dimensionless"),
            "frac_io_to_services": Quantity(fioas, "dimensionless"),
            "frac_io_to_agriculture": Quantity(fioaa, "dimensionless"),
            "frac_io_to_consumption": Quantity(fioac, "dimensionless"),
        }

    def declares_reads(self) -> list[str]:
        return [
            "fcaor",
            "POP",
            "food_per_capita",
            "service_output_per_capita",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "IC",
            "SC",
            "industrial_output",
            "industrial_output_per_capita",
            "service_output",
            "service_output_per_capita",
            "frac_io_to_industry",
            "frac_io_to_services",
            "frac_io_to_agriculture",
            "frac_io_to_consumption",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
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
            "validation_status": ValidationStatus.EMPIRICALLY_ANCHORED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "CUF fixed at 1.0 (full CUF requires jobs subsector)",
                "FIOAC table simplified normalization",
            ],
            "free_parameters": ["icor", "scor", "alic", "alsc"],
            "conservation_groups": [],
            "observables": [
                "IC",
                "SC",
                "industrial_output",
                "industrial_output_per_capita",
                "service_output",
                "service_output_per_capita",
            ],
            "unit_notes": "capital_units, industrial_output_units",
        }
