"""SEIR epidemiological module (Phase 2 Task 5, from q58, q59, q64).

Parallel SEIR disease state matrix integrated with the 4-cohort population
model. Each cohort has its own S, E, I, R compartments (16 total state vars).

Cohorts:
  C1: 0-14 years
  C2: 15-44 years (working age)
  C3: 45-64 years (working age)
  C4: 65+ years (elderly, non-working)

ODEs per cohort c:
  dS_c/dt = births_c - beta * contact_rate_c * S_c * I_total/N - deaths_S_c
  dE_c/dt = beta * contact_rate_c * S_c * I_total/N - sigma * E_c - deaths_E_c
  dI_c/dt = sigma * E_c - gamma * I_c - deaths_I_c
  dR_c/dt = gamma * I_c - deaths_R_c

Parameters (fixed to literature values):
  sigma = 1 / incubation_period  (~1/5.2 days -> ~68.5/year)
  gamma = 1 / infectious_period  (~1/10 days -> ~36.5/year)
  R0_base = basic reproduction number (~2.5-3.0 for typical respiratory virus)
  beta = R0_base * gamma  (derived from R0 = beta/gamma)

Temperature coupling:
  beta(T) = beta_base * (1 + temp_sensitivity * max(T, 0))
  Higher temperature anomaly increases transmission (vector-borne diseases).

Labor Force Multiplier:
  LFM = (S_C2 + R_C2 + S_C3 + R_C3) / (total_C2 + total_C3)
  Broadcast to shared state as 'labor_force_multiplier'.
  Capital sector reads LFM and adjusts effective labor.

Post-infection productivity penalty:
  Recovered individuals have reduced productivity for some period.
  Modeled as: effective_R = R * (1 - productivity_penalty)
  where productivity_penalty decays over recovery_lag years.

This sector runs at 64:1 substep ratio (timestep_hint = 1/64 = 0.015625)
for accuracy with fast disease dynamics.
"""

from __future__ import annotations

import numpy as np

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Cohort definitions ────────────────────────────────────────────────

# Cohort names and age ranges
_COHORT_NAMES = ["C1_0_14", "C2_15_44", "C3_45_64", "C4_65_plus"]
_COHORT_LABELS = ["0-14", "15-44", "45-64", "65+"]

# Working-age cohorts (indices into cohort list)
_WORKING_COHORTS = [1, 2]  # C2 and C3

# ── Disease parameters (fixed to literature values) ───────────────────

# For a model with annual timesteps, we scale disease dynamics to
# operate on yearly timescales. Real disease dynamics (days/weeks) are
# much faster than the model timestep, so we use effective annual rates
# that capture the aggregate effect of a fast epidemic.
#
# R0 = 2.5 is preserved. The epidemic growth rate is (R0-1)*gamma.
# For annual dynamics: gamma_eff ~ 2.0/year (infectious period ~6 months)
# This gives epidemic growth rate ~3.0/year, meaning the epidemic
# unfolds over ~1 year rather than weeks.

_INCUBATION_PERIOD_YEAR = 0.05    # ~18 days in years
_INFECTIOUS_PERIOD_YEAR = 0.1     # ~36 days in years
_R0_BASE = 2.5                    # basic reproduction number
_RECOVERY_LAG = 30.0 / 365.0      # 30 days in years
_PRODUCTIVITY_PENALTY = 0.2       # 20% productivity reduction during recovery

# Convert to per-year rates
_SIGMA = 1.0 / _INCUBATION_PERIOD_YEAR   # ~20.0 per year
_GAMMA = 1.0 / _INFECTIOUS_PERIOD_YEAR    # ~10.0 per year
_BETA_BASE = _R0_BASE * _GAMMA            # ~25.0 per year

# Temperature sensitivity for transmission
_TEMP_SENSITIVITY = 0.02  # 2% increase in beta per degree of warming

# Contact matrix (relative contact rates between cohorts)
# Row = source cohort, Col = target cohort
# Simplified: higher within-cohort contacts, lower between-cohort
_CONTACT_MATRIX = np.array([
    [1.5, 0.8, 0.4, 0.3],  # C1: high school/daycare contacts
    [0.8, 1.5, 0.6, 0.3],  # C2: workplace contacts
    [0.4, 0.6, 1.2, 0.5],  # C3: mixed workplace/home
    [0.3, 0.3, 0.5, 1.0],  # C4: home/care contacts
])


