# tests/unit/test_databridge_validation.py
"""Tests for Task 2: DataBridge train/validation split."""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from pathlib import Path

from pyworldx.data.bridge import (
    CalibrationTarget,
    DataBridge,
    DataBridgeError,
)
from pyworldx.calibration.empirical import EmpiricalCalibrationReport


def _make_target(
    years: "np.ndarray[Any, Any]",
    values: "np.ndarray[Any, Any]",
    name: str = "POP",
) -> CalibrationTarget:
    return CalibrationTarget(
        variable_name=name,
        years=years,
        values=values,
        unit="persons",
        weight=1.0,
        source="test",
        nrmsd_method="direct",
    )


def _trivial_engine(
    params: dict[str, float],
) -> tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"]:
    time = np.arange(1900, 2101, dtype=float)
    scale = params.get("scale", 1.0)
    return {"POP": np.linspace(1.0, 3.0, len(time)) * scale}, time


# ── DataBridgeError tests ──────────────────────────────────────────────

def test_databridge_error_is_exception() -> None:
    """DataBridgeError must subclass Exception."""
    assert issubclass(DataBridgeError, Exception)


def test_load_targets_raises_for_missing_dir(tmp_path: Path) -> None:
    """load_targets() must raise DataBridgeError when aligned_dir doesn't exist."""
    bridge = DataBridge()
    missing = tmp_path / "does_not_exist"
    with pytest.raises(DataBridgeError, match="does_not_exist"):
        bridge.load_targets(missing)


# ── Train-window filtering tests ──────────────────────────────────────

def test_build_objective_with_train_window_filters_years() -> None:
    """build_objective with train_start/train_end filters target years before NRMSD."""
    bridge = DataBridge(normalize=False)
    # Target has 1950–2050 data
    years = np.arange(1950, 2051, dtype=int)
    values = np.ones(len(years), dtype=float)
    target = _make_target(years=years, values=values)

    eval_count: list[int] = []

    def counting_engine(
        params: dict[str, float],
    ) -> tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"]:
        eval_count.append(1)
        time = np.arange(1900, 2101, dtype=float)
        return {"POP": np.ones(len(time), dtype=float)}, time

    # With train window 1970–2010, objective uses only years 1970–2010
    obj = bridge.build_objective(
        [target], counting_engine, train_start=1970, train_end=2010
    )
    score = obj({"scale": 1.0})
    assert score == pytest.approx(0.0, abs=1e-10)  # perfect match on train years


def test_build_objective_without_train_window_uses_all_years() -> None:
    """Without train_start/train_end, all years are used (existing behaviour)."""
    bridge = DataBridge(normalize=False)
    years = np.arange(1950, 2051, dtype=int)
    values = np.ones(len(years), dtype=float)
    target = _make_target(years=years, values=values)
    obj = bridge.build_objective([target], _trivial_engine)
    # objective is callable and returns a float
    score = obj({"scale": 1.0})
    assert isinstance(score, float)


# ── calculate_validation_score tests ─────────────────────────────────

def test_calculate_validation_score_uses_holdout_years() -> None:
    """Validation score uses only years in [validate_start, validate_end]."""
    bridge = DataBridge(normalize=False)
    # Engine outputs 1.0 everywhere; target = 2.0 in 1970–2009, 1.0 in 2010–2023
    years = np.arange(1970, 2024, dtype=int)
    values = np.where(years < 2010, 2.0, 1.0).astype(float)
    target = _make_target(years=years, values=values)

    def constant_engine(
        params: dict[str, float],
    ) -> tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"]:
        time = np.arange(1900, 2101, dtype=float)
        return {"POP": np.ones(len(time), dtype=float)}, time

    # Engine always returns 1.0 → NRMSD in 2010–2023 = 0.0, NRMSD in 1970–2009 > 0
    result = bridge.calculate_validation_score(
        [target], constant_engine, {},
        validate_start=2010, validate_end=2023,
    )
    assert result.composite_nrmsd == pytest.approx(0.0, abs=1e-10)


def test_calculate_validation_score_returns_bridge_result() -> None:
    from pyworldx.data.bridge import BridgeResult
    bridge = DataBridge(normalize=False)
    years = np.arange(1970, 2024, dtype=int)
    values = np.ones(len(years), dtype=float)
    target = _make_target(years=years, values=values)
    result = bridge.calculate_validation_score(
        [target], _trivial_engine, {},
        validate_start=2010, validate_end=2023,
    )
    assert isinstance(result, BridgeResult)


# ── EmpiricalCalibrationReport new fields ─────────────────────────────

