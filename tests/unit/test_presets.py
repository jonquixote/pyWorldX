"""Tests for Phase 3: ModelPreset system.

Covers:
  - ModelPreset dataclass
  - Built-in presets (world3_03, nebel_2024)
  - Preset registry (get_preset, list_presets, register_preset)
  - Preset application to ParameterRegistry
  - Scenario.from_preset() integration
"""

from __future__ import annotations

import pytest

from pyworldx.presets import (
    NEBEL_2024,
    PRESETS,
    WORLD3_03,
    ModelPreset,
    get_preset,
    list_presets,
    register_preset,
)
from pyworldx.calibration.parameters import (
    build_world3_parameter_registry,
)
from pyworldx.scenarios.scenario import Scenario


# ═══════════════════════════════════════════════════════════════════════
# ModelPreset dataclass
# ═══════════════════════════════════════════════════════════════════════

class TestModelPreset:
    def test_defaults(self):
        preset = ModelPreset(name="test", description="Test preset")
        assert preset.parameter_overrides == {}
        assert preset.source == ""
        assert preset.year == 2004
        assert preset.notes == ""

    def test_with_overrides(self):
        preset = ModelPreset(
            name="custom",
            description="Custom preset",
            parameter_overrides={"capital.alic": 15.0},
            source="my_paper",
            year=2025,
        )
        assert preset.parameter_overrides["capital.alic"] == 15.0
        assert preset.year == 2025

    def test_to_scenario_overrides(self):
        preset = ModelPreset(
            name="test",
            description="Test",
            parameter_overrides={"a": 1.0, "b": 2.0},
        )
        overrides = preset.to_scenario_overrides()
        assert overrides == {"a": 1.0, "b": 2.0}
        # Should be a copy
        overrides["c"] = 3.0
        assert "c" not in preset.parameter_overrides


# ═══════════════════════════════════════════════════════════════════════
# Built-in presets
# ═══════════════════════════════════════════════════════════════════════

class TestBuiltinPresets:
    def test_world3_03_exists(self):
        assert "world3_03" in PRESETS
        assert WORLD3_03.name == "world3_03"

    def test_world3_03_has_no_overrides(self):
        """W3-03 IS the baseline — no overrides needed."""
        assert WORLD3_03.parameter_overrides == {}

    def test_world3_03_year(self):
        assert WORLD3_03.year == 2004

    def test_nebel_2024_exists(self):
        assert "nebel_2024" in PRESETS
        assert NEBEL_2024.name == "nebel_2024"

    def test_nebel_2024_has_overrides(self):
        """Nebel should have at least the headline alic parameter.
        NOTE: pptd=111.8 is now the engine default (Phase 0.5), not a Nebel override.
        """
        assert "capital.alic" in NEBEL_2024.parameter_overrides

    def test_nebel_2024_alic_value(self):
        assert NEBEL_2024.parameter_overrides["capital.alic"] == 15.24

    def test_nebel_2024_year(self):
        assert NEBEL_2024.year == 2024

    def test_nebel_2024_has_source(self):
        assert "10.1111/jiec.13442" in NEBEL_2024.source

    def test_nebel_different_from_w3_03(self):
        """Nebel overrides should be different from W3-03 defaults."""
        reg = build_world3_parameter_registry()
        defaults = reg.get_defaults()
        for param, nebel_val in NEBEL_2024.parameter_overrides.items():
            if param in defaults:
                assert nebel_val != defaults[param], (
                    f"Nebel override for {param} equals W3-03 default"
                )


# ═══════════════════════════════════════════════════════════════════════
# Preset registry
# ═══════════════════════════════════════════════════════════════════════