class SEIRModule:
    """SEIR disease dynamics with 4-cohort population model.

    Stocks: S, E, I, R for each of 4 cohorts (16 total)
    Reads: temperature_anomaly, P1, P2, P3, P4 (population by cohort),
           birth_rate, death_rate
    Writes: S/E/I/R for each cohort, labor_force_multiplier,
            infected_count, reproduction_number
    """

    name = "seir"
    version = "1.0.0"
    # 64:1 substep ratio for fast disease dynamics
    timestep_hint: float | None = 1.0 / 64.0

    def __init__(
        self,
        r0_base: float = _R0_BASE,
        incubation_period: float = _INCUBATION_PERIOD_YEAR,
        infectious_period: float = _INFECTIOUS_PERIOD_YEAR,
        temp_sensitivity: float = _TEMP_SENSITIVITY,
        initial_infected_fraction: float = 0.001,  # 0.1% initially infected
    ) -> None:
        self.r0_base = r0_base
        self.sigma = 1.0 / max(incubation_period, 1e-10)
        self.gamma = 1.0 / max(infectious_period, 1e-10)
        self.beta_base = self.r0_base * self.gamma
        self.temp_sensitivity = temp_sensitivity
        self.initial_infected_fraction = initial_infected_fraction

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        stocks = {}
        # Initialize with small infected fraction to seed the epidemic
        for i, label in enumerate(_COHORT_NAMES):
            # Get population from context or use defaults
            # These will be overwritten when population sector runs first
            pop_default = [0.4e9, 1.0e9, 0.5e9, 0.2e9][i]
            s0 = pop_default * (1.0 - self.initial_infected_fraction)
            e0 = 0.0
            i0 = pop_default * self.initial_infected_fraction
            r0 = 0.0
            stocks[f"S_{label}"] = Quantity(s0, "persons")
            stocks[f"E_{label}"] = Quantity(e0, "persons")
            stocks[f"I_{label}"] = Quantity(i0, "persons")
            stocks[f"R_{label}"] = Quantity(r0, "persons")
        return stocks

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        # Read temperature anomaly for transmission coupling
        temp_anomaly = inputs.get(
            "temperature_anomaly", Quantity(0.0, "deg_C_anomaly")
        ).magnitude

        # Read population by cohort (from PopulationSector)
        # Fall back to SEIR stock totals if PopulationSector isn't present
        pop_by_cohort = []
        pop_keys = ["P1", "P2", "P3", "P4"]
        for i, key in enumerate(pop_keys):
            p = inputs.get(key, Quantity(0.0, "persons")).magnitude
            if p <= 0.0:
                label = _COHORT_NAMES[i]
                p = (
                    stocks[f"S_{label}"].magnitude
                    + stocks[f"E_{label}"].magnitude
                    + stocks[f"I_{label}"].magnitude
                    + stocks[f"R_{label}"].magnitude
                )
            pop_by_cohort.append(max(p, 1.0))  # Avoid division by zero

        # Maturation flows from PopulationSector (persons/year aging into next cohort)
        mat_vals = [
            inputs.get("mat1", Quantity(0.0, "persons_per_year")).magnitude,
            inputs.get("mat2", Quantity(0.0, "persons_per_year")).magnitude,
            inputs.get("mat3", Quantity(0.0, "persons_per_year")).magnitude,
            0.0,  # C4 (65+): no out-flow
        ]

        # Read birth and death rates
        birth_rate = inputs.get(
            "birth_rate", Quantity(0.03, "per_year")
        ).magnitude
        death_rate = inputs.get(
            "death_rate", Quantity(0.02, "per_year")
        ).magnitude

        # Temperature-modified transmission rate
        beta = self.beta_base * (
            1.0 + self.temp_sensitivity * max(temp_anomaly, 0.0)
        )

        # Total population and infected
        N_total = sum(pop_by_cohort)
        I_total = 0.0
        S_vals = []
        E_vals = []
        I_vals = []
        R_vals = []

        for i, label in enumerate(_COHORT_NAMES):
            s = max(stocks[f"S_{label}"].magnitude, 0.0)
            e = max(stocks[f"E_{label}"].magnitude, 0.0)
            iv = max(stocks[f"I_{label}"].magnitude, 0.0)
            r = max(stocks[f"R_{label}"].magnitude, 0.0)
            S_vals.append(s)
            E_vals.append(e)
            I_vals.append(iv)
            R_vals.append(r)
            I_total += iv

        # Compute derivatives for each cohort
        outputs: dict[str, Quantity] = {}
        total_disease_excess_deaths: float = 0.0

        for i, label in enumerate(_COHORT_NAMES):
            s = S_vals[i]
            e = E_vals[i]
            iv = I_vals[i]
            r = R_vals[i]
            pop = pop_by_cohort[i]

            # Contact-modified force of infection
            # Weighted sum of infected contacts from all cohorts
            foi_c = 0.0
            for j in range(4):
                foi_c += _CONTACT_MATRIX[i, j] * I_vals[j] / max(N_total, 1.0)
            foi_c *= beta

            # Clamp force of infection to prevent numerical explosions
            foi_c = min(foi_c, 5.0)  # Max 500% infection rate per year

            # Births go into S of C1 cohort (0-14)
            births = birth_rate * pop if i == 0 else 0.0

            # Deaths (proportional to compartment size)
            deaths_s = death_rate * s
            deaths_e = death_rate * e
            deaths_i = death_rate * iv * 1.5  # Higher mortality for infected
            deaths_r = death_rate * r
            total_disease_excess_deaths += death_rate * iv * 0.5  # excess above background

            # Proportional aging: fraction of this cohort that ages into next
            out_frac = mat_vals[i] / max(pop, 1.0)
            if i > 0:
                prev_pop = pop_by_cohort[i - 1]
                in_frac = mat_vals[i - 1] / max(prev_pop, 1.0)
                aging_in_s = S_vals[i - 1] * in_frac
                aging_in_e = E_vals[i - 1] * in_frac
                aging_in_i = I_vals[i - 1] * in_frac
                aging_in_r = R_vals[i - 1] * in_frac
            else:
                aging_in_s = aging_in_e = aging_in_i = aging_in_r = 0.0

            # SEIR dynamics
            dS = births - foi_c * s - deaths_s - s * out_frac + aging_in_s
            dE = foi_c * s - self.sigma * e - deaths_e - e * out_frac + aging_in_e
            dI = self.sigma * e - self.gamma * iv - deaths_i - iv * out_frac + aging_in_i
            dR = self.gamma * iv - deaths_r - r * out_frac + aging_in_r

            # Clamp derivatives to prevent negative stocks
            if s <= 0.0 and dS < 0:
                dS = 0.0
            if e <= 0.0 and dE < 0:
                dE = 0.0
            if iv <= 0.0 and dI < 0:
                dI = 0.0
            if r <= 0.0 and dR < 0:
                dR = 0.0

            # Additional clamp: derivatives should not change stocks by more
            # than 100% in one substep (prevents numerical explosions)
            max_change = max(s, e, iv, r, 1.0) * 0.5  # 50% max change
            dS = max(-max_change, min(dS, max_change))
            dE = max(-max_change, min(dE, max_change))
            dI = max(-max_change, min(dI, max_change))
            dR = max(-max_change, min(dR, max_change))

            outputs[f"d_S_{label}"] = Quantity(dS, "persons")
            outputs[f"d_E_{label}"] = Quantity(dE, "persons")
            outputs[f"d_I_{label}"] = Quantity(dI, "persons")
            outputs[f"d_R_{label}"] = Quantity(dR, "persons")

        # Labor Force Multiplier
        # Only working-age cohorts (C2: 15-44, C3: 45-64) contribute
        working_susceptible = sum(S_vals[i] for i in _WORKING_COHORTS)
        working_recovered = sum(R_vals[i] for i in _WORKING_COHORTS)
        working_total = sum(pop_by_cohort[i] for i in _WORKING_COHORTS)

        # Post-infection productivity penalty for recovered
        effective_recovered = working_recovered * (
            1.0 - _PRODUCTIVITY_PENALTY
        )

        labor_force_multiplier = (
            working_susceptible + effective_recovered
        ) / max(working_total, 1.0)
        labor_force_multiplier = min(max(labor_force_multiplier, 0.0), 1.0)

        # Effective reproduction number
        R_eff = beta / self.gamma * I_total / max(N_total, 1.0) if I_total > 0 else 0.0

        outputs["labor_force_multiplier"] = Quantity(
            labor_force_multiplier, "dimensionless"
        )
        outputs["infected_count"] = Quantity(I_total, "persons")
        outputs["reproduction_number"] = Quantity(R_eff, "dimensionless")
        outputs["disease_death_rate"] = Quantity(
            total_disease_excess_deaths / max(N_total, 1.0), "per_year"
        )

        # Write S/E/I/R stocks to shared for recording
        for i, label in enumerate(_COHORT_NAMES):
            outputs[f"S_{label}"] = Quantity(S_vals[i], "persons")
            outputs[f"E_{label}"] = Quantity(E_vals[i], "persons")
            outputs[f"I_{label}"] = Quantity(I_vals[i], "persons")
            outputs[f"R_{label}"] = Quantity(R_vals[i], "persons")

        return outputs

    def declares_reads(self) -> list[str]:
        return [
            "temperature_anomaly",
            "P1", "P2", "P3", "P4",
            "birth_rate",
            "death_rate",
            "mat1",
            "mat2",
            "mat3",
        ]

    def declares_writes(self) -> list[str]:
        writes = []
        for label in _COHORT_NAMES:
            writes.extend([
                f"S_{label}", f"E_{label}",
                f"I_{label}", f"R_{label}",
            ])
        writes.extend([
            "labor_force_multiplier",
            "infected_count",
            "reproduction_number",
            "disease_death_rate",
        ])
        return writes

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.SYNTHESIZED_FROM_PRIMARY_LITERATURE,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Fixed contact matrix (not dynamic network)",
                "Uniform death rate across compartments (except 1.5x for infected)",
                "Births only enter C1 cohort",
                "Post-infection productivity penalty is constant (not decaying)",
                "Temperature coupling is linear (not species-specific)",
            ],
            "free_parameters": [
                "r0_base",
                "incubation_period",
                "infectious_period",
                "temp_sensitivity",
                "initial_infected_fraction",
            ],
            "conservation_groups": [],
            "observables": [
                "labor_force_multiplier",
                "infected_count",
                "reproduction_number",
            ],
            "unit_notes": (
                "S/E/I/R in persons, labor_force_multiplier dimensionless 0-1, "
                "reproduction_number dimensionless"
            ),
        }
