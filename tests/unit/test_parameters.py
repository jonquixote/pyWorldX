"""Tests for calibration parameter registry."""

from __future__ import annotations

import pytest

from pyworldx.calibration.parameters import (
    DuplicateParameterError,
    IdentifiabilityRisk,
    ParameterEntry,
    ParameterRegistry,
    UnknownParameterError,
    build_world3_parameter_registry,
)


class TestParameterEntry:
    def test_valid_entry(self) -> None:
        e = ParameterEntry(
            name="test", default=1.0, bounds=(0.0, 2.0),
            units="m", sector_owner="s1",
        )
        assert e.default == 1.0

    def test_bounds_validation(self) -> None:
        with pytest.raises(ValueError, match="lower bound"):
            ParameterEntry(
                name="bad", default=1.0, bounds=(3.0, 1.0),
                units="m", sector_owner="s1",
            )

    def test_default_outside_bounds(self) -> None:
        with pytest.raises(ValueError, match="outside bounds"):
            ParameterEntry(
                name="bad", default=5.0, bounds=(0.0, 2.0),
                units="m", sector_owner="s1",
            )


class TestParameterRegistry:
    def test_register_and_lookup(self) -> None:
        reg = ParameterRegistry()
        entry = ParameterEntry(
            name="x", default=1.0, bounds=(0.0, 2.0),
            units="m", sector_owner="s1",
        )
        reg.register(entry)
        result = reg.lookup("x")
        assert result.default == 1.0

    def test_duplicate_raises(self) -> None:
        reg = ParameterRegistry()
        entry = ParameterEntry(
            name="x", default=1.0, bounds=(0.0, 2.0),
            units="m", sector_owner="s1",
        )
        reg.register(entry)
        with pytest.raises(DuplicateParameterError):
            reg.register(entry)

    def test_unknown_raises(self) -> None:
        reg = ParameterRegistry()
        with pytest.raises(UnknownParameterError):
            reg.lookup("missing")

    def test_get_defaults(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
        reg.register(ParameterEntry("b", 3.0, (0.0, 5.0), "m", "s2"))
        defaults = reg.get_defaults()
        assert defaults == {"a": 1.0, "b": 3.0}

    def test_get_bounds(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
        bounds = reg.get_bounds()
        assert bounds["a"] == (0.0, 2.0)

    def test_get_sector_parameters(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
        reg.register(ParameterEntry("b", 2.0, (0.0, 5.0), "m", "s1"))
        reg.register(ParameterEntry("c", 3.0, (0.0, 5.0), "m", "s2"))
        params = reg.get_sector_parameters("s1")
        assert len(params) == 2

    def test_get_risky_parameters(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry(
            "safe", 1.0, (0.0, 2.0), "m", "s1",
            identifiability_risk=IdentifiabilityRisk.NONE,
        ))
        reg.register(ParameterEntry(
            "risky", 1.0, (0.0, 2.0), "m", "s1",
            identifiability_risk=IdentifiabilityRisk.HIGH,
        ))
        risky = reg.get_risky_parameters()
        assert len(risky) == 1
        assert risky[0].name == "risky"

    def test_validate_overrides(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
        # Valid override
        assert len(reg.validate_overrides({"a": 1.5})) == 0
        # Out of bounds
        warnings = reg.validate_overrides({"a": 5.0})
        assert len(warnings) == 1
        # Unknown parameter
        warnings = reg.validate_overrides({"unknown": 1.0})
        assert len(warnings) == 1

    def test_apply_overrides(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
        reg.register(ParameterEntry("b", 3.0, (0.0, 5.0), "m", "s2"))
        result = reg.apply_overrides({"a": 1.5})
        assert result["a"] == 1.5
        assert result["b"] == 3.0

    def test_to_dict(self) -> None:
        reg = ParameterRegistry()
        reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
        d = reg.to_dict()
        assert "a" in d
        assert d["a"]["default"] == 1.0

    def test_build_world3_registry(self) -> None:
        reg = build_world3_parameter_registry()
        assert reg.size >= 15
        # Check known parameters exist
        icor = reg.lookup("capital.icor")
        assert icor.identifiability_risk == IdentifiabilityRisk.HIGH
        pop = reg.lookup("population.cbr_base")
        assert pop.sector_owner == "population"
