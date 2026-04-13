"""World3-03 Population sector — full 4-cohort implementation.

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).

Stocks: P1 (0-14), P2 (15-44), P3 (45-64), P4 (65+)
Flows:  births, deaths (d1-d4), maturation (mat1-mat3)

  POP  = P1 + P2 + P3 + P4
  dP1/dt = births - d1 - mat1
  dP2/dt = mat1 - d2 - mat2
  dP3/dt = mat2 - d3 - mat3
  dP4/dt = mat3 - d4

  births = TF * P2 * 0.5 / RLT
  mat_i  = P_i * (1 - M_i) / cohort_span
  d_i    = P_i * M_i

  LE = LEN * LMF * LMHS * LMP * LMC
  TF = min(MTF, MTF*(1-FCE) + DTF*FCE)
  DTF = DCFS * CMPLE
  DCFS = DCFSN * FRSN * SFSN   (or 2.0 after ZPGT)
  MTF = MTFN * FM

All table functions match the canonical pyworld3 reference implementation
(cvanwynsberghe/pyworld3), which is a faithful translation of wrld3-03.mdl.
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── W3-03 canonical tables ────────────────────────────────────────────

# Age-specific mortality tables: M_i(LE)
# MDL: M1#22, M2#28, M3#34, M4#40
_M1_X = (20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_M1_Y = (0.0567, 0.0366, 0.0243, 0.0155, 0.0082, 0.0023, 0.001)

_M2_X = (20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_M2_Y = (0.0266, 0.0171, 0.011, 0.0065, 0.004, 0.0016, 0.0008)

_M3_X = (20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_M3_Y = (0.0562, 0.0373, 0.0252, 0.0171, 0.0118, 0.0083, 0.006)

_M4_X = (20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_M4_Y = (0.13, 0.11, 0.09, 0.07, 0.06, 0.05, 0.04)

# Lifetime multiplier from food: LMF(FPC/SFPC)
_LMF_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_LMF_Y = (0.0, 1.0, 1.2, 1.3, 1.35, 1.4)

# Lifetime multiplier from health services: LMHS1 (before IPHST)
_LMHS1_X = (0.0, 20.0, 40.0, 60.0, 80.0, 100.0)
_LMHS1_Y = (1.0, 1.1, 1.4, 1.6, 1.7, 1.8)

# Lifetime multiplier from health services: LMHS2 (after IPHST)
_LMHS2_X = (0.0, 20.0, 40.0, 60.0, 80.0, 100.0)
_LMHS2_Y = (1.0, 1.4, 1.6, 1.8, 1.95, 2.0)

# Lifetime multiplier from persistent pollution: LMP(PPOLX)
_LMP_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
_LMP_Y = (1.0, 0.99, 0.97, 0.95, 0.90, 0.85, 0.75, 0.65, 0.55, 0.40, 0.20)

# Fraction of population urban: FPU(POP)
_FPU_X = (0.0, 2e9, 4e9, 6e9, 8e9, 10e9, 12e9, 14e9, 16e9)
_FPU_Y = (0.0, 0.2, 0.4, 0.5, 0.58, 0.65, 0.72, 0.78, 0.80)

# Crowding multiplier from industrialization: CMI(IOPC)
_CMI_X = (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0, 1600.0)
_CMI_Y = (0.5, 0.05, -0.1, -0.08, -0.02, 0.05, 0.1, 0.15, 0.2)

# Health services allocations per capita: HSAPC(SOPC)
_HSAPC_X = (0.0, 250.0, 500.0, 750.0, 1000.0, 1250.0, 1500.0, 1750.0, 2000.0)
_HSAPC_Y = (0.0, 20.0, 50.0, 95.0, 140.0, 175.0, 200.0, 220.0, 230.0)

# Fecundity multiplier: FM(LE)
_FM_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_FM_Y = (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.05, 1.1)

# Compensatory multiplier from perceived life expectancy: CMPLE(PLE)
_CMPLE_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_CMPLE_Y = (3.0, 2.1, 1.6, 1.4, 1.3, 1.2, 1.1, 1.05, 1.0)

# Social family size norm: SFSN(DIOPC)
_SFSN_X = (0.0, 200.0, 400.0, 600.0, 800.0)
_SFSN_Y = (1.25, 1.0, 0.9, 0.8, 0.75)

# Family response to social norm: FRSN(FIE)
_FRSN_X = (-0.2, -0.1, 0.0, 0.1, 0.2)
_FRSN_Y = (0.5, 0.6, 0.7, 0.85, 1.0)

# Fertility control effectiveness (to clip): FCE(FCFPC)
_FCE_X = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
_FCE_Y = (0.75, 0.85, 0.9, 0.95, 0.98, 0.99, 1.0)

# Fraction of services allocated to fertility control: FSAFC(NFC)
_FSAFC_X = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)
_FSAFC_Y = (0.0, 0.005, 0.015, 0.025, 0.03, 0.035)

# ── W3-03 constants ───────────────────────────────────────────────────

_LEN = 28.0          # normal life expectancy (years)
_IPHST = 1940        # implementation of health service time (calendar year)
_P1I = 6.5e8         # initial P1 (0-14) in 1900
_P2I = 7.0e8         # initial P2 (15-44) in 1900
_P3I = 1.9e8         # initial P3 (45-64) in 1900
_P4I = 6.0e7         # initial P4 (65+) in 1900
_SFPC = 230.0        # subsistence food per capita
_MTFN = 12.0         # maximum total fertility normal
_DCFSN = 4.0         # desired completed family size normal
_RLT = 30.0          # reproductive lifetime (years)
_ZPGT = 4000         # zero population growth time (inactive in base run)
_FCEST = 4000        # fertility control effectiveness set time
_LPD = 20.0          # lifetime perception delay (years)
_SAD = 20.0          # social adjustment delay (years)
_IEAT = 3.0          # income expectation averaging time (years)
_HSID = 20.0         # health services impact delay (years)
_PET = 4000          # population equilibrium time (inactive in base run)


class PopulationSector:
    """World3-03 population sector — full 4-cohort implementation.

    Stocks: P1, P2, P3, P4 (age cohorts)
    Reads:  food_per_capita, industrial_output, pollution_index,
            service_output_per_capita
    Writes: POP, P1, P2, P3, P4, birth_rate, death_rate,
            life_expectancy, industrial_output_per_capita
    """

    name = "population"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters (overridable for presets)
    initial_population: float = _P1I + _P2I + _P3I + _P4I  # backward compat

    # Internal smooth states are now managed as integrated stocks 
    # to be compatible with RK4 integration inside the engine.

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        pop0 = _P1I + _P2I + _P3I + _P4I
        # Initial guess inputs for deriving the initial smooth values
        iopc0 = 0.0665e12 / pop0  # Roughly 1900 IO / POP
        spc0 = 87.0               # Roughly 1900 service output per capita
        hsapc0 = table_lookup(spc0, _HSAPC_X, _HSAPC_Y)
        fcapc0 = 0.0              # Starts at 0
        
        return {
            "P1": Quantity(_P1I, "persons"),
            "P2": Quantity(_P2I, "persons"),
            "P3": Quantity(_P3I, "persons"),
            "P4": Quantity(_P4I, "persons"),
            "POP": Quantity(pop0, "persons"),
            "PLE": Quantity(_LEN, "years"),
            "EHSPC": Quantity(hsapc0, "dollars_per_person"),
            "AIOPC": Quantity(iopc0, "industrial_output_units"),
            "DIOPC": Quantity(iopc0, "industrial_output_units"),
            "FCFPC": Quantity(fcapc0, "dollars_per_person"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        p1 = stocks["P1"].magnitude
        p2 = stocks["P2"].magnitude
        p3 = stocks["P3"].magnitude
        p4 = stocks["P4"].magnitude
        pop = p1 + p2 + p3 + p4
        
        # Extract smooth state stocks
        ple = stocks["PLE"].magnitude
        ehspc = stocks["EHSPC"].magnitude
        aiopc = stocks["AIOPC"].magnitude
        diopc = stocks["DIOPC"].magnitude
        fcfpc = stocks["FCFPC"].magnitude

        # Read inputs with defaults
        fpc = inputs.get(
            "food_per_capita", Quantity(230.0, "food_units_per_person")
        ).magnitude
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude
        sopc = inputs.get(
            "service_output_per_capita", Quantity(0.0, "service_output_units")
        ).magnitude

        iopc = io / max(pop, 1.0)
        dt = ctx.master_dt

        # ── Life expectancy ───────────────────────────────────────────
        # LMF: lifetime multiplier from food
        lmf = table_lookup(fpc / _SFPC, _LMF_X, _LMF_Y)

        # HSAPC: health services allocations per capita
        hsapc = table_lookup(sopc, _HSAPC_X, _HSAPC_Y)

        # EHSPC: effective HSAPC (smoothed with HSID delay)
        d_ehspc = (hsapc - ehspc) / max(_HSID, 1e-6)

        # LMHS: switching at IPHST (1940 calendar = t=40 sim time)
        iphst_sim = _IPHST - 1900
        if t < iphst_sim:
            lmhs = table_lookup(ehspc, _LMHS1_X, _LMHS1_Y)
        else:
            lmhs = table_lookup(ehspc, _LMHS2_X, _LMHS2_Y)

        # LMP: lifetime multiplier from pollution
        lmp = table_lookup(pi, _LMP_X, _LMP_Y)

        # LMC: lifetime multiplier from crowding
        fpu = table_lookup(pop, _FPU_X, _FPU_Y)
        cmi = table_lookup(iopc, _CMI_X, _CMI_Y)
        lmc = 1.0 - cmi * fpu

        # Life expectancy
        life_expectancy = _LEN * lmf * lmhs * lmp * lmc
        life_expectancy = max(life_expectancy, 1.0)

        # ── Age-specific mortality ────────────────────────────────────
        m1 = table_lookup(life_expectancy, _M1_X, _M1_Y)
        m2 = table_lookup(life_expectancy, _M2_X, _M2_Y)
        m3 = table_lookup(life_expectancy, _M3_X, _M3_Y)
        m4 = table_lookup(life_expectancy, _M4_X, _M4_Y)

        # Deaths
        d1 = p1 * m1
        d2 = p2 * m2
        d3 = p3 * m3
        d4 = p4 * m4
        total_deaths = d1 + d2 + d3 + d4

        # ── Maturation flows ──────────────────────────────────────────
        mat1 = p1 * (1.0 - m1) / 15.0   # 0-14 → 15-44
        mat2 = p2 * (1.0 - m2) / 30.0   # 15-44 → 45-64
        mat3 = p3 * (1.0 - m3) / 20.0   # 45-64 → 65+

        # ── Fertility chain ───────────────────────────────────────────

        # Perceived life expectancy: PLE = DLINF3(LE, LPD)
        d_ple = (life_expectancy - ple) / max(_LPD, 1e-6)

        # CMPLE: compensatory multiplier from perceived LE
        cmple = table_lookup(ple, _CMPLE_X, _CMPLE_Y)

        # FM: fecundity multiplier from LE
        fm = table_lookup(life_expectancy, _FM_X, _FM_Y)

        # MTF: maximum total fertility
        mtf = _MTFN * fm

        # Average IOPC (SMOOTH with IEAT)
        d_aiopc = (iopc - aiopc) / max(_IEAT, 1e-6)

        # FIE: family income expectation
        fie = (iopc - aiopc) / max(aiopc, 1.0)

        # Delayed IOPC (DLINF3 with SAD)
        d_diopc = (iopc - diopc) / max(_SAD, 1e-6)

        # SFSN: social family size norm
        sfsn = table_lookup(diopc, _SFSN_X, _SFSN_Y)

        # FRSN: family response to social norm
        frsn = table_lookup(fie, _FRSN_X, _FRSN_Y)

        # DCFS: desired completed family size
        # After ZPGT (=4000 in base run), DCFS = 2.0
        calendar_year = t + 1900
        if calendar_year >= _ZPGT:
            dcfs = 2.0
        else:
            dcfs = _DCFSN * frsn * sfsn

        # DTF: desired total fertility
        dtf = dcfs * cmple

        # NFC: need for fertility control
        nfc = max(mtf / max(dtf, 0.01) - 1.0, 0.0)

        # FSAFC: fraction of services allocated to fertility control
        fsafc = table_lookup(nfc, _FSAFC_X, _FSAFC_Y)

        # FCAPC: fertility control allocations per capita
        fcapc = fsafc * sopc

        # FCFPC: fertility control facilities per capita (delayed)
        d_fcfpc = (fcapc - fcfpc) / max(_HSID, 1e-6)

        # FCE: fertility control effectiveness
        if calendar_year >= _FCEST:
            fce = 1.0
        else:
            fce = table_lookup(fcfpc, _FCE_X, _FCE_Y)

        # TF: total fertility
        tf = min(mtf, mtf * (1.0 - fce) + dtf * fce)

        # ── Births ────────────────────────────────────────────────────
        # births = TF * P2 * 0.5 / RLT
        # (P2 * 0.5 approximates women in reproductive age)
        if calendar_year >= _PET:
            births = total_deaths  # equilibrium
        else:
            births = tf * p2 * 0.5 / _RLT

        # ── Stock derivatives ─────────────────────────────────────────
        d_p1 = births - d1 - mat1
        d_p2 = mat1 - d2 - mat2
        d_p3 = mat2 - d3 - mat3
        d_p4 = mat3 - d4
        d_pop = d_p1 + d_p2 + d_p3 + d_p4

        return {
            "d_P1": Quantity(d_p1, "persons"),
            "d_P2": Quantity(d_p2, "persons"),
            "d_P3": Quantity(d_p3, "persons"),
            "d_P4": Quantity(d_p4, "persons"),
            "d_POP": Quantity(d_pop, "persons"),
            "d_PLE": Quantity(d_ple, "years"),
            "d_EHSPC": Quantity(d_ehspc, "dollars_per_person"),
            "d_AIOPC": Quantity(d_aiopc, "industrial_output_units"),
            "d_DIOPC": Quantity(d_diopc, "industrial_output_units"),
            "d_FCFPC": Quantity(d_fcfpc, "dollars_per_person"),
            # Aggregate for downstream sectors
            "POP": Quantity(pop, "persons"),
            "birth_rate": Quantity(births, "persons_per_year"),
            "death_rate": Quantity(total_deaths, "persons_per_year"),
            "life_expectancy": Quantity(life_expectancy, "years"),
            "industrial_output_per_capita": Quantity(
                iopc, "industrial_output_units"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "food_per_capita",
            "industrial_output",
            "pollution_index",
            "service_output_per_capita",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "P1",
            "P2",
            "P3",
            "P4",
            "POP",
            "birth_rate",
            "death_rate",
            "life_expectancy",
            "industrial_output_per_capita",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EMPIRICALLY_ANCHORED,
            "equation_source": EquationSource.MEADOWS_SPEC,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "DLINF3 delays simplified to 1st-order smooth",
                "LMC crowding multiplier included",
            ],
            "free_parameters": ["initial_population"],
            "conservation_groups": ["population_mass"],
            "observables": [
                "POP",
                "P1",
                "P2",
                "P3",
                "P4",
                "PLE",
                "EHSPC",
                "AIOPC",
                "DIOPC",
                "FCFPC",
                "birth_rate",
                "death_rate",
                "life_expectancy",
            ],
            "unit_notes": "persons, persons/year, years",
        }
