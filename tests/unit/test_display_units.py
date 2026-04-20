"""T0-2: Display units gate — food per capita conversion.

Verifies the display-layer conversion constant is correct and that
the conversion function produces plausible kcal/day values at known
historical anchor points.
"""
from __future__ import annotations

import pytest
from pyworldx.calibration.display_units import (
    FOOD_KG_TO_KCAL_DAY,
    FOOD_KCAL_PER_KG_VEG_EQUIV,
    convert_food_per_capita_to_display,
    convert_food_trajectory_to_display,
)


def test_conversion_constant_is_correct() -> None:
    """FOOD_KG_TO_KCAL_DAY must be 1800/365 ≈ 4.932."""
    expected = 1800.0 / 365.0
    assert FOOD_KG_TO_KCAL_DAY == pytest.approx(expected, rel=1e-6), (
        f"FOOD_KG_TO_KCAL_DAY={FOOD_KG_TO_KCAL_DAY:.4f}, expected {expected:.4f}. "
        "Use FAO veg-equiv standard: 1800 kcal/kg."
    )


def test_kcal_per_kg_is_fao_standard() -> None:
    """Must be 1800 kcal/kg (FAO veg-equiv), not 3500 (dry biomass)."""
    assert FOOD_KCAL_PER_KG_VEG_EQUIV == 1800.0


def test_1970_baseline_is_plausible() -> None:
    """World3-03 ~1970 engine output of ~450 kg/person/yr → ~2220 kcal/day."""
    kcal = convert_food_per_capita_to_display(450.0)
    assert 2000 < kcal < 2600, (
        f"450 kg/yr → {kcal:.0f} kcal/day, expected 2000–2600. "
        "Check conversion factor."
    )


def test_preindustrial_1900_baseline_is_below_subsistence() -> None:
    """World3-03 1900 FPC ≈ 230 kg/yr → ~1134 kcal/day (pre-industrial, below FAO subsistence)."""
    kcal = convert_food_per_capita_to_display(230.0)
    assert 900 < kcal < 1400, (
        f"230 kg/yr → {kcal:.0f} kcal/day, expected 900–1400 for 1900 pre-industrial. "
        "FAO subsistence is ~2100 kcal/day — 1900 should be well below it."
    )


def test_trajectory_conversion_preserves_keys() -> None:
    """convert_food_trajectory_to_display must return the same year keys."""
    trajectory = {1900: 230.0, 1970: 450.0, 2000: 520.0}
    result = convert_food_trajectory_to_display(trajectory)
    assert set(result.keys()) == {1900, 1970, 2000}
    assert result[1970] == pytest.approx(450.0 * FOOD_KG_TO_KCAL_DAY, rel=1e-9)


def test_zero_fpc_converts_to_zero() -> None:
    assert convert_food_per_capita_to_display(0.0) == 0.0


def test_conversion_is_linear() -> None:
    """The conversion must be a simple scale — no offsets."""
    a = convert_food_per_capita_to_display(100.0)
    b = convert_food_per_capita_to_display(200.0)
    assert b == pytest.approx(2 * a, rel=1e-9)
