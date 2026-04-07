"""Tests for ontology dimensions and unit conversion."""

from __future__ import annotations

import pytest

from pyworldx.ontology.dimensions import (
    UNIT_FAMILIES,
    UnitFamily,
    convert_units,
)


class TestUnitFamilies:
    def test_populated(self) -> None:
        assert len(UNIT_FAMILIES) > 0

    def test_expected_families_exist(self) -> None:
        expected = [
            "people",
            "capital_units",
            "resource_units",
            "pollution_units",
            "food_units",
            "industrial_output_units",
            "years",
            "per_year",
            "hectares",
            "dimensionless",
        ]
        for family in expected:
            assert family in UNIT_FAMILIES, f"Missing family: {family}"

    def test_each_family_has_base_unit(self) -> None:
        for name, family in UNIT_FAMILIES.items():
            assert isinstance(family, UnitFamily)
            assert family.base_unit, f"Family '{name}' has no base_unit"

    def test_each_family_has_self_conversion(self) -> None:
        for name, family in UNIT_FAMILIES.items():
            assert (
                family.base_unit in family.conversions
            ), f"Family '{name}' missing base unit in conversions"


class TestConvertUnits:
    def test_millions_to_persons(self) -> None:
        result = convert_units(1.0, "millions", "persons", "people")
        assert result == 1e6

    def test_persons_to_millions(self) -> None:
        result = convert_units(5e6, "persons", "millions", "people")
        assert abs(result - 5.0) < 1e-10

    def test_identity_conversion(self) -> None:
        result = convert_units(42.0, "persons", "persons", "people")
        assert result == 42.0

    def test_hectares_to_km2(self) -> None:
        # 1 km2 = 100 hectares, so 100 hectares -> 1 km2
        result = convert_units(100.0, "hectares", "km2", "hectares")
        assert abs(result - 1.0) < 1e-10

    def test_percent_to_fraction(self) -> None:
        result = convert_units(50.0, "percent", "fraction", "dimensionless")
        assert abs(result - 0.5) < 1e-10

    def test_unknown_family_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown unit family"):
            convert_units(1.0, "x", "y", "nonexistent_family")

    def test_unknown_from_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown unit"):
            convert_units(1.0, "bogus_unit", "persons", "people")

    def test_unknown_to_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown unit"):
            convert_units(1.0, "persons", "bogus_unit", "people")
