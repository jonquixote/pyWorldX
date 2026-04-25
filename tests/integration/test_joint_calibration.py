"""T3-1 · Joint Optuna + Nelder-Mead on Composite Objective.

Tests verify that EmpiricalCalibrationRunner in composite mode correctly:
  - Exposes the mandated composite weights
  - Computes independent validation NRMSD on the holdout window
  - Returns a report with all required fields (train_nrmsd, validation_nrmsd,
    overfit_flagged, optimized_params)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
from pyworldx.data.bridge import BridgeResult


# ── T3-1: Composite objective weights ────────────────────────────────


def test_composite_objective_weights_sum_to_meaningful_total():
    runner = EmpiricalCalibrationRunner(composite=True)
    weights = runner.get_objective_weights()
    assert "population" in weights
    assert "co2" in weights
    assert weights["population"] == pytest.approx(1.5, rel=0.01)
    assert weights["co2"] == pytest.approx(1.5, rel=0.01)
    assert weights["resources"] == pytest.approx(0.75, rel=0.01)


# ── T3-1: Validation NRMSD independence ──────────────────────────────


def test_joint_calibration_validation_nrmsd_is_independent():
    """Joint run must compute validation NRMSD on holdout window only."""
    runner = EmpiricalCalibrationRunner(composite=True)

    _dummy_result = BridgeResult(
        per_variable_nrmsd={},
        composite_nrmsd=0.09,
        n_targets=0,
        coverage={},
    )

    with patch.object(
        runner.bridge,
        "calculate_validation_score",
        return_value=_dummy_result,
    ) as mock_val:
        # Stub the optimizer to return empty params (skip real Optuna)
        with patch.object(runner, "_run_optimizer", return_value={}):
            # Stub build_objective so it doesn't need real targets/engine
            with patch.object(
                runner.bridge, "build_objective", return_value=lambda p: 0.05
            ):
                # Stub load_targets to avoid Parquet I/O
                with patch.object(runner, "load_targets", return_value=[
                    _make_dummy_target("POP"),
                ]):
                    runner.run()
        mock_val.assert_called_once()


# ── T3-1: Result report completeness ─────────────────────────────────


def test_joint_calibration_result_has_all_required_fields():
    runner = EmpiricalCalibrationRunner(composite=True)

    _dummy_val = BridgeResult(
        per_variable_nrmsd={},
        composite_nrmsd=0.07,
        n_targets=0,
        coverage={},
    )

    with patch.object(runner, "_run_optimizer", return_value={"cbr_base": 0.028}):
        with patch.object(
            runner.bridge, "build_objective", return_value=lambda p: 0.05
        ):
            with patch.object(
                runner.bridge, "calculate_validation_score", return_value=_dummy_val
            ):
                with patch.object(runner, "load_targets", return_value=[
                    _make_dummy_target("POP"),
                ]):
                    result = runner.run()

    assert hasattr(result, "train_nrmsd")
    assert hasattr(result, "validation_nrmsd")
    assert hasattr(result, "overfit_flagged")
    assert hasattr(result, "optimized_params")

    # Verify the values were actually populated
    assert result.train_nrmsd == pytest.approx(0.05)
    assert result.validation_nrmsd == pytest.approx(0.07)
    assert result.optimized_params == {"cbr_base": 0.028}


# ── Helpers ───────────────────────────────────────────────────────────

import numpy as np  # noqa: E402

from pyworldx.data.bridge import CalibrationTarget  # noqa: E402


def _make_dummy_target(var_name: str) -> CalibrationTarget:
    """Create a minimal CalibrationTarget for stubbing load_targets."""
    return CalibrationTarget(
        variable_name=var_name,
        years=np.array([1970, 1980, 1990, 2000], dtype=int),
        values=np.array([1.0, 2.0, 3.0, 4.0]),
        unit="test",
        weight=1.0,
        source="test",
        nrmsd_method="direct",
    )
