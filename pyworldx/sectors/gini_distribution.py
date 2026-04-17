"""Gini Distribution Matrix (Phase 1 Task 5).

Replaces global average resource allocation with a Distribution Matrix
that allocates food/capital by percentile with Intake Accentuation
during scarcity.

Implementation (Q50):
  - Pre-computed non-linear lookup tables (TABHL-style)
  - Live vectorized NumPy array sum for normalization
  - Scalar-to-array multiplication for final allocation
  - NOT iterative Python loops

Bifurcated Collapse (Q06):
  - Top 10%: "Comprehensive Technology" moderate decline
  - Bottom 90%: "Business as Usual" demographic crash

Social Suicide Governance Multiplier (Q06):
  - Equal sharing abandoned when average below subsistence
  - Governance Multiplier drives this behavior

Three distinct mortality multipliers (Q06):
  - DRFM_p: death-rate-from-food (per percentile)
  - DRHM_p: health service deprivation (per percentile)
  - DRPM_p: pollution exposure (per percentile)
"""

from __future__ import annotations

import numpy as np

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Pre-computed Gini weight lookup tables ─────────────────────────────

# Scarcity levels (0.0 = total scarcity, 1.0 = abundance)
_SCARCITY_X = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])

# Gini weights for top 10% at each scarcity level (intake accentuation)
_TOP10_WEIGHTS = np.array([0.90, 0.70, 0.50, 0.30, 0.15, 0.10])

# Gini weights for bottom 90% at each scarcity level
_BOT90_WEIGHTS = np.array([0.10, 0.30, 0.50, 0.70, 0.85, 0.90])

# Subsistence threshold (FPC below this → Social Suicide mechanism)
_SUBSISTENCE_FPC = 230.0  # kg/person/year


def _interp_weight(scarcity: float, table: np.ndarray) -> float:
    """Interpolate weight from pre-computed table."""
    return float(np.interp(scarcity, _SCARCITY_X, table))


