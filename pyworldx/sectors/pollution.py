"""World3-03 Persistent Pollution sector.

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).

Stocks: PPOL (persistent pollution)
Flows:  PPAPR (pollution appearance rate), PPASR (pollution assimilation rate)
Key auxiliaries: PPOLX (pollution index), AHLM, AHL

  dPPOL/dt = PPAPR - PPASR
  PPASR    = PPOL / (AHL70 * AHLM(PPOLX) * 1.4)
  PPOLX    = PPOL / PPOL70

Pollution generation uses the PCRUM chain from resources, not IO directly:
  PPGIO = PCRUM * POP * FRPM * IMEF * IMTI
  PPGAO = AIPH * AL * FIPM * AMTI
  PPGR  = (PPGIO + PPGAO) * PPGF
  PPAPR = DELAY3(PPGR, PPTD)  -- 20-year transmission delay

In this simplified implementation, the DELAY3 is approximated by a
3-stage pipeline (three cascaded first-order delays).
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── W3-03 canonical tables ────────────────────────────────────────────

# Absorption half-life multiplier: AHLM(PPOLX)
# MDL: AHLM#145.1  X=pollution index (PPOL/PPOL70)
_AHLM_X = (1.0, 251.0, 501.0, 751.0, 1001.0)
_AHLM_Y = (1.0, 11.0, 21.0, 31.0, 41.0)

# Life-expectancy multiplier from pollution (LMPT) -- used by population
# but kept here for cross-reference: same as in population.py
_LMPP_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
_LMPP_Y = (1.0, 0.99, 0.97, 0.95, 0.90, 0.85, 0.75, 0.65, 0.55, 0.40, 0.20)

# ── W3-03 constants ───────────────────────────────────────────────────

_PPOL70 = 1.36e8    # persistent pollution in 1970 (reference level)
_AHL70 = 1.5        # absorption half-life in 1970 (years)
_FRPM = 0.02        # fraction of resources as pollution material
_IMEF = 0.1         # industrial material emissions factor
_IMTI = 10.0        # industrial material toxicity index
_AMTI = 1.0         # agricultural material toxicity index
_FIPM = 0.001       # fraction of inputs as pollution material (ag)
_PPTD = 111.8       # persistent pollution transmission delay (years); Nebel et al. 2024 (DOI: 10.1111/jiec.13442)
_PPGF1 = 1.0        # persistent pollution generation factor (pre-policy)
_AHL_FACTOR = 1.4   # absorption rate divisor factor from MDL
_PPOL0 = 2.5e7      # initial PPOL in 1900


class PollutionSector:
    """World3-03 Persistent Pollution sector.

    Stocks: PPOL (persistent pollution),
            PPDL1/PPDL2/PPDL3 (3-stage delay pipeline for DELAY3)
    Reads:  POP, industrial_output, food, AL, nrur
    Writes: PPOL, pollution_index, pollution_generation, pollution_efficiency
    """

    name = "pollution"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_ppol: float = _PPOL0
    ppol_1970: float = _PPOL70
    ahl70: float = _AHL70
    pptd: float = _PPTD

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        # DELAY3 is approximated as 3 cascaded first-order lags.
        # Each stage delay = PPTD/3. Initial values = initial generation rate.
        # We start with small initial generation to avoid zero-divide.
        init_gen = 0.0
        return {
            "PPOL": Quantity(self.initial_ppol, "pollution_units"),
            "PPDL1": Quantity(init_gen, "pollution_units"),
            "PPDL2": Quantity(init_gen, "pollution_units"),
            "PPDL3": Quantity(init_gen, "pollution_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        ppol = stocks["PPOL"].magnitude
        dl1 = stocks["PPDL1"].magnitude
        dl2 = stocks["PPDL2"].magnitude
        dl3 = stocks["PPDL3"].magnitude

        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        food = inputs.get("food", Quantity(0.0, "food_units")).magnitude
        al = inputs.get("AL", Quantity(0.9e9, "hectares")).magnitude

        # Read PCRUM-based resource usage if available, else estimate
        pcrum_pop = inputs.get(
            "nrur", Quantity(pop * 1.0, "resource_units")
        ).magnitude

        # ── Pollution generation ──────────────────────────────────────
        # Industrial: uses resource usage as proxy (PCRUM * POP already = NRUR)
        ppgio = pcrum_pop * _FRPM * _IMEF * _IMTI

        # Agricultural: uses ag input per hectare proxy
        # AIPH = total ag input / AL; proxy from food/AL
        aiph = food / max(al, 1.0)
        ppgao = aiph * al * _FIPM * _AMTI

        # Total generation rate (before delay)
        ppgf = _PPGF1  # base run: no technology change
        ppgr = (ppgio + ppgao) * ppgf
        pollution_generation = ppgr

        # ── DELAY3 pipeline (3-stage cascade) ─────────────────────────
        stage_delay = max(self.pptd / 3.0, 0.1)
        d_dl1 = (ppgr - dl1) / stage_delay
        d_dl2 = (dl1 - dl2) / stage_delay
        d_dl3 = (dl2 - dl3) / stage_delay
        # Output of DELAY3 = output of 3rd stage
        ppapr = dl3 / stage_delay  # appearance rate

        # ── Pollution index ───────────────────────────────────────────
        ppolx = ppol / self.ppol_1970

        # ── Absorption ────────────────────────────────────────────────
        ahlm = table_lookup(ppolx, _AHLM_X, _AHLM_Y)
        ahl = self.ahl70 * ahlm
        ppasr = ppol / (ahl * _AHL_FACTOR)

        # ── Pollution effect on life expectancy (for population sector)
        pe = table_lookup(ppolx, _LMPP_X, _LMPP_Y)

        return {
            "d_PPOL": Quantity(ppapr - ppasr, "pollution_units"),
            "d_PPDL1": Quantity(d_dl1, "pollution_units"),
            "d_PPDL2": Quantity(d_dl2, "pollution_units"),
            "d_PPDL3": Quantity(d_dl3, "pollution_units"),
            "pollution_index": Quantity(ppolx, "dimensionless"),
            "pollution_efficiency": Quantity(pe, "dimensionless"),
            "pollution_generation": Quantity(pollution_generation, "pollution_units"),
        }

    def declares_reads(self) -> list[str]:
        return ["POP", "industrial_output", "food", "AL", "nrur"]

    def declares_writes(self) -> list[str]:
        return [
            "PPOL",
            "PPDL1",
            "PPDL2",
            "PPDL3",
            "pollution_index",
            "pollution_efficiency",
            "pollution_generation",
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
                "DELAY3 as 3-stage cascade",
                "PPGF fixed at 1.0 (no pollution technology in base run)",
                "Agricultural pollution from food/AL proxy",
            ],
            "free_parameters": [
                "initial_ppol",
                "ppol_1970",
                "ahl70",
                "pptd",
            ],
            "conservation_groups": [],
            "observables": [
                "PPOL",
                "pollution_index",
                "pollution_efficiency",
                "pollution_generation",
            ],
            "unit_notes": "pollution_units, dimensionless",
        }
