"""Tests for sensitivity analysis (Morris, Sobol, profile likelihood)."""

from __future__ import annotations

from pyworldx.calibration.parameters import (
    IdentifiabilityRisk,
    ParameterEntry,
    ParameterRegistry,
)
from pyworldx.calibration.sensitivity import (
    run_morris_screening,
    run_profile_likelihood,
    run_sobol_analysis,
)


def _make_registry() -> ParameterRegistry:
    reg = ParameterRegistry()
    reg.register(ParameterEntry("a", 1.0, (0.0, 2.0), "m", "s1"))
    reg.register(ParameterEntry("b", 0.5, (0.0, 1.0), "m", "s1"))
    reg.register(ParameterEntry(
        "c", 5.0, (0.0, 10.0), "m", "s2",
        identifiability_risk=IdentifiabilityRisk.HIGH,
    ))
    return reg


def _quadratic_objective(params: dict[str, float]) -> float:
    """Simple quadratic: dominated by 'a', minor 'b', negligible 'c'."""
    a = params.get("a", 1.0)
    b = params.get("b", 0.5)
    c = params.get("c", 5.0)
    return 10 * (a - 1.0) ** 2 + (b - 0.5) ** 2 + 0.001 * c


class TestMorrisScreening:
    def test_runs_and_returns_result(self) -> None:
        reg = _make_registry()
        result = run_morris_screening(
            _quadratic_objective, reg, n_trajectories=5
        )
        assert len(result.parameter_names) == 3
        assert len(result.ranking) == 3
        assert len(result.mu_star) == 3

    def test_ranking_order(self) -> None:
        reg = _make_registry()
        result = run_morris_screening(
            _quadratic_objective, reg, n_trajectories=20
        )
        # 'a' should dominate (coefficient 10)
        assert result.ranking[0] == "a"

    def test_get_influential(self) -> None:
        reg = _make_registry()
        result = run_morris_screening(
            _quadratic_objective, reg, n_trajectories=20
        )
        influential = result.get_influential(threshold_fraction=0.9)
        assert "a" in influential
        assert len(influential) <= 3


class TestSobolAnalysis:
    def test_runs_and_returns_result(self) -> None:
        reg = _make_registry()
        result = run_sobol_analysis(
            _quadratic_objective, reg, n_samples=64
        )
        assert len(result.s1) == 3
        assert len(result.st) == 3
        # All indices should be non-negative
        for name in result.parameter_names:
            assert result.s1[name] >= 0
            assert result.st[name] >= 0

    def test_dominant_parameter(self) -> None:
        reg = _make_registry()
        result = run_sobol_analysis(
            _quadratic_objective, reg, n_samples=128
        )
        dominant = result.get_dominant_parameters(st_threshold=0.05)
        assert "a" in dominant


class TestProfileLikelihood:
    def test_runs_on_risky_params(self) -> None:
        reg = _make_registry()
        report = run_profile_likelihood(
            _quadratic_objective, reg, grid_resolution=10
        )
        # Only 'c' is flagged as risky
        assert len(report.results) == 1
        assert report.results[0].parameter == "c"

    def test_flat_profile_detected(self) -> None:
        reg = _make_registry()
        # c has coefficient 0.001 — nearly flat profile
        report = run_profile_likelihood(
            _quadratic_objective, reg, grid_resolution=10,
            flat_threshold=0.5,
        )
        assert report.results[0].classification in (
            "flat_plateau", "threshold_gated"
        )

    def test_identifiable_report(self) -> None:
        reg = _make_registry()
        report = run_profile_likelihood(
            _quadratic_objective, reg,
            parameter_names=["a"],
            grid_resolution=10,
        )
        # 'a' has strong curvature — should be identifiable
        assert report.results[0].classification == "identifiable"
        assert report.total_evaluations == 10
