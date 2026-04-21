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
        pop = reg.lookup("population.len_scale")  # updated: cbr_base → len_scale
        assert pop.sector_owner == "population"


# ── Phase 1: Full ParameterRegistry contract tests ─────────────────────


class TestRegistryConstruction:
    def test_registry_builds_without_error(self) -> None:
        reg = build_world3_parameter_registry()
        assert reg is not None

    def test_registry_has_17_parameters(self, full_registry) -> None:
        assert full_registry.size == 16  # 3 pop + 4 capital + 4 agri + 2 res + 3 poll

    def test_all_sectors_present(self, full_registry) -> None:
        sectors = {e.sector_owner for e in full_registry.all_entries()}
        assert sectors == {"population", "capital", "agriculture", "resources", "pollution"}

    def test_get_defaults_returns_all_names(self, full_registry) -> None:
        defaults = full_registry.get_defaults()
        assert len(defaults) == full_registry.size
        assert all(isinstance(v, float) for v in defaults.values())

    def test_get_bounds_all_valid(self, full_registry) -> None:
        for name, (lo, hi) in full_registry.get_bounds().items():
            assert lo < hi, f"{name}: lo={lo} >= hi={hi}"
        assert len(full_registry.get_bounds()) == full_registry.size

    def test_default_within_bounds_for_all(self, full_registry) -> None:
        bounds = full_registry.get_bounds()
        defaults = full_registry.get_defaults()
        for name, val in defaults.items():
            lo, hi = bounds[name]
            assert lo <= val <= hi, f"{name}: {val} outside [{lo}, {hi}]"


class TestGetSectorParameters:
    def test_get_sector_parameters_population(self, full_registry) -> None:
        params = full_registry.get_sector_parameters("population")
        assert len(params) == 3
        names = {p.name for p in params}
        assert "population.len_scale" in names
        assert "population.mtfn_scale" in names
        assert "population.initial_population" in names

    def test_get_sector_parameters_capital(self, full_registry) -> None:
        params = full_registry.get_sector_parameters("capital")
        assert len(params) == 4

    def test_get_sector_parameters_agriculture(self, full_registry) -> None:
        params = full_registry.get_sector_parameters("agriculture")
        assert len(params) == 4

    def test_get_sector_parameters_resources(self, full_registry) -> None:
        params = full_registry.get_sector_parameters("resources")
        assert len(params) == 2

    def test_get_sector_parameters_pollution(self, full_registry) -> None:
        params = full_registry.get_sector_parameters("pollution")
        assert len(params) == 3

    def test_get_sector_parameters_unknown_sector_returns_empty(self, full_registry) -> None:
        result = full_registry.get_sector_parameters("nonexistent")
        assert result == []

    def test_sector_parameters_sum_to_total(self, full_registry) -> None:
        total = sum(
            len(full_registry.get_sector_parameters(s))
            for s in ["population", "capital", "agriculture", "resources", "pollution"]
        )
        assert total == full_registry.size


class TestLookupAndValidation:
    def test_lookup_known_parameter(self, full_registry) -> None:
        entry = full_registry.lookup("population.len_scale")
        assert entry.default == pytest.approx(1.0)
        assert entry.bounds == (0.5, 1.5)
        assert entry.units == "dimensionless"

    def test_lookup_unknown_raises(self, full_registry) -> None:
        with pytest.raises(KeyError):
            full_registry.lookup("does.not.exist")

    def test_validate_overrides_out_of_bounds(self, full_registry) -> None:
        warnings = full_registry.validate_overrides({"population.len_scale": 999.0})
        assert len(warnings) == 1
        assert "population.len_scale" in warnings[0]

    def test_validate_overrides_unknown_param(self, full_registry) -> None:
        warnings = full_registry.validate_overrides({"fake.param": 1.0})
        assert any("Unknown" in w for w in warnings)

    def test_apply_overrides_produces_correct_value(self, full_registry) -> None:
        result = full_registry.apply_overrides({"population.len_scale": 1.2})
        assert result["population.len_scale"] == pytest.approx(1.2)
        # all other params unchanged
        assert result["population.mtfn_scale"] == pytest.approx(1.0)

    def test_duplicate_registration_raises(self) -> None:
        reg = ParameterRegistry()
        entry = ParameterEntry(
            name="test.param", default=1.0, bounds=(0.0, 2.0),
            units="dimensionless", sector_owner="test"
        )
        reg.register(entry)
        with pytest.raises(DuplicateParameterError):
            reg.register(entry)

    def test_all_entries_returns_list(self, full_registry) -> None:
        entries = full_registry.all_entries()
        assert isinstance(entries, list)
        assert len(entries) == full_registry.size


class TestRegistryNegativeContracts:
    """Regression guard: ensure phantom methods are never added."""

    def test_registry_has_no_for_sector_classmethod(self, full_registry) -> None:
        assert not hasattr(full_registry, "for_sector")

    def test_registry_has_no_subset_method(self, full_registry) -> None:
        assert not hasattr(full_registry, "subset")

    def test_registry_has_no_len(self) -> None:
        """len(registry) must raise TypeError — use .size instead."""
        reg = ParameterRegistry()
        with pytest.raises(TypeError):
            len(reg)
