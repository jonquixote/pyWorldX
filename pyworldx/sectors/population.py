"""World3-03 Population sector (simplified 1-level aggregation).

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).

This is a simplified 1-level population model. The full W3-03 uses
4 age cohorts (0-14, 15-44, 45-64, 65+) with separate mortality
and fertility chains. This approximation keeps the simplified CBR/CDR
approach but uses correct W3-03 life-expectancy multiplier tables.

Key W3-03 corrections:
  - LMHS1/LMHS2 switching at t=1940 (was single blended table)
  - LMFT and LMPP tables already matched W3-03
  - Normal life expectancy = 28 years (LEN)

Note: The CBR and DFS tables are pyWorldX approximations.
W3-03 computes births from total_fertility * reproductive_pop,
which requires the 4-cohort structure. The simplified CBR(IOPC)
approach is augmented with fecundity multipliers from food shortage
and life expectancy to approximate the collapse-phase fertility drop
that W3-03 achieves via its 4-cohort reproductive mechanics.
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# ── W3-03 canonical tables ────────────────────────────────────────────

# Lifetime multiplier from food: LMFT(FPC/SFPC)
# MDL: matches W3-03
_LMFT_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_LMFT_Y = (0.0, 1.0, 1.43, 1.5, 1.5, 1.5)

# Lifetime multiplier from health services: LMHS1 (before 1940)
# MDL: LMHS1T  X = effective health services per capita
_LMHS1_X = (0.0, 20.0, 40.0, 60.0, 80.0, 100.0)
_LMHS1_Y = (1.0, 1.1, 1.4, 1.6, 1.7, 1.8)

# Lifetime multiplier from health services: LMHS2 (after 1940)
# MDL: LMHS2T  X = effective health services per capita
_LMHS2_X = (0.0, 20.0, 40.0, 60.0, 80.0, 100.0)
_LMHS2_Y = (1.0, 1.5, 1.9, 2.0, 2.0, 2.0)

# Lifetime multiplier from persistent pollution: LMPT(PPOLX)
# MDL: matches W3-03
_LMPP_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
_LMPP_Y = (1.0, 0.99, 0.97, 0.95, 0.90, 0.85, 0.75, 0.65, 0.55, 0.40, 0.20)

# Crude birth rate from IOPC (pyWorldX approximation — not in W3-03)
_CBR_X = (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0, 1600.0)
_CBR_Y = (0.04, 0.035, 0.030, 0.025, 0.020, 0.017, 0.015, 0.014, 0.013)

# Fecundity multiplier from food (pyWorldX approximation).
# In W3-03, malnutrition affects fecundity via the reproductive fraction
# and mortality shifting away from childbearing ages. This simplified table
# approximates: when FPC < SFPC, fewer women can sustain pregnancy.
# At FPC/SFPC=0 fecundity=0, at 0.5 it's 0.5, at 1.0+ it's 1.0.
_FMF_X = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0)
_FMF_Y = (0.0, 0.2, 0.5, 0.8, 1.0, 1.0, 1.0)

# Fecundity multiplier from life expectancy (pyWorldX approximation).
# In W3-03, lower LE means higher infant mortality and fewer women
# surviving to reproductive age. This proxy captures that: when LE is
# very low, effective fecundity drops sharply.
_FMLE_X = (20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)
_FMLE_Y = (0.2, 0.5, 0.75, 0.85, 0.95, 1.0, 1.0)

# ── W3-03 constants ───────────────────────────────────────────────────

_LEN = 28.0          # normal life expectancy (years)
_LMHS_SWITCH = 1940  # year to switch from LMHS1 to LMHS2
_POP0 = 1.65e9       # initial population (1900)
_SFPC_REF = 230.0    # subsistence food per capita for fecundity calc


class PopulationSector:
    """World3-03 population sector (simplified 1-level aggregation).

    Stocks: POP (total population)
    Reads:  food_per_capita, industrial_output, pollution_index,
            service_output_per_capita
    Writes: POP, birth_rate, death_rate, life_expectancy,
            industrial_output_per_capita
    """

    name = "population"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_population: float = _POP0

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"POP": Quantity(self.initial_population, "persons")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        pop = stocks["POP"].magnitude

        # Read inputs with defaults
        fpc = inputs.get(
            "food_per_capita", Quantity(1.0, "food_units_per_person")
        ).magnitude
        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        pi = inputs.get(
            "pollution_index", Quantity(0.0, "dimensionless")
        ).magnitude
        spc = inputs.get(
            "service_output_per_capita", Quantity(0.0, "service_output_units")
        ).magnitude

        # Industrial output per capita
        iopc = io / max(pop, 1.0)

        # ── Life expectancy multipliers ───────────────────────────────
        lmf = table_lookup(fpc, _LMFT_X, _LMFT_Y)

        # LMHS switching at 1940 (W3-03 structural feature)
        if t < _LMHS_SWITCH:
            lmhs = table_lookup(spc, _LMHS1_X, _LMHS1_Y)
        else:
            lmhs = table_lookup(spc, _LMHS2_X, _LMHS2_Y)

        lmpp = table_lookup(pi, _LMPP_X, _LMPP_Y)

        life_expectancy = _LEN * lmf * lmhs * lmpp

        # ── Crude death rate ──────────────────────────────────────────
        cdr = 1.0 / max(life_expectancy, 1.0)

        # ── Crude birth rate (pyWorldX approximation) ─────────────────
        cbr = table_lookup(iopc, _CBR_X, _CBR_Y)

        # Fecundity multipliers — approximate W3-03 reproductive mechanics
        fpc_ratio = fpc / _SFPC_REF
        fm_food = table_lookup(fpc_ratio, _FMF_X, _FMF_Y)
        fm_le = table_lookup(life_expectancy, _FMLE_X, _FMLE_Y)
        cbr *= fm_food * fm_le

        # Flows
        births = pop * cbr
        deaths = pop * cdr

        return {
            "d_POP": Quantity(births - deaths, "persons"),
            "birth_rate": Quantity(births, "persons_per_year"),
            "death_rate": Quantity(deaths, "persons_per_year"),
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
                "1-level population (W3-03 uses 4 age cohorts)",
                "CBR from IOPC table (W3-03 uses total fertility chain)",
                "LMHS1/LMHS2 switching at 1940 implemented",
            ],
            "free_parameters": ["initial_population"],
            "conservation_groups": ["population_mass"],
            "observables": [
                "POP",
                "birth_rate",
                "death_rate",
                "life_expectancy",
            ],
            "unit_notes": "persons, persons/year, years",
        }
