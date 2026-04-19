# tests/unit/test_bayesian_optimizer.py
"""Tests for Task 3: Bayesian global optimizer in calibration pipeline."""
from __future__ import annotations

import numpy as np
import pytest

optuna = pytest.importorskip("optuna", reason="optuna required for Bayesian optimizer tests")


def test_bayesian_optimize_import() -> None:
    """_bayesian_optimize must be importable from pipeline."""
    from pyworldx.calibration.pipeline import _bayesian_optimize  # noqa: F401


def test_bayesian_optimize_returns_within_bounds() -> None:
    """All returned params must lie within their declared bounds."""
    from pyworldx.calibration.pipeline import _bayesian_optimize

    bounds = {"a": (0.0, 1.0), "b": (2.0, 5.0)}
    initial = {"a": 0.5, "b": 3.0}

    def obj(p: dict[str, float]) -> float:
        return (p["a"] - 0.3) ** 2 + (p["b"] - 4.0) ** 2

    best_params, best_val, n_trials_done = _bayesian_optimize(
        obj, initial, bounds, ["a", "b"], n_trials=20, timeout=30, seed=0
    )
    assert 0.0 <= best_params["a"] <= 1.0
    assert 2.0 <= best_params["b"] <= 5.0
    assert isinstance(best_val, float)
    assert np.isfinite(best_val)
    assert 1 <= n_trials_done <= 20


def test_bayesian_optimize_improves_over_initial() -> None:
    """Bayesian search must find a value at least as good as the initial point."""
    from pyworldx.calibration.pipeline import _bayesian_optimize

    bounds = {"x": (0.0, 10.0)}
    initial = {"x": 9.0}  # far from optimum at x=3

    def obj(p: dict[str, float]) -> float:
        return (p["x"] - 3.0) ** 2

    initial_val = obj(initial)
    best_params, best_val, _ = _bayesian_optimize(
        obj, initial, bounds, ["x"], n_trials=30, timeout=30, seed=42
    )
    assert best_val <= initial_val


def test_bayesian_optimize_non_screened_params_unchanged() -> None:
    """Params not in parameter_names must stay at their initial values."""
    from pyworldx.calibration.pipeline import _bayesian_optimize

    bounds = {"a": (0.0, 1.0), "b": (0.0, 1.0), "fixed": (0.0, 1.0)}
    initial = {"a": 0.5, "b": 0.5, "fixed": 0.99}

    def obj(p: dict[str, float]) -> float:
        return p["a"] ** 2 + p["b"] ** 2

    best_params, _, _ = _bayesian_optimize(
        obj, initial, bounds, ["a", "b"],  # "fixed" not optimized
        n_trials=10, timeout=10, seed=0,
    )
    assert best_params["fixed"] == pytest.approx(0.99)


def test_run_calibration_pipeline_accepts_bayesian_params() -> None:
    """run_calibration_pipeline must accept bayesian_n_trials and bayesian_timeout."""
    from pyworldx.calibration.pipeline import run_calibration_pipeline
    from pyworldx.calibration.parameters import ParameterRegistry

    registry = ParameterRegistry()

    def obj(p: dict[str, float]) -> float:
        return sum(v ** 2 for v in p.values())

    # Must not raise TypeError from unexpected keyword argument
    report = run_calibration_pipeline(
        obj, registry, bayesian_n_trials=5, bayesian_timeout=10, seed=0
    )
    assert report is not None


def test_bayesian_n_trials_zero_skips_bayesian() -> None:
    """bayesian_n_trials=0 must skip Bayesian step entirely."""
    from pyworldx.calibration.pipeline import run_calibration_pipeline
    from pyworldx.calibration.parameters import ParameterRegistry

    registry = ParameterRegistry()

    def obj(p: dict[str, float]) -> float:
        return sum(v ** 2 for v in p.values())

    # With 0 trials, pipeline should still complete without calling _bayesian_optimize
    report = run_calibration_pipeline(
        obj, registry, bayesian_n_trials=0, seed=0
    )
    assert report is not None
    assert report.calibration is not None


def test_nelder_mead_starts_from_bayesian_best(monkeypatch: pytest.MonkeyPatch) -> None:
    """The initial_params passed to _nelder_mead_optimize must equal Bayesian best."""
    import pyworldx.calibration.pipeline as pipe_module

    captured: dict[str, dict[str, float]] = {}

    original_nm = pipe_module._nelder_mead_optimize
    def mock_nm(
        objective_fn,
        initial_params,
        bounds,
        parameter_names,
        **kwargs,
    ):
        captured["initial"] = dict(initial_params)
        return original_nm(objective_fn, initial_params, bounds, parameter_names, **kwargs)

    bayesian_result: dict[str, float] = {}

    def mock_bayes(objective_fn, initial_params, bounds, parameter_names, **kwargs):
        best = {k: 0.42 for k in parameter_names}
        bayesian_result.update(best)
        return best, 0.01, len(parameter_names)

    monkeypatch.setattr(pipe_module, "_nelder_mead_optimize", mock_nm)
    monkeypatch.setattr(pipe_module, "_bayesian_optimize", mock_bayes)

    from pyworldx.calibration.parameters import ParameterRegistry
    registry = ParameterRegistry()

    def obj(p: dict[str, float]) -> float:
        return sum(v ** 2 for v in p.values())

    pipe_module.run_calibration_pipeline(obj, registry, bayesian_n_trials=3, seed=0)

    # Nelder-Mead's initial_params for screened parameters must match Bayesian output
    for name, val in bayesian_result.items():
        assert captured["initial"].get(name, None) == pytest.approx(val, abs=1e-9)
