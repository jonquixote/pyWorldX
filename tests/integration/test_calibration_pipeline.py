"""Phase 5 integration tests: preset-based calibration and verification.

Tests the full pipeline:
  Preset -> ParameterRegistry -> Engine -> DataBridge -> NRMSD
"""

from __future__ import annotations

import numpy as np

from pyworldx.presets import (
    WORLD3_03,
    NEBEL_2024,
    get_preset,
    list_presets,
    ModelPreset,
)
from pyworldx.calibration.parameters import build_world3_parameter_registry
from pyworldx.data.bridge import CalibrationTarget, DataBridge
from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
from data_pipeline.connectors.world3_reference import World3ReferenceConnector
from pyworldx.scenarios.scenario import Scenario


# ── Helpers ──────────────────────────────────────────────────────────────

def _engine_from_preset(preset: ModelPreset):
    """Build a simple engine factory from a preset.

    Returns trajectories that scale based on key preset parameters,
    giving us different outputs for different presets.
    """
    registry = build_world3_parameter_registry()
    params = preset.apply_to_registry(registry)

    # Use alic and initial_nr as drivers of trajectory shape
    alic = params.get("capital.alic", 14.0)
    initial_nr = params.get("resources.initial_nr", 1.0e12)
    pptd = params.get("pollution.pptd", 20.0)

    def engine(run_params: dict[str, float]):
        merged = dict(params)
        merged.update(run_params)

        time = np.arange(1900, 2101, dtype=float)

        # Population: logistic curve, peaks later with higher alic
        peak_year = 2030 + (alic - 14.0) * 2
        pop_raw = 1.65e9 * np.exp(0.015 * (time - 1900)) / (
            1 + np.exp(0.015 * (time - 1900)) * np.exp(-0.02 * (time - peak_year))
        )
        pop = np.clip(pop_raw, 1.65e9, 12e9)

        # Industrial output: peaks and declines
        io_peak = 2020 + (alic - 14.0) * 3
        io = 7.9e11 * np.exp(0.03 * (time - 1970)) * np.exp(
            -0.001 * np.maximum(time - io_peak, 0) ** 2
        )

        # Food per capita
        fpc = 230.0 + 50 * np.sin(np.pi * (time - 1900) / 200)

        # NR fraction: exponential depletion scaled by initial_nr
        nr_scale = initial_nr / 1.0e12
        nrfr = nr_scale * np.exp(-0.015 * (time - 1900))

        # Pollution index: rises with delay driven by pptd
        delay_factor = 20.0 / max(pptd, 1.0)
        ppolx = 1.0 + 25 * (1 - np.exp(-delay_factor * 0.02 * (time - 1900)))

        # Life expectancy
        le = 28.0 + 45 * (1 - np.exp(-0.02 * (time - 1900)))

        # HWI and EF
        hwi = 0.3 + 0.5 * np.clip((le - 28) / 50, 0, 1)
        ef = 0.5 + 3.5 * np.clip((io / 7.9e11) ** 0.5, 0, 3)

        trajectories = {
            "POP": pop,
            "industrial_output": io,
            "food_per_capita": fpc,
            "NR": nrfr * initial_nr,
            "pollution_index": ppolx,
            "life_expectancy": le,
            "human_welfare_index": hwi,
            "ecological_footprint": ef,
        }
        return trajectories, time

    return engine


# ═══════════════════════════════════════════════════════════════════════
# Phase 5: Preset -> Reference validation
# ═══════════════════════════════════════════════════════════════════════

class TestPresetReferenceValidation:
    """Validate presets against W3-03 reference trajectories."""

    def test_w303_against_reference(self):
        """W3-03 preset engine vs reference should have finite NRMSD."""
        connector = World3ReferenceConnector()
        engine = _engine_from_preset(WORLD3_03)

        runner = EmpiricalCalibrationRunner(
            aligned_dir="/nonexistent",  # no empirical data needed
            reference_connector=connector,
            normalize=True,
        )
        result = runner.validate_against_reference(engine, {})
        assert result is not None
        assert result.n_targets >= 5  # at least 5 of 8 variables matched
        assert np.isfinite(result.composite_nrmsd)
        # Simplified engine won't perfectly match, but should be reasonable
        assert result.composite_nrmsd < 5.0

    def test_nebel_against_reference(self):
        """Nebel preset should produce different NRMSD vs reference."""
        connector = World3ReferenceConnector()

        w3_engine = _engine_from_preset(WORLD3_03)
        nebel_engine = _engine_from_preset(NEBEL_2024)

        runner = EmpiricalCalibrationRunner(
            aligned_dir="/nonexistent",
            reference_connector=connector,
            normalize=True,
        )
        w3_result = runner.validate_against_reference(w3_engine, {})
        nebel_result = runner.validate_against_reference(nebel_engine, {})

        assert w3_result is not None
        assert nebel_result is not None
        # They should produce different composite NRMSD values
        assert w3_result.composite_nrmsd != nebel_result.composite_nrmsd