def test_empirical_report_has_validation_fields() -> None:
    """EmpiricalCalibrationReport must have validation_nrmsd and overfit_flagged."""
    report = EmpiricalCalibrationReport()
    assert hasattr(report, "validation_nrmsd")
    assert hasattr(report, "overfit_flagged")
    assert report.validation_nrmsd is None
    assert report.overfit_flagged is False


def test_clip_targets_drops_short_windows() -> None:
    """_clip_targets_to_window must drop targets with < 3 points after clipping."""
    bridge = DataBridge(normalize=False)
    # Target has only 2 years in the window [2028, 2029]
    years = np.arange(1970, 2030, dtype=int)
    values = np.ones(len(years), dtype=float)
    target = _make_target(years=years, values=values)
    clipped = bridge._clip_targets_to_window([target], start_year=2028, end_year=2029)
    assert len(clipped) == 0, "Target with 2 points after clip must be dropped"


def test_overfit_flagged_when_validation_degrades() -> None:
    """overfit_flagged must be True when validation NRMSD >> train NRMSD.

    Engine outputs 1.01 everywhere:
      - Train target = 1.0 → NRMSD ≈ 1% (small)
      - Validation target = 10.0 → NRMSD ≈ 800% (huge)
    degradation = 800%/1% - 1 >> 0.20, so overfit_flagged must be True.
    """
    bridge = DataBridge(normalize=False)

    def constant_engine(
        params: dict[str, float],
    ) -> tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"]:
        t = np.arange(1900, 2101, dtype=float)
        return {"POP": np.full(len(t), 1.01, dtype=float)}, t

    years = np.arange(1970, 2024, dtype=int)
    train_target = _make_target(years=years, values=np.ones(len(years), dtype=float))
    val_target = _make_target(years=years, values=np.full(len(years), 10.0, dtype=float))

    obj = bridge.build_objective([train_target], constant_engine, train_start=1970, train_end=2009)
    train_nrmsd = obj({})
    assert train_nrmsd > 0.0, "Train NRMSD must be positive (engine returns 1.01, target is 1.0)"

    val_result = bridge.calculate_validation_score(
        [val_target], constant_engine, {},
        validate_start=2010, validate_end=2023,
    )

    assert val_result.composite_nrmsd > train_nrmsd, (
        "Validation NRMSD (target=10.0, engine=1.01) must exceed train NRMSD (target=1.0, engine=1.01)"
    )
    degradation = val_result.composite_nrmsd / train_nrmsd - 1.0
    assert degradation > 0.20, f"Expected degradation > 20%, got {degradation:.2%}"


def test_empirical_runner_wires_validation_nrmsd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EmpiricalCalibrationRunner.run() with CrossValidationConfig must populate validation_nrmsd.

    Monkeypatches load_targets (bypasses Parquet store) and run_calibration_pipeline
    (bypasses Morris/NM/Sobol) so this test is fast and deterministic.
    """
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    from pyworldx.calibration.metrics import (
        CalibrationResult,
        CrossValidationConfig,
    )
    from pyworldx.calibration.parameters import ParameterRegistry
    from pyworldx.calibration.pipeline import PipelineReport
    import pyworldx.calibration.empirical as emp_module

    years = np.arange(1970, 2024, dtype=int)
    values = np.ones(len(years), dtype=float)
    fake_targets = [_make_target(years=years, values=values)]

    registry = ParameterRegistry()
    cv = CrossValidationConfig(
        train_start=1970, train_end=2009,
        validate_start=2010, validate_end=2023,
        overfit_threshold=0.20,
    )

    def engine_factory(
        params: dict[str, float],
    ) -> tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"]:
        t = np.arange(1900, 2101, dtype=float)
        return {"POP": np.ones(len(t), dtype=float)}, t

    # Stub calibration result — gives run() a non-None calibration to trigger validation block
    stub_calibration = CalibrationResult(
        parameters={},
        nrmsd_scores={},
        total_nrmsd=0.01,
        train_config=cv,
        iterations=1,
        converged=True,
    )
    stub_pipeline = PipelineReport(calibration=stub_calibration)
    monkeypatch.setattr(
        emp_module, "run_calibration_pipeline", lambda **kwargs: stub_pipeline
    )

    runner = EmpiricalCalibrationRunner(aligned_dir=tmp_path)
    monkeypatch.setattr(runner, "load_targets", lambda weights=None: fake_targets)

    report = runner.run(
        registry=registry,
        engine_factory=engine_factory,
        cross_val_config=cv,
    )
    assert report.validation_nrmsd is not None, (
        "run() must populate validation_nrmsd when cross_val_config is provided"
    )
    assert isinstance(report.validation_nrmsd, float)
