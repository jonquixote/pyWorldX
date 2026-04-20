"""Display-layer unit conversions for pyWorldX engine output.

Internal engine units are physical/model units. This module provides
display-layer conversions for human-readable reporting only.

CRITICAL: These conversions must NEVER be applied inside:
  - _normalize_to_index() — normalization must be unit-agnostic
  - NRMSD calculation — comparisons always use internal units
  - Any sector compute() path

They are ONLY for CalibrationResult.sector_trajectories display output
and human-readable reports.
"""
from __future__ import annotations

# ── Food per capita ───────────────────────────────────────────────────
# Internal engine unit: veg_equiv_kg / person / yr
# Display unit: kcal / person / day
#
# Conversion: 1800 kcal per kg vegetable-equivalent (FAO standard for
# a mixed diet basket, World3 FPC definition). NOT dry biomass (3500)
# and NOT wet weight (≈700 kcal/kg).
#
# Sanity check at 1970 engine baseline:
#   ~450 kg/person/yr × 4.932 ≈ 2,220 kcal/day  (historically plausible)
#   230 kg/person/yr × 4.932 ≈ 1,134 kcal/day   (1900 pre-industrial — below FAO
#                                                  subsistence, correct for W3-03)
#
# The threshold in gini_distribution.py (_SUBSISTENCE_FPC = 230 kg/person/yr)
# converts to 2500/4.932 ≈ 507 kg/person/yr at starvation — a distinct,
# more severe level than engine subsistence. Do NOT change _SUBSISTENCE_FPC.
FOOD_KCAL_PER_KG_VEG_EQUIV: float = 1800.0
DAYS_PER_YEAR: float = 365.0
FOOD_KG_TO_KCAL_DAY: float = FOOD_KCAL_PER_KG_VEG_EQUIV / DAYS_PER_YEAR  # ≈ 4.932


def convert_food_per_capita_to_display(kg_per_yr: float) -> float:
    """Convert internal veg_equiv_kg/person/yr to kcal/person/day for display.

    Args:
        kg_per_yr: Food per capita in vegetable-equivalent kg per person per year.

    Returns:
        Food per capita in kcal per person per day.
    """
    return kg_per_yr * FOOD_KG_TO_KCAL_DAY


def convert_food_trajectory_to_display(
    trajectory: dict[int, float],
) -> dict[int, float]:
    """Convert a year-keyed food_per_capita trajectory to display units.

    Args:
        trajectory: Dict mapping year (int) to food_per_capita in kg/person/yr.

    Returns:
        Dict mapping year (int) to food_per_capita in kcal/person/day.
    """
    return {year: convert_food_per_capita_to_display(v) for year, v in trajectory.items()}
