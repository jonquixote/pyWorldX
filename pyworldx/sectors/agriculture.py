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

# Fraction of IO to agriculture: FIOAA1(FPC/IFPC)
# MDL: FIOAA1  X = food per capita / indicated food per capita
_FIOAA_X = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)
_FIOAA_Y = (0.4, 0.2, 0.1, 0.025, 0.0, 0.0)

# Indicated food per capita: IFPC(IOPC) — rising food expectation with development
# MDL: IFPC1T / IFPC2T (identical in Standard Run)
_IFPC_X = (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0, 1600.0)
_IFPC_Y = (230.0, 480.0, 690.0, 850.0, 970.0, 1070.0, 1150.0, 1210.0, 1250.0)

# Land yield multiplier from air pollution: LYMAP1(IO/IO70)
# MDL: LYMAP1#106  X = pollution proxy (IO relative to 1970)
_LYMAP1_X = (0.0, 10.0, 20.0, 30.0)
_LYMAP1_Y = (1.0, 1.0, 0.7, 0.4)

# Land life multiplier from land yield: LLMY1(LY/ILF)
# MDL: LLMY1#112  X = land yield / inherent land fertility
_LLMY1_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
_LLMY1_Y = (1.2, 1.0, 0.63, 0.36, 0.16, 0.055, 0.04, 0.025, 0.015, 0.01)

# Fraction of inputs to land development: FIALD(MPLD/MPAI)
# MDL: FIALDT  X = marginal productivity ratio (land/ag-input)
# Canonical W3-03 values (Meadows spec / pyworld3)
_FIALD_X = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
_FIALD_Y = (0.0, 0.05, 0.15, 0.30, 0.50, 0.70, 0.85, 0.95, 1.0)

# Development cost per hectare: DCPH(fraction of PAL developed)
# MDL: DCPHT  X = 1 - AL/PAL  (difficulty rises as more land is developed)
_DCPH_X = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_DCPH_Y = (100000.0, 7400.0, 5200.0, 3500.0, 2400.0, 1500.0,
           750.0, 300.0, 150.0, 75.0, 50.0)

# Fraction of agricultural inputs to land maintenance: FALM(PFR)
# MDL: FALMT  X = perceived food ratio (FPC/SFPC, smoothed)
_FALM_X = (0.0, 1.0, 2.0, 3.0, 4.0)
_FALM_Y = (0.0, 0.04, 0.07, 0.09, 0.10)

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
_ALAI = 2.0           # average lifetime of agricultural inputs (years)


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

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        # CAI: 1st-order delay of cai_input = TAI*(1-FIALD). Initialized
        # to 1900 equilibrium IO*FIOAA(1)*(1-FIALD(MPLD/MPAI≈1))≈IO*0.1*0.5.
        cai_init = 0.0665e12 * 0.1 * 0.5
        return {
            "AL": Quantity(self.initial_arable_land, "hectares"),
            "LFERT": Quantity(self.initial_land_fertility, "veg_equiv_kg_per_ha_yr"),
            "CAI": Quantity(cai_init, "agricultural_input_units"),
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
        cai = stocks["CAI"].magnitude

        # Read inputs
        io = inputs.get(
            "industrial_output", Quantity(6.65e10, "industrial_output_units")
        ).magnitude
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude

        iopc = io / max(pop, 1.0)

        # ── Agricultural input allocation (W3-03: FPC/IFPC, IFPC is dynamic) ─
        # Use last-step raw FPC; guard against bootstrap-zero from engine seed.
        prev_fpc_q = inputs.get("food_per_capita")
        prev_fpc = prev_fpc_q.magnitude if prev_fpc_q is not None else self.sfpc
        if prev_fpc <= 1.0:
            prev_fpc = self.sfpc
        ifpc = table_lookup(iopc, _IFPC_X, _IFPC_Y)
        fpc_ratio_alloc = prev_fpc / max(ifpc, 1.0)
        fioaa = table_lookup(fpc_ratio_alloc, _FIOAA_X, _FIOAA_Y)

        # ── FIALD split (land dev vs agricultural inputs) ─────────────
        # AIPH from current smoothed CAI (FALM applied below). Use CAI for
        # AIPH calc in marginal-productivity step (productive share only).
        falm_x = prev_fpc / self.sfpc
        falm = table_lookup(falm_x, _FALM_X, _FALM_Y)
        ai_productive = cai * (1.0 - falm)
        aiph = ai_productive / max(al, 1.0)

        # MLYMC = d(LYMC)/d(AIPH) — numerical derivative of LYMC curve.
        _mlymc_delta = 1.0
        lymc_base = table_lookup(aiph, _LYMC_X, _LYMC_Y)
        lymc_perturbed = table_lookup(
            aiph + _mlymc_delta, _LYMC_X, _LYMC_Y
        )
        mlymc = (lymc_perturbed - lymc_base) / _mlymc_delta

        # MPAI: marginal productivity of agricultural inputs = LFERT * MLYMC
        mpai = max(lfert * mlymc, 1e-10)

        # MPLD: marginal productivity of land development = LY / DCPH
        dev_frac = 1.0 - al / max(self.potential_arable_land, 1.0)
        dev_frac = min(max(dev_frac, 0.0), 1.0)
        dcph = table_lookup(dev_frac, _DCPH_X, _DCPH_Y)
        ly_now = lfert * lymc_base  # pollution factor applied later for yield,
                                    # but MPLD uses base yield
        mpld = ly_now / max(dcph, 1e-6)

        fiald = table_lookup(mpld / mpai, _FIALD_X, _FIALD_Y)

        # TAI and CAI dynamics
        tai = io * fioaa
        cai_input = tai * (1.0 - fiald)
        d_cai = (cai_input - cai) / _ALAI

        # ── Land yield ────────────────────────────────────────────────
        lymc = lymc_base

        # Air pollution effect on yield
        io_ratio = io / _IO70
        lymap = table_lookup(io_ratio, _LYMAP1_X, _LYMAP1_Y)

        # Land yield = fertility * capital multiplier * pollution effect
        land_yield = lfert * lymc * lymap

        # ── Food production ───────────────────────────────────────────
        food = al * land_yield * _LFH * (1.0 - _PL)
        fpc = food / max(pop, 1.0)

        # ── Land dynamics ─────────────────────────────────────────────
        # LDR = TAI * FIALD / DCPH (W3-03 canonical)
        land_dev = tai * fiald / max(dcph, 1e-6)

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
            "d_CAI": Quantity(d_cai, "agricultural_input_units"),
            "food": Quantity(food, "food_units"),
            "food_per_capita": Quantity(fpc, "food_units_per_person"),
            "land_yield": Quantity(land_yield, "kg_per_hectare_year"),
            "frac_io_to_agriculture": Quantity(fioaa, "dimensionless"),
            "aiph": Quantity(aiph, "agricultural_inputs_per_hectare"),
            "fiald": Quantity(fiald, "dimensionless"),
            "falm": Quantity(falm, "dimensionless"),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "POP", "pollution_index", "food_per_capita"]

    def declares_writes(self) -> list[str]:
        return [
            "AL",
            "LFERT",
            "CAI",
            "food",
            "food_per_capita",
            "land_yield",
            "frac_io_to_agriculture",
            "aiph",
            "fiald",
            "falm",
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
