"""Tests for the config module."""

from __future__ import annotations

from pyworldx.config import ModelConfig
from pyworldx.config.calibration_config import (
    CrossValidationConfig,
    NEBEL_2023_BOUNDS,
    NEBEL_2023_CALIBRATION_CONFIG,
    NEBEL_2023_TOTAL_NRMSD_BOUND,
)
from pyworldx.config.ensemble_config import (
    DistributionType,
    ParameterDistribution,
    ThresholdQuery,
    UncertaintyType,
)
from pyworldx.config.scenario_config import PolicyEvent, PolicyShape, Scenario


class TestModelConfigDefaults:
    def test_master_dt(self) -> None:
        cfg = ModelConfig()
        assert cfg.master_dt == 1.0

    def test_t_start(self) -> None:
        cfg = ModelConfig()
        assert cfg.t_start == 0.0

    def test_t_end(self) -> None:
        cfg = ModelConfig()
        assert cfg.t_end == 200.0

    def test_integrator(self) -> None:
        cfg = ModelConfig()
        assert cfg.integrator == "rk4"

    def test_loop_tol(self) -> None:
        cfg = ModelConfig()
        assert cfg.loop_tol == 1e-10

    def test_trace_level(self) -> None:
        cfg = ModelConfig()
        assert cfg.trace_level == "OFF"


class TestCalibrationConfigReExports:
    def test_cross_validation_config(self) -> None:
        assert CrossValidationConfig is not None
        cfg = NEBEL_2023_CALIBRATION_CONFIG
        assert isinstance(cfg, CrossValidationConfig)

    def test_nebel_bounds(self) -> None:
        assert isinstance(NEBEL_2023_BOUNDS, dict)
        assert len(NEBEL_2023_BOUNDS) > 0

    def test_nebel_total_bound(self) -> None:
        assert isinstance(NEBEL_2023_TOTAL_NRMSD_BOUND, float)
        assert NEBEL_2023_TOTAL_NRMSD_BOUND > 0


class TestScenarioConfigReExports:
    def test_policy_shape(self) -> None:
        assert PolicyShape.STEP is not None
        assert PolicyShape.RAMP is not None

    def test_policy_event(self) -> None:
        pe = PolicyEvent("x", PolicyShape.STEP, t_start=50.0, magnitude=10.0)
        assert pe.target == "x"

    def test_scenario(self) -> None:
        s = Scenario(name="t", description="d", start_year=1900, end_year=2100)
        assert s.name == "t"


class TestEnsembleConfigReExports:
    def test_uncertainty_type(self) -> None:
        assert UncertaintyType.PARAMETER.value == "parameter"

    def test_distribution_type(self) -> None:
        assert DistributionType.UNIFORM.value == "uniform"

    def test_threshold_query(self) -> None:
        tq = ThresholdQuery("q", "X", "below", 1.0, 2050)
        assert tq.name == "q"

    def test_parameter_distribution(self) -> None:
        pd = ParameterDistribution(
            DistributionType.UNIFORM,
            {"low": 0.0, "high": 1.0},
            "stream",
            UncertaintyType.PARAMETER,
        )
        assert pd.uncertainty_type == UncertaintyType.PARAMETER