class GiniDistributionSector:
    """Gini Distribution Matrix with Intake Accentuation.

    NOT a traditional stock-based sector. Computes per-percentile
    allocation using vectorized NumPy operations.

    Reads: food_per_capita, industrial_output_per_capita,
           service_output_per_capita, pollution_index, POP
    Writes: gini_food_top10, gini_food_bot90, gini_io_top10, gini_io_bot90,
            DRFM_top10, DRFM_bot90, DRHM_top10, DRHM_bot90,
            DRPM_top10, DRPM_bot90, social_suicide_active
    """

    name = "gini_distribution"
    version = "1.0.0"
    timestep_hint: float | None = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        # No stocks — this is a pure allocation module
        return {}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        fpc = inputs.get(
            "food_per_capita", Quantity(300.0, "food_units")
        ).magnitude
        iopc = inputs.get(
            "industrial_output_per_capita",
            Quantity(40.0, "industrial_output_units"),
        ).magnitude
        sopc = inputs.get(
            "service_output_per_capita",
            Quantity(87.0, "service_output_units"),
        ).magnitude
        ppolx = inputs.get(
            "pollution_index", Quantity(1.0, "dimensionless")
        ).magnitude

        # ── Scarcity index (0=total scarcity, 1=abundance) ───────────
        food_scarcity = min(fpc / max(_SUBSISTENCE_FPC * 2, 1.0), 1.0)

        # ── Vectorized allocation (NumPy, no Python loops) ───────────
        top10_weight = _interp_weight(food_scarcity, _TOP10_WEIGHTS)
        bot90_weight = _interp_weight(food_scarcity, _BOT90_WEIGHTS)

        # Normalize so weights sum to 1.0
        total_w = top10_weight * 0.1 + bot90_weight * 0.9
        top10_norm = (top10_weight * 0.1) / max(total_w, 1e-15)
        bot90_norm = (bot90_weight * 0.9) / max(total_w, 1e-15)

        # Per-capita allocation by percentile
        food_top10 = fpc * top10_norm / 0.1   # per-capita for top 10%
        food_bot90 = fpc * bot90_norm / 0.9   # per-capita for bottom 90%

        io_top10 = iopc * top10_norm / 0.1
        io_bot90 = iopc * bot90_norm / 0.9

        # ── Social Suicide Governance Multiplier (Q06) ───────────────
        # When average amount is not enough for life, system abandons
        # equal sharing to prevent rich cohort from falling below subsistence
        social_suicide = 1.0 if food_bot90 < _SUBSISTENCE_FPC * 0.5 else 0.0

        # ── Stratified mortality multipliers (Q06) ───────────────────
        # DRFM_p: death-rate-from-food per percentile
        drfm_top10 = max(1.0 - food_top10 / max(_SUBSISTENCE_FPC, 1.0), 0.0)
        drfm_bot90 = max(1.0 - food_bot90 / max(_SUBSISTENCE_FPC, 1.0), 0.0)

        # Threshold-gated exponentials for bottom 90% during collapse
        if drfm_bot90 > 0.5:
            # Switch from linear to exponential mortality
            drfm_bot90 = drfm_bot90 ** 2 * 2.0

        # DRHM_p: health service deprivation per percentile
        service_top10 = sopc * top10_norm / 0.1
        service_bot90 = sopc * bot90_norm / 0.9
        drhm_top10 = max(1.0 - service_top10 / max(sopc * 2, 1.0), 0.0)
        drhm_bot90 = max(1.0 - service_bot90 / max(sopc * 2, 1.0), 0.0)

        # DRPM_p: pollution exposure per percentile
        # Bottom 90% have higher pollution exposure (environmental injustice)
        drpm_top10 = max(ppolx - 1.0, 0.0) * 0.05
        drpm_bot90 = max(ppolx - 1.0, 0.0) * 0.15

        return {
            "gini_food_top10": Quantity(food_top10, "food_units"),
            "gini_food_bot90": Quantity(food_bot90, "food_units"),
            "gini_io_top10": Quantity(
                io_top10, "industrial_output_units"
            ),
            "gini_io_bot90": Quantity(
                io_bot90, "industrial_output_units"
            ),
            "DRFM_top10": Quantity(drfm_top10, "dimensionless"),
            "DRFM_bot90": Quantity(drfm_bot90, "dimensionless"),
            "DRHM_top10": Quantity(drhm_top10, "dimensionless"),
            "DRHM_bot90": Quantity(drhm_bot90, "dimensionless"),
            "DRPM_top10": Quantity(drpm_top10, "dimensionless"),
            "DRPM_bot90": Quantity(drpm_bot90, "dimensionless"),
            "social_suicide_active": Quantity(
                social_suicide, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "food_per_capita",
            "industrial_output_per_capita",
            "service_output_per_capita",
            "pollution_index",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "gini_food_top10",
            "gini_food_bot90",
            "gini_io_top10",
            "gini_io_bot90",
            "DRFM_top10",
            "DRFM_bot90",
            "DRHM_top10",
            "DRHM_bot90",
            "DRPM_top10",
            "DRPM_bot90",
            "social_suicide_active",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.DESIGN_CHOICE,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Two-bin stratification (top 10%, bottom 90%) not full percentile",
                "Simplified Gini weight lookup tables",
                "Linear-to-exponential mortality transition at threshold",
            ],
            "free_parameters": [],
            "conservation_groups": [],
            "observables": [
                "gini_food_top10",
                "gini_food_bot90",
                "DRFM_top10",
                "DRFM_bot90",
                "social_suicide_active",
            ],
            "unit_notes": (
                "Intake Accentuation via pre-computed weight tables. "
                "Vectorized NumPy operations. "
                "DRFM/DRHM/DRPM per-percentile mortality multipliers (Q06)."
            ),
        }
