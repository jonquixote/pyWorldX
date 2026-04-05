"""Tests for Quantity arithmetic and unit checking."""

import math

import pytest

from pyworldx.core.quantities import (
    CAPITAL_UNITS,
    DIMENSIONLESS,
    PER_YEAR,
    PEOPLE,
    POLLUTION_UNITS,
    RESOURCE_UNITS,
    YEARS,
    Quantity,
    UnitMismatchError,
)


# ---------------------------------------------------------------------------
# Addition / subtraction — same unit only
# ---------------------------------------------------------------------------

class TestAdditiveArithmetic:
    def test_add_same_unit(self) -> None:
        a = Quantity(10.0, PEOPLE)
        b = Quantity(5.0, PEOPLE)
        result = a + b
        assert result.magnitude == 15.0
        assert result.unit == PEOPLE

    def test_sub_same_unit(self) -> None:
        a = Quantity(10.0, RESOURCE_UNITS)
        b = Quantity(3.0, RESOURCE_UNITS)
        result = a - b
        assert result.magnitude == 7.0

    def test_add_different_units_raises(self) -> None:
        a = Quantity(10.0, PEOPLE)
        b = Quantity(5.0, CAPITAL_UNITS)
        with pytest.raises(UnitMismatchError, match="Cannot add"):
            _ = a + b

    def test_sub_different_units_raises(self) -> None:
        a = Quantity(10.0, POLLUTION_UNITS)
        b = Quantity(5.0, YEARS)
        with pytest.raises(UnitMismatchError, match="Cannot subtract"):
            _ = a - b

    def test_negation(self) -> None:
        a = Quantity(7.0, PEOPLE)
        result = -a
        assert result.magnitude == -7.0
        assert result.unit == PEOPLE


# ---------------------------------------------------------------------------
# Multiplication / division
# ---------------------------------------------------------------------------

class TestMultiplicativeArithmetic:
    def test_mul_dimensionless(self) -> None:
        a = Quantity(10.0, PEOPLE)
        b = Quantity(2.0, DIMENSIONLESS)
        result = a * b
        assert result.magnitude == 20.0
        assert result.unit == PEOPLE

    def test_mul_scalar(self) -> None:
        a = Quantity(5.0, RESOURCE_UNITS)
        result = a * 3.0
        assert result.magnitude == 15.0
        assert result.unit == RESOURCE_UNITS

    def test_rmul_scalar(self) -> None:
        a = Quantity(5.0, RESOURCE_UNITS)
        result = 3.0 * a
        assert result.magnitude == 15.0
        assert result.unit == RESOURCE_UNITS

    def test_div_same_unit_yields_dimensionless(self) -> None:
        a = Quantity(10.0, PEOPLE)
        b = Quantity(5.0, PEOPLE)
        result = a / b
        assert result.magnitude == 2.0
        assert result.unit == DIMENSIONLESS

    def test_div_scalar(self) -> None:
        a = Quantity(10.0, CAPITAL_UNITS)
        result = a / 2.0
        assert result.magnitude == 5.0
        assert result.unit == CAPITAL_UNITS

    def test_per_year_times_years(self) -> None:
        rate = Quantity(0.05, PER_YEAR)
        dt = Quantity(1.0, YEARS)
        result = rate * dt
        assert result.unit == DIMENSIONLESS
        assert math.isclose(result.magnitude, 0.05)

    def test_power(self) -> None:
        a = Quantity(4.0, DIMENSIONLESS)
        result = a ** 0.5
        assert math.isclose(result.magnitude, 2.0)
        assert result.unit == DIMENSIONLESS


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:
    def test_lt(self) -> None:
        assert Quantity(1.0, PEOPLE) < Quantity(2.0, PEOPLE)

    def test_gt(self) -> None:
        assert Quantity(5.0, PEOPLE) > Quantity(2.0, PEOPLE)

    def test_compare_different_units_raises(self) -> None:
        with pytest.raises(UnitMismatchError):
            _ = Quantity(1.0, PEOPLE) < Quantity(2.0, CAPITAL_UNITS)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

class TestUtility:
    def test_is_finite(self) -> None:
        assert Quantity(1.0, PEOPLE).is_finite()
        assert not Quantity(float("nan"), PEOPLE).is_finite()
        assert not Quantity(float("inf"), PEOPLE).is_finite()

    def test_assert_unit_pass(self) -> None:
        q = Quantity(1.0, PEOPLE)
        assert q.assert_unit(PEOPLE) is q

    def test_assert_unit_fail(self) -> None:
        q = Quantity(1.0, PEOPLE)
        with pytest.raises(UnitMismatchError):
            q.assert_unit(CAPITAL_UNITS)

    def test_float_conversion(self) -> None:
        q = Quantity(42.0, DIMENSIONLESS)
        assert float(q) == 42.0