class TestPresetRegistry:
    def test_get_preset_known(self):
        preset = get_preset("world3_03")
        assert preset is WORLD3_03

    def test_get_preset_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown preset"):
            get_preset("nonexistent")

    def test_list_presets(self):
        names = list_presets()
        assert "world3_03" in names
        assert "nebel_2024" in names
        # Should be sorted
        assert names == sorted(names)

    def test_register_custom_preset(self):
        custom = ModelPreset(
            name="test_custom_42",
            description="Test custom",
            parameter_overrides={"capital.icor": 4.0},
        )
        register_preset(custom)
        assert get_preset("test_custom_42") is custom
        # Clean up
        del PRESETS["test_custom_42"]


# ═══════════════════════════════════════════════════════════════════════
# Preset + ParameterRegistry integration
# ═══════════════════════════════════════════════════════════════════════

class TestPresetRegistryIntegration:
    def test_world3_03_returns_defaults(self):
        reg = build_world3_parameter_registry()
        params = WORLD3_03.apply_to_registry(reg)
        defaults = reg.get_defaults()
        assert params == defaults

    def test_nebel_overrides_applied(self):
        reg = build_world3_parameter_registry()
        params = NEBEL_2024.apply_to_registry(reg)
        assert params["capital.alic"] == 15.24
        # pptd=111.8 is now the engine default — no longer a Nebel override
        assert params["pollution.pptd"] == 111.8

    def test_nebel_preserves_non_overridden_defaults(self):
        reg = build_world3_parameter_registry()
        defaults = reg.get_defaults()
        params = NEBEL_2024.apply_to_registry(reg)
        for name, default_val in defaults.items():
            if name not in NEBEL_2024.parameter_overrides:
                assert params[name] == default_val, (
                    f"Non-overridden param {name} changed"
                )

    def test_nebel_overrides_within_bounds(self):
        """All Nebel overrides should be within parameter bounds."""
        reg = build_world3_parameter_registry()
        bounds = reg.get_bounds()
        for param, value in NEBEL_2024.parameter_overrides.items():
            if param in bounds:
                lo, hi = bounds[param]
                assert lo <= value <= hi, (
                    f"Nebel override {param}={value} outside bounds ({lo}, {hi})"
                )


# ═══════════════════════════════════════════════════════════════════════
# Scenario.from_preset() integration
# ═══════════════════════════════════════════════════════════════════════

class TestScenarioFromPreset:
    def test_from_world3_03(self):
        scenario = Scenario.from_preset("world3_03")
        assert scenario.name == "world3_03_scenario"
        assert scenario.start_year == 1900
        assert scenario.end_year == 2100
        assert scenario.parameter_overrides == {}
        assert "world3_03" in scenario.tags

    def test_from_nebel_2024(self):
        scenario = Scenario.from_preset("nebel_2024")
        assert "capital.alic" in scenario.parameter_overrides
        assert scenario.parameter_overrides["capital.alic"] == 15.24
        assert "nebel_2024" in scenario.tags

    def test_custom_name(self):
        scenario = Scenario.from_preset("world3_03", name="my_scenario")
        assert scenario.name == "my_scenario"

    def test_extra_overrides_merge(self):
        scenario = Scenario.from_preset(
            "nebel_2024",
            extra_overrides={"resources.initial_nr": 2.0e12},
        )
        # Nebel overrides preserved
        assert scenario.parameter_overrides["capital.alic"] == 15.24
        # Extra override added
        assert scenario.parameter_overrides["resources.initial_nr"] == 2.0e12

    def test_extra_overrides_take_precedence(self):
        scenario = Scenario.from_preset(
            "nebel_2024",
            extra_overrides={"capital.alic": 20.0},
        )
        # Extra override should override Nebel's value
        assert scenario.parameter_overrides["capital.alic"] == 20.0

    def test_unknown_preset_raises(self):
        with pytest.raises(KeyError, match="Unknown preset"):
            Scenario.from_preset("nonexistent")

    def test_custom_time_range(self):
        scenario = Scenario.from_preset(
            "world3_03",
            start_year=1950,
            end_year=2050,
        )
        assert scenario.start_year == 1950
        assert scenario.end_year == 2050