class TestCrossPresetComparison:
    """Compare trajectories across W3-03 and Nebel presets."""

    def test_presets_produce_different_params(self):
        """Registry with different presets yields different parameter values."""
        registry = build_world3_parameter_registry()

        w3_params = WORLD3_03.apply_to_registry(registry)
        nebel_params = NEBEL_2024.apply_to_registry(registry)

        # These should differ for known Nebel overrides
        assert w3_params["capital.alic"] != nebel_params["capital.alic"]
        # pptd=111.8 is now the engine default, so both presets agree on it.
        # Check icor instead (another Nebel recalibrated parameter):
        assert w3_params["capital.icor"] != nebel_params["capital.icor"]

    def test_presets_produce_different_trajectories(self):
        """Different presets should produce observably different trajectories."""
        w3_engine = _engine_from_preset(WORLD3_03)
        nebel_engine = _engine_from_preset(NEBEL_2024)

        w3_trajs, w3_time = w3_engine({})
        nebel_trajs, nebel_time = nebel_engine({})

        # Population trajectories should differ
        w3_pop_2050 = np.interp(2050, w3_time, w3_trajs["POP"])
        nebel_pop_2050 = np.interp(2050, nebel_time, nebel_trajs["POP"])
        assert w3_pop_2050 != nebel_pop_2050

        # Industrial output trajectories should differ (alic, icor are different)
        w3_io_2050 = np.interp(2050, w3_time, w3_trajs["industrial_output"])
        nebel_io_2050 = np.interp(2050, nebel_time, nebel_trajs["industrial_output"])
        assert w3_io_2050 != nebel_io_2050

    def test_nebel_has_later_peaks(self):
        """Nebel's higher alic should push industrial output peak later."""
        w3_engine = _engine_from_preset(WORLD3_03)
        nebel_engine = _engine_from_preset(NEBEL_2024)

        w3_trajs, w3_time = w3_engine({})
        nebel_trajs, nebel_time = nebel_engine({})

        w3_io_peak_year = w3_time[np.argmax(w3_trajs["industrial_output"])]
        nebel_io_peak_year = nebel_time[np.argmax(nebel_trajs["industrial_output"])]

        assert nebel_io_peak_year >= w3_io_peak_year

    def test_all_presets_produce_valid_trajectories(self):
        """Every registered preset produces finite, positive key trajectories."""
        for name in list_presets():
            preset = get_preset(name)
            engine = _engine_from_preset(preset)
            trajs, time = engine({})

            assert len(time) == 201, f"{name}: wrong time length"

            for var in ["POP", "industrial_output", "life_expectancy"]:
                assert var in trajs, f"{name}: missing {var}"
                assert np.all(np.isfinite(trajs[var])), f"{name}: {var} has NaN/Inf"
                assert np.all(trajs[var] > 0), f"{name}: {var} has non-positive values"


class TestScenarioFromPresetIntegration:
    """Test Scenario.from_preset() with calibration bridge."""

    def test_scenario_from_w303_has_correct_overrides(self):
        scenario = Scenario.from_preset("world3_03")
        assert scenario.parameter_overrides == {}
        assert "world3_03" in scenario.tags

    def test_scenario_from_nebel_has_correct_overrides(self):
        scenario = Scenario.from_preset("nebel_2024")
        assert scenario.parameter_overrides["capital.alic"] == 15.24
        # pptd is now the engine default — not a Nebel override
        assert "nebel_2024" in scenario.tags

    def test_scenario_extra_overrides_applied(self):
        scenario = Scenario.from_preset(
            "world3_03",
            extra_overrides={"capital.alic": 16.0},
        )
        assert scenario.parameter_overrides["capital.alic"] == 16.0

    def test_scenario_extra_overrides_override_preset(self):
        """Extra overrides take precedence over preset values."""
        scenario = Scenario.from_preset(
            "nebel_2024",
            extra_overrides={"capital.alic": 20.0},
        )
        assert scenario.parameter_overrides["capital.alic"] == 20.0


class TestBridgeObjectiveWithPresets:
    """Test that DataBridge objective functions work with preset engines."""

    def test_objective_from_reference_targets(self):
        """Build an objective from reference targets and evaluate."""
        connector = World3ReferenceConnector()
        targets_dicts = connector.to_calibration_targets()

        targets = [
            CalibrationTarget(
                variable_name=td["variable_name"],
                years=td["years"],
                values=td["values"],
                unit=td["unit"],
                weight=td["weight"],
                source=td["source"],
                nrmsd_method=td["nrmsd_method"],
            )
            for td in targets_dicts
        ]

        bridge = DataBridge(normalize=True)
        engine = _engine_from_preset(WORLD3_03)
        objective = bridge.build_objective(targets, engine)

        score = objective({})
        assert isinstance(score, float)
        assert np.isfinite(score)
        assert score > 0  # won't be perfect match

    def test_nebel_objective_differs_from_w303(self):
        """Nebel and W3-03 should give different objective scores."""
        connector = World3ReferenceConnector()
        targets_dicts = connector.to_calibration_targets()

        targets = [
            CalibrationTarget(
                variable_name=td["variable_name"],
                years=td["years"],
                values=td["values"],
                unit=td["unit"],
                weight=td["weight"],
                source=td["source"],
                nrmsd_method=td["nrmsd_method"],
            )
            for td in targets_dicts
        ]

        bridge = DataBridge(normalize=True)

        w3_engine = _engine_from_preset(WORLD3_03)
        nebel_engine = _engine_from_preset(NEBEL_2024)

        w3_score = bridge.build_objective(targets, w3_engine)({})
        nebel_score = bridge.build_objective(targets, nebel_engine)({})

        assert w3_score != nebel_score


class TestReferenceConnectorCoverage:
    """Verify reference connector covers full simulation range."""

    def test_reference_spans_1900_to_2100(self):
        connector = World3ReferenceConnector()
        for var in connector.available_variables():
            series = connector.fetch(var)
            assert series.index[0] == 1900, f"{var} doesn't start at 1900"
            assert series.index[-1] == 2100, f"{var} doesn't end at 2100"

    def test_interpolated_annual_coverage(self):
        connector = World3ReferenceConnector()
        for var in connector.available_variables():
            series = connector.fetch_interpolated(var)
            assert len(series) == 201, f"{var}: expected 201 annual values"
            assert np.all(np.isfinite(series.values)), f"{var}: has NaN/Inf"
