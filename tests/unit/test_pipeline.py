"""Tests for calibration pipeline."""

from __future__ import annotations

from pyworldx.calibration.metrics import CrossValidationConfig
from pyworldx.calibration.parameters import (
    IdentifiabilityRisk,
    ParameterEntry,
    ParameterRegistry,
)
from pyworldx.calibration.pipeline import (
    _nelder_mead_optimize,
    run_calibration_pipeline,
)


def _make_registry() -> ParameterRegistry:
    reg = ParameterRegistry()
    reg.register(ParameterEntry(
        "a", 1.0, (0.0, 3.0), "m", "s1",
        identifiability_risk=IdentifiabilityRisk.NONE,
    ))
    reg.register(ParameterEntry(
        "b", 0.5, (0.0, 2.0), "m", "s1",
        identifiability_risk=IdentifiabilityRisk.NONE,
    ))
    reg.register(ParameterEntry(
        "c", 5.0, (0.0, 10.0), "m", "s2",
        identifiability_risk=IdentifiabilityRisk.HIGH,
    ))
    return reg


def _rosenbrock(params: dict[str, float]) -> float:
    """2D Rosenbrock-like: minimum at a=1.5, b=1.0."""
    a = params.get("a", 1.0)
    b = params.get("b", 0.5)
    return (a - 1.5) ** 2 + 2 * (b - 1.0) ** 2 + 0.001 * params.get("c", 5.0)


class TestNelderMead:
    def test_finds_minimum(self) -> None:
        reg = _make_registry()
        best, obj, iters, converged = _nelder_mead_optimize(
            _rosenbrock,
            reg.get_defaults(),
            reg.get_bounds(),
            ["a", "b"],
            max_iter=200,
        )
        assert abs(best["a"] - 1.5) < 0.1
        assert abs(best["b"] - 1.0) < 0.1
        assert obj < 0.05

    def test_converges(self) -> None:
        reg = _make_registry()
        _, _, _, converged = _nelder_mead_optimize(
            _rosenbrock,
            reg.get_defaults(),
            reg.get_bounds(),
            ["a", "b"],
            max_iter=500,
            tol=1e-8,
        )
        assert converged


class TestCalibrationPipeline:
    def test_full_pipeline(self) -> None:
        reg = _make_registry()
        report = run_calibration_pipeline(
            _rosenbrock,
            reg,
            cross_val_config=CrossValidationConfig(),
            morris_trajectories=5,
            sobol_samples=32,
            profile_grid=5,
            optimize_max_iter=50,
        )
        # All steps should have run
        assert report.identifiability is not None
        assert report.morris is not None
        assert report.calibration is not None
        assert report.sobol is not None
        assert report.total_evaluations > 0

    def test_pipeline_improves_objective(self) -> None:
        reg = _make_registry()
        initial_obj = _rosenbrock(reg.get_defaults())
        report = run_calibration_pipeline(
            _rosenbrock, reg,
            morris_trajectories=5,
            sobol_samples=32,
            optimize_max_iter=100,
        )
        assert report.calibration is not None
        assert report.calibration.total_nrmsd < initial_obj

    def test_screened_parameters_subset(self) -> None:
        reg = _make_registry()
        report = run_calibration_pipeline(
            _rosenbrock, reg,
            morris_trajectories=10,
            sobol_samples=32,
            optimize_max_iter=50,
        )
        # Screened should be a subset of all
        all_names = {e.name for e in reg.all_entries()}
        for name in report.screened_parameters:
            assert name in all_names
