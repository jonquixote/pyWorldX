"""World3-03 Agriculture sector.

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).

Stocks: AL (arable land), LFERT (land fertility)
Flows:  land development, land erosion, land urbanization
        land fertility degradation, land fertility regeneration

  food = AL * LY * LFH * (1 - PL)
  LY   = LFERT * LYMC(AIPH) * LYMAP(IO/IO70)
  AIPH = IO * FIOAA / AL

Key W3-03 corrections:
  - LYMC expanded to full 26-point table
  - FIOAA corrected (reaches 0 at FPC/SFPC=2.0)
  - Food equation includes LFH=0.7 and PL=0.1
  - Land fertility as separate stock
  - LYMAP replaces invented LYPM table
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── W3-03 canonical tables ────────────────────────────────────────────

# Land yield multiplier from capital: LYMC(AIPH)
# MDL: LYMC#104  X = agricultural input per hectare ($/ha/yr)
# Full 26-point table from wrld3-03.mdl
_LYMC_X = (
    0.0, 40.0, 80.0, 120.0, 160.0, 200.0, 240.0, 280.0, 320.0, 360.0,
    400.0, 440.0, 480.0, 520.0, 560.0, 600.0, 640.0, 680.0, 720.0, 760.0,
    800.0, 840.0, 880.0, 920.0, 960.0, 1000.0,
)
_LYMC_Y = (
    1.0, 3.0, 4.5, 5.0, 5.3, 5.6, 5.9, 6.1, 6.35, 6.6,
    6.9, 7.2, 7.4, 7.6, 7.8, 8.0, 8.2, 8.4, 8.6, 8.8,
    9.0, 9.2, 9.4, 9.6, 9.8, 10.0,
)

# Fraction of IO to agriculture: FIOAA1(FPC/SFPC)
# MDL: FIOAA1  X = food per capita / subsistence FPC
_FIOAA_X = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)
_FIOAA_Y = (0.4, 0.2, 0.1, 0.025, 0.0, 0.0)

# Land yield multiplier from air pollution: LYMAP1(IO/IO70)
# MDL: LYMAP1#106  X = pollution proxy (IO relative to 1970)
_LYMAP1_X = (0.0, 10.0, 20.0, 30.0)
_LYMAP1_Y = (1.0, 1.0, 0.7, 0.4)

# Land life multiplier from land yield: LLMY1(LY/ILF)
# MDL: LLMY1#112  X = land yield / inherent land fertility
_LLMY1_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
_LLMY1_Y = (1.2, 1.0, 0.63, 0.36, 0.16, 0.055, 0.04, 0.025, 0.015, 0.01)

# ── W3-03 constants ───────────────────────────────────────────────────

_AL0 = 0.9e9         # initial arable land (hectares, 1900)
_PAL = 3.2e9          # potentially arable land total
_LFERT0 = 600.0       # initial land fertility (veg equiv kg/ha/yr)
_LFH = 0.7            # land fraction harvested
_PL = 0.1             # processing loss fraction
_IO70 = 7.9e11        # industrial output in 1970 (reference)
_SFPC = 230.0         # subsistence food per capita
_ILF = 600.0          # inherent land fertility (for LLMY normalization)
_ALLN = 6000.0        # average life of land (years, normal)
_UILDT = 10.0         # urban-industrial land development time
_UILPC = 0.005        # urban-industrial land per capita (ha)


class AgricultureSector:
    """World3-03 Agriculture sector.

    Stocks: AL (arable land), LFERT (land fertility)
    Reads:  industrial_output, POP, pollution_index
    Writes: AL, LFERT, food, food_per_capita, land_yield, frac_io_to_agriculture
    """

    name = "agriculture"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_arable_land: float = _AL0
    potential_arable_land: float = _PAL
    initial_land_fertility: float = _LFERT0
    land_development_rate: float = 0.005
    sfpc: float = _SFPC

    # Internal state for SMOOTH2 on FPC (2-stage cascade, matches W3-03)
    _smooth_fpc_s1: float = _SFPC
    _smooth_fpc_s2: float = _SFPC

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "AL": Quantity(self.initial_arable_land, "hectares"),
            "LFERT": Quantity(self.initial_land_fertility, "veg_equiv_kg_per_ha_yr"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        al = stocks["AL"].magnitude
        lfert = stocks["LFERT"].magnitude

        # Read inputs
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude

        iopc = io / max(pop, 1.0)

        # ── Smoothed FPC for allocation decisions ────────────────────
        # W3-03 uses SMOOTH2 on food ratio (~2yr delay).
        # SMOOTH2 = two cascaded first-order delays, each with tau/2.
        smooth_tau = 2.0  # smoothing time constant (years)
        half_tau = smooth_tau / 2.0
        alpha = min(ctx.master_dt / half_tau, 1.0)

        # ── Agricultural input allocation ─────────────────────────────
        fpc_ratio = self._smooth_fpc_s2 / self.sfpc
        fioaa = table_lookup(fpc_ratio, _FIOAA_X, _FIOAA_Y)

        # Agricultural input
        ag_input = io * fioaa
        aiph = ag_input / max(al, 1.0)

        # ── Land yield ────────────────────────────────────────────────
        lymc = table_lookup(aiph, _LYMC_X, _LYMC_Y)

        # Air pollution effect on yield
        io_ratio = io / _IO70
        lymap = table_lookup(io_ratio, _LYMAP1_X, _LYMAP1_Y)

        # Land yield = fertility * capital multiplier * pollution effect
        land_yield = lfert * lymc * lymap

        # ── Food production ───────────────────────────────────────────
        food = al * land_yield * _LFH * (1.0 - _PL)
        fpc_raw = food / max(pop, 1.0)

        # Update SMOOTH2 cascade with this step's actual FPC
        self._smooth_fpc_s1 += alpha * (fpc_raw - self._smooth_fpc_s1)
        self._smooth_fpc_s2 += alpha * (self._smooth_fpc_s1 - self._smooth_fpc_s2)
        fpc = self._smooth_fpc_s2

        # ── Land dynamics ─────────────────────────────────────────────
        remaining = max(self.potential_arable_land - al, 0.0)
        land_dev = remaining * self.land_development_rate * min(
            io / max(io + 1e9, 1.0), 1.0
        )

        # Land erosion via land life: LLMY determines land lifetime
        ly_ratio = land_yield / _ILF
        llmy = table_lookup(ly_ratio, _LLMY1_X, _LLMY1_Y)
        land_life = _ALLN * llmy
        land_erosion = al / max(land_life, 1.0)

        # Urban-industrial land use
        land_urban = pop * _UILPC / _UILDT * min(iopc / 400.0, 2.0)
        land_urban = min(land_urban, al * 0.01)  # cap at 1% of AL per year

        d_al = land_dev - land_erosion - land_urban

        # ── Land fertility dynamics ───────────────────────────────────
        # Degradation from pollution (simplified: use pollution index as proxy)
        lfdr = lfert * 0.1 * max(pi - 1.0, 0.0) / max(pi + 10.0, 1.0)

        # Regeneration toward inherent fertility
        lfr = (_ILF - lfert) * 0.02 if lfert < _ILF else 0.0

        d_lfert = lfr - lfdr

        return {
            "d_AL": Quantity(d_al, "hectares"),
            "d_LFERT": Quantity(d_lfert, "veg_equiv_kg_per_ha_yr"),
            "food": Quantity(food, "food_units"),
            "food_per_capita": Quantity(fpc, "food_units_per_person"),
            "land_yield": Quantity(land_yield, "kg_per_hectare_year"),
            "frac_io_to_agriculture": Quantity(fioaa, "dimensionless"),
            "aiph": Quantity(aiph, "agricultural_inputs_per_hectare"),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "POP", "pollution_index", "food_per_capita"]

    def declares_writes(self) -> list[str]:
        return [
            "AL",
            "LFERT",
            "food",
            "food_per_capita",
            "land_yield",
            "frac_io_to_agriculture",
            "aiph",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EMPIRICALLY_ANCHORED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Land fertility degradation simplified from full LFDR chain",
                "DCPH (development cost) not modeled",
                "FALM (fraction of inputs to land maintenance) not modeled",
            ],
            "free_parameters": [
                "initial_arable_land",
                "potential_arable_land",
                "initial_land_fertility",
                "land_development_rate",
                "sfpc",
            ],
            "conservation_groups": [],
            "observables": [
                "AL",
                "LFERT",
                "food",
                "food_per_capita",
                "land_yield",
            ],
            "unit_notes": "hectares, food_units, kg/hectare/year",
        }
