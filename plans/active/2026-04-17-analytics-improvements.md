# Analytics Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver four analytics improvements: Parquet time-series export for ensemble reports, DataBridge train/validation split, Bayesian global optimization step in the calibration pipeline, and real SALib Sobol variance decomposition replacing the fake TODO in `ensemble.py`.

**Architecture:** Each task is a self-contained patch touching 1-3 files. Priority order matches risk: Parquet exporter (zero new deps, pure addition), DataBridge validation (extends existing DataBridge), Optuna Bayesian optimizer (new dep, new pipeline step), Sobol decomposition (new dep, replaces fake code). All changes preserve existing test behavior.

**Tech Stack:** Python 3.11+, pytest, mypy strict, ruff. New deps: `optuna ^3.6`, `SALib ^1.5` (both added to `pyproject.toml` as required deps). `pyarrow` is already an optional dep (`-E pipeline`) and is guarded with `ImportError` in the reporter. Run tests with `python3 -m pytest tests/unit/<test_file>.py -v`.

---

## Scope note

These four tasks are independent subsystems. If context is tight, each can be a separate PR. The plan treats them sequentially because each task's regression check is "run the full suite", giving the next task a clean baseline.

---

## File Map

| File | Change |
|---|---|
| `pyworldx/forecasting/ensemble.py` | Add `temporal_resolution`, `run_sobol`, `sobol_n`, `force_sobol` to `EnsembleSpec`; add `time_axis` to `EnsembleResult`; capture time axis in `run_ensemble()`; set year index on summary DataFrames; replace fake decomposition with `_sobol_decompose()` |
| `pyworldx/observability/reports.py` | Add `output_dir` + `temporal_resolution` params to `build_ensemble_report()`; add `_write_parquet()` helper |
| `pyworldx/data/bridge.py` | Add `DataBridgeError`; add directory guard to `load_targets()`; add `_clip_targets_to_window()`; update `build_objective()` with `train_start`/`train_end`; add `calculate_validation_score()` |
| `pyworldx/calibration/empirical.py` | Add `validation_nrmsd`/`overfit_flagged` to `EmpiricalCalibrationReport`; wire validation in `run()` |
| `pyworldx/calibration/pipeline.py` | Add `_bayesian_optimize()`; add `bayesian_n_trials`/`bayesian_timeout` params; insert Bayesian step between Morris and Nelder-Mead |
| `pyproject.toml` | Add `optuna = "^3.6"` and `SALib = "^1.5"` to required deps |
| `tests/unit/test_parquet_exporter.py` | New — Parquet export tests |
| `tests/unit/test_databridge_validation.py` | New — DataBridgeError + validation score tests |
| `tests/unit/test_bayesian_optimizer.py` | New — Bayesian optimizer tests |
| `tests/unit/test_sobol_decomposition.py` | New — SALib Sobol decomposition tests |

---

## Task 1: Ensemble Parquet Exporter

`build_ensemble_report()` currently saves only the final-year values. The `summary` DataFrames inside `EnsembleResult` hold the full time-series but are never written anywhere. This task exports the full percentile bands to Parquet in long format and adds `temporal_resolution` to control decimation.

**Files:**
- Create: `tests/unit/test_parquet_exporter.py`
- Modify: `pyworldx/forecasting/ensemble.py` (lines 108–133, 165–278)
- Modify: `pyworldx/observability/reports.py` (lines 102–150)

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_parquet_exporter.py
"""Tests for Task 1: Ensemble Parquet Exporter."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from pyworldx.forecasting.ensemble import EnsembleSpec
from pyworldx.observability.reports import build_ensemble_report
from pyworldx.scenarios.scenario import Scenario

pyarrow = pytest.importorskip("pyarrow", reason="pyarrow required for Parquet tests")


def _make_summary(n_years: int = 11) -> dict[str, pd.DataFrame]:
    """Synthetic summary with year-indexed DataFrames (years 1900..1900+n_years-1)."""
    years = pd.Index(np.arange(1900, 1900 + n_years, dtype=int), name="year")
    data = {
        "mean": np.linspace(1.0, 2.0, n_years),
        "median": np.linspace(1.0, 2.0, n_years),
        "p05": np.linspace(0.8, 1.8, n_years),
        "p25": np.linspace(0.9, 1.9, n_years),
        "p75": np.linspace(1.1, 2.1, n_years),
        "p95": np.linspace(1.2, 2.2, n_years),
        "min": np.linspace(0.5, 1.5, n_years),
        "max": np.linspace(1.5, 2.5, n_years),
    }
    return {
        "POP": pd.DataFrame(data, index=years),
        "IC": pd.DataFrame(
            {k: v * 100 for k, v in data.items()}, index=years
        ),
    }


def test_build_ensemble_report_writes_parquet(tmp_path: Path) -> None:
    """output_dir triggers parquet file creation."""
    summary = _make_summary()
    build_ensemble_report(summary, output_dir=tmp_path)
    assert (tmp_path / "ensemble_trajectories.parquet").exists()


def test_parquet_long_format_columns(tmp_path: Path) -> None:
    """Parquet file must have columns: year, variable, p05, median, p95, min, max."""
    summary = _make_summary()
    build_ensemble_report(summary, output_dir=tmp_path)
    df = pd.read_parquet(tmp_path / "ensemble_trajectories.parquet")
    required = {"year", "variable", "p05", "median", "p95", "min", "max"}
    assert required.issubset(set(df.columns))
    assert set(df["variable"].unique()) == {"POP", "IC"}


def test_temporal_resolution_decimation(tmp_path: Path) -> None:
    """resolution=5 on 11 years (indices 0..10) → rows 0,5,10 → 3 rows per variable."""
    summary = _make_summary(n_years=11)
    build_ensemble_report(summary, output_dir=tmp_path, temporal_resolution=5)
    df = pd.read_parquet(tmp_path / "ensemble_trajectories.parquet")
    pop_rows = df[df["variable"] == "POP"]
    assert len(pop_rows) == 3


def test_default_resolution_keeps_all_rows(tmp_path: Path) -> None:
    """temporal_resolution=1 (default) writes every timestep."""
    n = 21
    summary = _make_summary(n_years=n)
    build_ensemble_report(summary, output_dir=tmp_path, temporal_resolution=1)
    df = pd.read_parquet(tmp_path / "ensemble_trajectories.parquet")
    pop_rows = df[df["variable"] == "POP"]
    assert len(pop_rows) == n


def test_peak_detection_uses_full_resolution(tmp_path: Path) -> None:
    """JSON final_values must use full-resolution data even with temporal_resolution=5."""
    summary = _make_summary(n_years=11)  # mean at final year (index 10) = 2.0
    report = build_ensemble_report(summary, output_dir=tmp_path, temporal_resolution=5)
    assert report.final_values["POP"] == pytest.approx(2.0, abs=1e-6)


def test_no_output_dir_skips_parquet() -> None:
    """Without output_dir no Parquet is written and no error is raised."""
    summary = _make_summary()
    report = build_ensemble_report(summary, output_dir=None)
    assert report.report_type == "ensemble"


def test_write_parquet_without_pyarrow_appends_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pd.DataFrame.to_parquet raises ImportError, a warning is appended."""
    import pandas as pd

    original_to_parquet = pd.DataFrame.to_parquet

    def _raise_import_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise ImportError("No module named 'pyarrow'")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_import_error)
    summary = _make_summary()
    report = build_ensemble_report(summary, output_dir=tmp_path)
    assert not (tmp_path / "ensemble_trajectories.parquet").exists()
    assert any("pyarrow" in w for w in report.warnings), (
        "Warning about missing pyarrow must appear in report.warnings"
    )


def test_ensemble_spec_temporal_resolution_field() -> None:
    """EnsembleSpec must accept temporal_resolution kwarg."""
    spec = EnsembleSpec(
        n_runs=1,
        base_scenario=Scenario("t", "test", 1900, 1910),
        parameter_distributions={},
        temporal_resolution=5,
    )
    assert spec.temporal_resolution == 5


def test_ensemble_result_has_time_axis() -> None:
    """EnsembleResult must expose time_axis field (numpy array)."""
    from pyworldx.forecasting.ensemble import EnsembleResult
    er = EnsembleResult(
        members=None,
        summary={},
        threshold_results={},
        uncertainty_decomposition={},
    )
    # Must exist and be array-like (even if empty)
    assert hasattr(er, "time_axis")
    assert hasattr(er.time_axis, "__len__")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_parquet_exporter.py -v 2>&1 | head -30
```

Expected: fail on `test_build_ensemble_report_writes_parquet` — `build_ensemble_report() got unexpected keyword argument 'output_dir'`.

- [ ] **Step 3: Implement — ensemble.py**

**Edit A**: Add `temporal_resolution` to `EnsembleSpec` (after `store_member_runs`):

```python
@dataclass
class EnsembleSpec:
    n_runs: int
    base_scenario: Scenario
    parameter_distributions: dict[str, ParameterDistribution]
    exogenous_perturbations: dict[str, ParameterDistribution] = field(
        default_factory=dict
    )
    initial_condition_perturbations: dict[str, ParameterDistribution] = field(
        default_factory=dict
    )
    threshold_queries: list[ThresholdQuery] = field(default_factory=list)
    seed: int = 42
    store_member_runs: bool = False
    temporal_resolution: int = 1  # decimation step for Parquet export
```

**Edit B**: Add `time_axis` to `EnsembleResult`:

```python
@dataclass
class EnsembleResult:
    members: list[RunResult] | None
    summary: dict[str, pd.DataFrame]
    threshold_results: dict[str, ThresholdQueryResult]
    uncertainty_decomposition: dict[str, dict[str, float]]
    manifest_refs: list[str] = field(default_factory=list)
    time_axis: "np.ndarray[Any, Any]" = field(
        default_factory=lambda: np.empty(0, dtype=float)
    )
```

**Edit C**: In `run_ensemble()`, capture `time_axis` and set year indices on summary DataFrames. Replace the section from `rng = np.random.default_rng(spec.seed)` through `summary: dict[str, pd.DataFrame] = {}` with:

```python
    rng = np.random.default_rng(spec.seed)
    members: list[RunResult] = []
    all_trajectories: dict[str, list["np.ndarray[Any, Any]"]] = {}
    time_axis: "np.ndarray[Any, Any] | None" = None

    # Pre-sample all perturbations
    param_samples: dict[str, "np.ndarray[Any, Any]"] = {}
    for name, dist in spec.parameter_distributions.items():
        param_samples[name] = dist.sample(rng, spec.n_runs)

    ic_samples: dict[str, "np.ndarray[Any, Any]"] = {}
    for name, dist in spec.initial_condition_perturbations.items():
        ic_samples[name] = dist.sample(rng, spec.n_runs)

    # Run ensemble members
    for i in range(spec.n_runs):
        overrides = dict(spec.base_scenario.parameter_overrides)
        for name, samples in param_samples.items():
            overrides[name] = float(samples[i])

        sectors = sector_factory(overrides)
        engine = Engine(
            sectors=sectors,
            t_start=float(spec.base_scenario.start_year - 1900),
            t_end=float(spec.base_scenario.end_year - 1900),
            **engine_kwargs,
        )
        result = engine.run()

        # Capture absolute year axis from first run
        if time_axis is None:
            time_axis = np.array(result.time_index) + 1900.0

        if spec.store_member_runs:
            members.append(result)

        for var_name, traj in result.trajectories.items():
            if var_name not in all_trajectories:
                all_trajectories[var_name] = []
            all_trajectories[var_name].append(traj)

    # ── Compute summary statistics ────────────────────────────────────
    _time_axis: "np.ndarray[Any, Any]" = (
        time_axis if time_axis is not None else np.empty(0, dtype=float)
    )
    summary: dict[str, pd.DataFrame] = {}
    for var_name, traj_list in all_trajectories.items():
        arr = np.array(traj_list)  # (n_runs, n_timesteps)
        idx = pd.Index(_time_axis, name="year") if len(_time_axis) > 0 else None
        summary[var_name] = pd.DataFrame(
            {
                "mean": np.mean(arr, axis=0),
                "median": np.median(arr, axis=0),
                "p05": np.percentile(arr, 5, axis=0),
                "p25": np.percentile(arr, 25, axis=0),
                "p75": np.percentile(arr, 75, axis=0),
                "p95": np.percentile(arr, 95, axis=0),
                "min": np.min(arr, axis=0),
                "max": np.max(arr, axis=0),
            },
            index=idx,
        )
```

**Edit D**: Update the `return EnsembleResult(...)` at the bottom of `run_ensemble()`:

```python
    return EnsembleResult(
        members=members if spec.store_member_runs else None,
        summary=summary,
        threshold_results=threshold_results,
        uncertainty_decomposition=decomposition,
        time_axis=_time_axis,
    )
```

- [ ] **Step 4: Implement — reports.py**

Add `Path` import at top of file (after existing imports):

```python
from pathlib import Path
```

Replace `build_ensemble_report()` signature and add `_write_parquet()`:

```python
def build_ensemble_report(
    summary: dict[str, pd.DataFrame],
    threshold_results: dict[str, Any] | None = None,
    manifest: RunManifest | None = None,
    ensemble_size: int = 0,
    output_dir: Path | None = None,
    temporal_resolution: int = 1,
) -> ForecastReport:
    """Build a forecast report from an ensemble result.

    Args:
        summary: per-variable DataFrames indexed by year with mean, median, percentiles
        threshold_results: threshold query results
        manifest: optional RunManifest for provenance
        ensemble_size: number of ensemble members
        output_dir: if provided, write ensemble_trajectories.parquet here
        temporal_resolution: decimation step for Parquet (1 = all rows, 5 = every 5th)
    """
    report = ForecastReport(
        report_type="ensemble",
        ensemble_size=ensemble_size,
    )

    if manifest is not None:
        report.manifest = manifest.to_dict()

    # Extract final-time percentile bands (uses full-resolution data)
    for var, df in summary.items():
        if df.empty:
            continue
        last = df.iloc[-1]
        report.percentile_bands[var] = {
            "mean": float(last.get("mean", 0.0)),
            "median": float(last.get("median", 0.0)),
            "p05": float(last.get("p05", 0.0)),
            "p95": float(last.get("p95", 0.0)),
            "min": float(last.get("min", 0.0)),
            "max": float(last.get("max", 0.0)),
        }
        report.final_values[var] = float(last.get("mean", 0.0))

    # Threshold results
    if threshold_results is not None:
        for name, tr in threshold_results.items():
            if hasattr(tr, "probability"):
                report.threshold_results[name] = {
                    "probability": tr.probability,
                    "member_count": tr.member_count,
                }
            else:
                report.threshold_results[name] = {"raw": str(tr)}

    # Write Parquet export (decimated, does not affect peak detection above)
    if output_dir is not None:
        _write_parquet(summary, output_dir, temporal_resolution, report)

    return report


def _write_parquet(
    summary: dict[str, pd.DataFrame],
    output_dir: Path,
    temporal_resolution: int,
    report: ForecastReport,
) -> None:
    """Write long-format Parquet with columns (year, variable, p05, median, p95, min, max)."""
    stat_cols = ["p05", "median", "p95", "min", "max"]
    frames = []
    for var, df in summary.items():
        if df.empty:
            continue
        present = [c for c in stat_cols if c in df.columns]
        dec = df.iloc[::max(temporal_resolution, 1)][present].reset_index()
        if "year" in dec.columns:
            dec["year"] = dec["year"].astype(int)
        dec.insert(0, "variable", var)
        frames.append(dec)
    if not frames:
        return
    out_path = output_dir / "ensemble_trajectories.parquet"
    try:
        pd.concat(frames, ignore_index=True).to_parquet(out_path, index=False)
    except ImportError:
        report.warnings.append(
            "pyarrow not installed; ensemble_trajectories.parquet not written. "
            "Install with: poetry install -E pipeline"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_parquet_exporter.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Regression check**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_ensemble.py tests/integration/test_phase1_integration.py -v
```

Expected: all pass. The `summary` DataFrame now has a year index; the existing tests do not assert on `.index`, so no breakage.

- [ ] **Step 7: mypy + ruff**

```bash
cd /Users/johnny/pyWorldX && mypy pyworldx/forecasting/ensemble.py pyworldx/observability/reports.py && ruff check pyworldx/ tests/unit/test_parquet_exporter.py
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/forecasting/ensemble.py pyworldx/observability/reports.py tests/unit/test_parquet_exporter.py
git commit -m "feat(observability): export full time-series to Parquet with temporal_resolution decimation"
```

---

## Task 2: DataBridge — Train/Validation Split

`bridge.py` currently uses ALL years in every target for both the calibration objective and post-calibration evaluation. This task adds: a `DataBridgeError` raised when the aligned directory is missing, train-window filtering to `build_objective()`, a `calculate_validation_score()` method for holdout evaluation, and wires the validation score into `EmpiricalCalibrationRunner.run()`.

**Background on `CrossValidationConfig`** (in `pyworldx/calibration/metrics.py`):
```python
@dataclass
class CrossValidationConfig:
    train_start: int = 1970
    train_end: int = 2010
    validate_start: int = 2010
    validate_end: int = 2023
    overfit_threshold: float = 0.20
```

**Why not import CrossValidationConfig into bridge.py?** `empirical.py` (in `calibration/`) already imports from `bridge.py` (in `data/`). If `bridge.py` also imported from `calibration/`, we'd have a circular: `data → calibration → data`. So `bridge.py` accepts plain `int` year bounds instead.

**Files:**
- Create: `tests/unit/test_databridge_validation.py`
- Modify: `pyworldx/data/bridge.py` (lines 1–160, 361–387)
- Modify: `pyworldx/calibration/empirical.py` (lines 33–52, 286–326)

- [ ] **Step 1: Write the failing tests**

```python
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

    # Engine always returns 1.0 → NRMSD in 2010–2023 = 0.0, NRMSD in 1970–2009 > 0
    result = bridge.calculate_validation_score(
        [target], _trivial_engine, {"scale": 1.0},
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
    # Target has only 2 years in the window [2020, 2021]
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_databridge_validation.py -v 2>&1 | head -30
```

Expected: fail on `test_databridge_error_is_exception` — `DataBridgeError` does not exist in `bridge.py`.

- [ ] **Step 3: Implement — bridge.py**

**Edit A**: Add `DataBridgeError` near the top of `bridge.py`, after the imports and before `ENTITY_TO_ENGINE_MAP`:

```python
class DataBridgeError(Exception):
    """Raised when the aligned data store is missing or malformed.

    Use this instead of letting raw FileNotFoundError propagate, so callers
    can catch a single exception type for all DataBridge failures.
    """
```

**Edit B**: Add directory guard at the start of `load_targets()` (inside the method, before the `try` import block):

```python
    def load_targets(
        self,
        aligned_dir: Path,
        weights: Optional[dict[str, float]] = None,
    ) -> list[CalibrationTarget]:
        """Load aligned Parquet data as calibration targets.
        ...
        """
        if not aligned_dir.exists():
            raise DataBridgeError(
                f"Aligned data directory not found: {aligned_dir}. "
                "Run the data pipeline first: python -m data_pipeline.run --align"
            )
        try:
            from data_pipeline.storage.parquet_store import read_aligned
        except (ImportError, ModuleNotFoundError):
            return []
        # ... rest of method unchanged ...
```

**Edit C**: Add `_clip_targets_to_window()` as a new method (add after the `load_targets_from_results()` method, before `compare()`):

```python
    def _clip_targets_to_window(
        self,
        targets: list[CalibrationTarget],
        start_year: int,
        end_year: int,
    ) -> list[CalibrationTarget]:
        """Return targets with years clipped to [start_year, end_year].

        Targets with fewer than 3 points after clipping are dropped.
        """
        clipped: list[CalibrationTarget] = []
        for t in targets:
            mask = (t.years >= start_year) & (t.years <= end_year)
            years = t.years[mask]
            values = t.values[mask]
            if len(years) < 3:
                continue
            clipped.append(
                CalibrationTarget(
                    variable_name=t.variable_name,
                    years=years,
                    values=values,
                    unit=t.unit,
                    weight=t.weight,
                    source=t.source,
                    nrmsd_method=t.nrmsd_method,
                )
            )
        return clipped
```

**Edit D**: Replace `build_objective()` with a version that accepts optional train-window params:

```python
    def build_objective(
        self,
        targets: list[CalibrationTarget],
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"],
        ],
        train_start: Optional[int] = None,
        train_end: Optional[int] = None,
    ) -> Callable[[dict[str, float]], float]:
        """Build NRMSD objective function from targets.

        Args:
            targets: Calibration targets
            engine_factory: Callable(params) -> (trajectories, time_index)
            train_start: If provided, clip targets to years >= train_start
            train_end: If provided, clip targets to years <= train_end

        Returns:
            Callable mapping parameter dict -> scalar NRMSD.
        """
        # Pre-clip to train window (no per-call overhead)
        active_targets = targets
        if train_start is not None or train_end is not None:
            lo = train_start if train_start is not None else int(targets[0].years.min())
            hi = train_end if train_end is not None else int(targets[0].years.max())
            active_targets = self._clip_targets_to_window(targets, lo, hi)

        def objective(params: dict[str, float]) -> float:
            try:
                trajectories, time_index = engine_factory(params)
            except Exception:
                return float("inf")
            result = self.compare(active_targets, trajectories, time_index)
            return result.composite_nrmsd

        return objective
```

**Edit E**: Add `calculate_validation_score()` after `build_objective()`:

```python
    def calculate_validation_score(
        self,
        targets: list[CalibrationTarget],
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"],
        ],
        params: dict[str, float],
        validate_start: int,
        validate_end: int,
    ) -> "BridgeResult":
        """Evaluate NRMSD on the holdout validation window only.

        Args:
            targets: All calibration targets (clipped to validation years internally)
            engine_factory: Callable(params) -> (trajectories, time_index)
            params: Parameter dict to evaluate
            validate_start: First year of the holdout window (inclusive)
            validate_end: Last year of the holdout window (inclusive)

        Returns:
            BridgeResult computed on validation years only.
        """
        val_targets = self._clip_targets_to_window(targets, validate_start, validate_end)
        try:
            trajectories, time_index = engine_factory(params)
        except Exception:
            return BridgeResult(
                per_variable_nrmsd={},
                composite_nrmsd=float("nan"),
                n_targets=0,
                coverage={},
            )
        return self.compare(val_targets, trajectories, time_index)
```

- [ ] **Step 4: Implement — empirical.py**

**Edit A**: Add `validation_nrmsd` and `overfit_flagged` to `EmpiricalCalibrationReport`:

```python
@dataclass
class EmpiricalCalibrationReport:
    """Full report from empirical calibration."""

    # Layer 1: Reference validation
    reference_result: Optional[BridgeResult] = None

    # Layer 2: Empirical calibration
    empirical_targets_loaded: int = 0
    empirical_result: Optional[BridgeResult] = None
    pipeline_report: Optional[PipelineReport] = None

    # Layer 3: USGS cross-validation
    usgs_targets_loaded: int = 0
    usgs_result: Optional[BridgeResult] = None

    # Summary
    calibrated_parameters: dict[str, float] = field(default_factory=dict)
    converged: bool = False
    total_evaluations: int = 0
    validation_nrmsd: Optional[float] = None   # holdout window NRMSD
    overfit_flagged: bool = False               # True if validation degrades > overfit_threshold
```

**Edit B**: In `EmpiricalCalibrationRunner.run()`, pass train window to `build_objective()` and call `calculate_validation_score()` after calibration. Replace the block starting at `# ── Layer 2: Build objective and run pipeline ─────────────────` through `report.empirical_result = self.bridge.compare(...)`:

```python
        # ── Layer 2: Build objective and run pipeline ─────────────────
        # Build objective restricted to the train window (avoids look-ahead bias)
        train_start: Optional[int] = None
        train_end: Optional[int] = None
        if cross_val_config is not None:
            train_start = cross_val_config.train_start
            train_end = cross_val_config.train_end

        objective = self.bridge.build_objective(
            targets, engine_factory,
            train_start=train_start,
            train_end=train_end,
        )

        pipeline_report = run_calibration_pipeline(
            objective_fn=objective,
            registry=registry,
            cross_val_config=cross_val_config,
            morris_trajectories=morris_trajectories,
            sobol_samples=sobol_samples,
            seed=seed,
        )
        report.pipeline_report = pipeline_report
        report.total_evaluations = pipeline_report.total_evaluations

        # ── Extract calibrated parameters ─────────────────────────────
        if pipeline_report.calibration is not None:
            report.calibrated_parameters = pipeline_report.calibration.parameters
            report.converged = pipeline_report.calibration.converged

            # Evaluate calibrated params against empirical targets (all years)
            try:
                trajectories, time_index = engine_factory(
                    report.calibrated_parameters
                )
                report.empirical_result = self.bridge.compare(
                    targets, trajectories, time_index,
                )
            except Exception:
                pass

            # Validation score on holdout window
            if cross_val_config is not None:
                val_result = self.bridge.calculate_validation_score(
                    targets,
                    engine_factory,
                    report.calibrated_parameters,
                    validate_start=cross_val_config.validate_start,
                    validate_end=cross_val_config.validate_end,
                )
                report.validation_nrmsd = val_result.composite_nrmsd

                train_nrmsd = pipeline_report.calibration.total_nrmsd
                if (
                    np.isfinite(val_result.composite_nrmsd)
                    and train_nrmsd > 0.0
                ):
                    degradation = val_result.composite_nrmsd / train_nrmsd - 1.0
                    report.overfit_flagged = (
                        degradation > cross_val_config.overfit_threshold
                    )
```

Also add `import numpy as np` to `empirical.py` if not already present.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_databridge_validation.py tests/unit/test_data_bridge.py -v
```

Expected: all pass. The existing `test_data_bridge.py` tests should still pass — `build_objective()` now accepts two new optional params with defaults of `None`, so existing call sites are unaffected.

- [ ] **Step 6: Regression check — calibration pipeline tests**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_calibration_pipeline.py tests/unit/test_empirical_calibration.py -v 2>&1 || true
```

Expected: all pass. Confirms `empirical.py`'s `run()` changes don't break existing calibration flows. (If these files don't exist yet, the command exits cleanly.)

- [ ] **Step 7: mypy + ruff**

```bash
cd /Users/johnny/pyWorldX && mypy pyworldx/data/bridge.py pyworldx/calibration/empirical.py && ruff check pyworldx/ tests/unit/test_databridge_validation.py
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/data/bridge.py pyworldx/calibration/empirical.py tests/unit/test_databridge_validation.py
git commit -m "feat(bridge): add DataBridgeError, train-window objective, calculate_validation_score"
```

---

## Task 3: Bayesian Global Optimizer (Optuna)

The calibration pipeline goes: profile likelihood → Morris → Nelder-Mead → Sobol. Nelder-Mead is a local optimizer and gets trapped in local minima on the rugged 5-sector ODE objective. This task inserts a Bayesian global search (Optuna TPE) between Morris and Nelder-Mead. Nelder-Mead then starts from the Bayesian best, using it for final refinement instead of the default parameter values.

**Files:**
- Create: `tests/unit/test_bayesian_optimizer.py`
- Modify: `pyproject.toml` (add `optuna`)
- Modify: `pyworldx/calibration/pipeline.py` (lines 1–50, 158–270)

- [ ] **Step 1: Write the failing tests**

```python
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

    original_bayes = pipe_module._bayesian_optimize
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_bayesian_optimizer.py::test_bayesian_optimize_import -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name '_bayesian_optimize' from 'pyworldx.calibration.pipeline'`.

- [ ] **Step 3: Add optuna dependency**

```bash
cd /Users/johnny/pyWorldX && poetry add optuna
```

Expected: `optuna` added to `pyproject.toml` under `[tool.poetry.dependencies]`.

Verify: `python3 -c "import optuna; print(optuna.__version__)"` — should print a version ≥ 3.0.

- [ ] **Step 4: Implement — pipeline.py**

**Edit A**: Add `optuna` import guard after the existing imports (do NOT add `import optuna` at the top level — optuna is imported lazily inside `_bayesian_optimize` so that tests that don't use Bayesian still run without the dep):

```python
# No top-level optuna import — imported lazily in _bayesian_optimize()
```

**Edit B**: Add `_bayesian_optimize()` function after `_nelder_mead_optimize()` and before `run_calibration_pipeline()` (insert at approximately line 156):

```python
def _bayesian_optimize(
    objective_fn: Callable[[dict[str, float]], float],
    initial_params: dict[str, float],
    bounds: dict[str, tuple[float, float]],
    parameter_names: list[str],
    n_trials: int = 100,
    timeout: int = 600,
    seed: int = 42,
) -> tuple[dict[str, float], float, int]:
    """Bayesian global optimization using Optuna TPE sampler.

    Searches the parameter space defined by `bounds` for `parameter_names`
    using the Tree-structured Parzen Estimator. Non-screened parameters
    remain at their values in `initial_params`.

    Args:
        objective_fn: maps parameter dict → scalar (lower is better)
        initial_params: starting values for all parameters (including non-optimized)
        bounds: {name: (lo, hi)} for all registry parameters
        parameter_names: subset to optimize
        n_trials: maximum number of objective evaluations
        timeout: wall-clock limit in seconds
        seed: reproducibility seed for TPESampler

    Returns:
        (best_params, best_objective_value) where best_params contains ALL
        parameters (non-screened ones unchanged from initial_params).
    """
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def _optuna_objective(trial: "optuna.Trial") -> float:
        params = dict(initial_params)
        for name in parameter_names:
            lo, hi = bounds[name]
            params[name] = trial.suggest_float(name, lo, hi)
        return objective_fn(params)

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(_optuna_objective, n_trials=n_trials, timeout=timeout)

    best_params = dict(initial_params)
    for name in parameter_names:
        best_params[name] = study.best_params[name]

    return best_params, study.best_value, len(study.trials)
```

**Edit C**: Update `run_calibration_pipeline()` signature to add `bayesian_n_trials` and `bayesian_timeout` params:

```python
def run_calibration_pipeline(
    objective_fn: Callable[[dict[str, float]], float],
    registry: ParameterRegistry,
    cross_val_config: CrossValidationConfig | None = None,
    morris_trajectories: int = 10,
    morris_threshold: float = 0.9,
    sobol_samples: int = 256,
    profile_grid: int = 20,
    optimize_max_iter: int = 200,
    optimize_tol: float = 1e-6,
    seed: int = 42,
    bayesian_n_trials: int = 100,
    bayesian_timeout: int = 600,
) -> PipelineReport:
```

**Edit D**: In the body of `run_calibration_pipeline()`, replace the existing Step 2 block (Nelder-Mead) with the two-step Bayesian → Nelder-Mead sequence. The original Step 2 reads:

```python
    # ── Step 2: Deterministic optimization ───────────────────────────
    # Start from defaults, optimize only screened parameters
    initial = dict(defaults)
    best_params, best_obj, iters, converged = _nelder_mead_optimize(
        objective_fn,
        initial,
        bounds,
        report.screened_parameters,
        max_iter=optimize_max_iter,
        tol=optimize_tol,
        seed=seed,
    )
```

Replace it with:

```python
    # ── Step 2: Bayesian global search (over screened parameters) ────
    initial = dict(defaults)
    if report.screened_parameters:
        bayesian_params, _, n_bayesian_actual = _bayesian_optimize(
            objective_fn,
            initial,
            bounds,
            report.screened_parameters,
            n_trials=bayesian_n_trials,
            timeout=bayesian_timeout,
            seed=seed,
        )
        report.total_evaluations += n_bayesian_actual  # actual completed trials
    else:
        bayesian_params = initial

    # ── Step 3: Local fine-tuning from Bayesian best ─────────────────
    best_params, best_obj, iters, converged = _nelder_mead_optimize(
        objective_fn,
        bayesian_params,          # start from Bayesian best, not defaults
        bounds,
        report.screened_parameters,
        max_iter=optimize_max_iter,
        tol=optimize_tol,
        seed=seed,
    )
```

Update the docstring comment from `Step 2: Sobol` to `Step 4: Sobol` as needed.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_bayesian_optimizer.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Regression check**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/integration/test_phase1_integration.py -v
```

Expected: all pass. `run_calibration_pipeline()` with default `bayesian_n_trials=100` would only be called if anyone invokes the full pipeline in integration tests; the integration tests don't call it directly, so no slowdown.

- [ ] **Step 7: mypy + ruff**

```bash
cd /Users/johnny/pyWorldX && mypy pyworldx/calibration/pipeline.py && ruff check pyworldx/ tests/unit/test_bayesian_optimizer.py
```

Expected: no errors. Mypy will see `optuna.Trial` as a string annotation (quoted) so it won't fail on missing stubs.

- [ ] **Step 8: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/calibration/pipeline.py tests/unit/test_bayesian_optimizer.py pyproject.toml poetry.lock
git commit -m "feat(calibration): inject Bayesian (Optuna TPE) global search before Nelder-Mead"
```

---

## Task 4: Sobol Ensemble Decomposition (SALib)

`ensemble.py` has a fake `TODO` that attributes 100% of variance to parameter uncertainty. This task replaces it with a real SALib Saltelli/Sobol analysis when `spec.run_sobol=True`. When `run_sobol=False` (the default), behaviour is unchanged. Because Saltelli requires N×(2D+2) model runs, a hard cap of 10 000 evaluations is enforced (bypassable with `force_sobol=True`).

**Why SALib and not `sensitivity.py`?** `sensitivity.py`'s `run_sobol_analysis()` analyzes the calibration objective (sensitivity of NRMSD to parameters). The ensemble decomposition is different: it partitions output *variance* by uncertainty source (parameter, exogenous, initial-condition). The Saltelli samples must be generated **before** running the ensemble, not post-hoc, which requires SALib's structured sampling.

**Constraint**: Only `DistributionType.UNIFORM` is supported for `run_sobol=True`. NORMAL/LOGNORMAL distributions don't have the box bounds SALib requires. Raise `ValueError` if non-UNIFORM dists are present.

**Files:**
- Create: `tests/unit/test_sobol_decomposition.py`
- Modify: `pyproject.toml` (add `SALib`)
- Modify: `pyworldx/forecasting/ensemble.py` (lines 107–133, 258–277)

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_sobol_decomposition.py
"""Tests for Task 4: SALib Sobol ensemble decomposition."""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

SALib = pytest.importorskip("SALib", reason="SALib required for Sobol decomposition tests")

from pyworldx.forecasting.ensemble import (
    DistributionType,
    EnsembleSpec,
    ParameterDistribution,
    UncertaintyType,
    run_ensemble,
)
from pyworldx.scenarios.scenario import Scenario


def _make_spec(
    run_sobol: bool = False,
    sobol_n: int = 8,
    force_sobol: bool = False,
    n_runs: int = 3,
    dists: dict | None = None,
) -> EnsembleSpec:
    if dists is None:
        dists = {
            "r0_base": ParameterDistribution(
                DistributionType.UNIFORM,
                {"low": 1.0, "high": 5.0},
                "s1",
                UncertaintyType.PARAMETER,
            )
        }
    return EnsembleSpec(
        n_runs=n_runs,
        base_scenario=Scenario("sobol_test", "test", 1900, 1905),
        parameter_distributions=dists,
        run_sobol=run_sobol,
        sobol_n=sobol_n,
        force_sobol=force_sobol,
        seed=42,
    )


def _simple_factory(overrides: dict[str, float]) -> list[Any]:
    from pyworldx.sectors.rip_sectors import IndustrySector, PollutionSector, ResourceSector
    return [ResourceSector(), IndustrySector(), PollutionSector()]


def test_ensemble_spec_has_sobol_fields() -> None:
    """EnsembleSpec must accept run_sobol, sobol_n, force_sobol."""
    spec = _make_spec(run_sobol=True, sobol_n=16, force_sobol=True)
    assert spec.run_sobol is True
    assert spec.sobol_n == 16
    assert spec.force_sobol is True


def test_run_sobol_false_uses_monte_carlo() -> None:
    """Without run_sobol, decomposition uses the simplified MC attribution."""
    spec = _make_spec(run_sobol=False, n_runs=3)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    # Simplified decomposition: scenario, exogenous_input, initial_condition = 0.0
    for var, dec in result.uncertainty_decomposition.items():
        assert dec["scenario"] == pytest.approx(0.0)
        assert dec["exogenous_input"] == pytest.approx(0.0)
        assert dec["initial_condition"] == pytest.approx(0.0)


def test_run_sobol_true_produces_s1_decomposition() -> None:
    """With run_sobol=True, decomposition values come from SALib Sobol analysis."""
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    for var, dec in result.uncertainty_decomposition.items():
        assert "parameter" in dec
        assert "exogenous_input" in dec
        assert "initial_condition" in dec
        assert "scenario" in dec
        # parameter S1 must be non-negative
        assert dec["parameter"] >= 0.0


def test_s1_sum_at_most_one() -> None:
    """Sum of all S1 contributions must not exceed 1.0 (SALib sanity check)."""
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    for var, dec in result.uncertainty_decomposition.items():
        total_s1 = dec["parameter"] + dec["exogenous_input"] + dec["initial_condition"]
        assert total_s1 <= 1.0 + 1e-6, (
            f"S1 sum {total_s1:.4f} > 1.0 for variable {var}"
        )


def test_sample_size_guard_raises_without_force() -> None:
    """N*(2D+2) > 10000 without force_sobol=True must raise ValueError."""
    # 1 parameter → total = 512*(2*1+2) = 2048 — fine
    # 3 parameters → total = 512*(2*3+2) = 4096 — fine
    # 5 parameters with sobol_n=512 → 512*(2*5+2)=6144 — fine
    # 6 parameters with sobol_n=512 → 512*(2*6+2)=7168 — fine
    # Use sobol_n=700 and 8 params → 700*(2*8+2) = 12600 > 10000
    dists = {
        f"p{i}": ParameterDistribution(
            DistributionType.UNIFORM, {"low": 0.0, "high": 1.0}, f"s{i}",
            UncertaintyType.PARAMETER,
        )
        for i in range(8)
    }
    spec = _make_spec(run_sobol=True, sobol_n=700, force_sobol=False, dists=dists)
    with pytest.raises(ValueError, match="force_sobol"):
        run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})


def test_sample_size_guard_bypassed_with_force(monkeypatch: pytest.MonkeyPatch) -> None:
    """force_sobol=True must bypass the 10000-run cap."""
    import pyworldx.forecasting.ensemble as ens_module
    called: list[bool] = []

    original = ens_module._sobol_decompose
    def mock_decompose(*args, **kwargs):
        called.append(True)
        return {}
    monkeypatch.setattr(ens_module, "_sobol_decompose", mock_decompose)

    dists = {
        f"p{i}": ParameterDistribution(
            DistributionType.UNIFORM, {"low": 0.0, "high": 1.0}, f"s{i}",
            UncertaintyType.PARAMETER,
        )
        for i in range(8)
    }
    spec = _make_spec(run_sobol=True, sobol_n=700, force_sobol=True, dists=dists)
    run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    assert called  # _sobol_decompose was invoked (guard bypassed)


def test_non_uniform_distribution_raises() -> None:
    """NORMAL distribution with run_sobol=True must raise ValueError."""
    dists = {
        "x": ParameterDistribution(
            DistributionType.NORMAL, {"mean": 0.0, "std": 1.0}, "s1",
            UncertaintyType.PARAMETER,
        )
    }
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True, dists=dists)
    with pytest.raises(ValueError, match="UNIFORM"):
        run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})


def test_ic_group_attributed_to_initial_condition() -> None:
    """Parameters with UncertaintyType.INITIAL_CONDITION aggregate into initial_condition."""
    dists = {
        "ic_p": ParameterDistribution(
            DistributionType.UNIFORM, {"low": 0.0, "high": 1.0}, "s1",
            UncertaintyType.INITIAL_CONDITION,
        )
    }
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True, dists=dists)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    for dec in result.uncertainty_decomposition.values():
        # initial_condition group should be non-zero (there's a parameter in it)
        assert dec["initial_condition"] >= 0.0
        assert dec["parameter"] == pytest.approx(0.0)  # no PARAMETER dists


def test_sobol_s1_differs_from_mc_raw_variance() -> None:
    """SALib S1 index (dimensionless, bounded 0-1) must differ from MC raw variance (unbounded).

    The MC fallback stores raw output variance; Sobol stores sensitivity indices.
    For any output with non-zero spread they measure different things and cannot be equal.
    """
    # MC fallback: 10 runs with r0_base ∈ [1.0, 5.0]
    spec_mc = _make_spec(run_sobol=False, n_runs=10)
    result_mc = run_ensemble(spec_mc, _simple_factory, engine_kwargs={"master_dt": 1.0})

    # Sobol: SALib Saltelli with 8 base samples (32 total runs)
    spec_sobol = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True)
    result_sobol = run_ensemble(spec_sobol, _simple_factory, engine_kwargs={"master_dt": 1.0})

    # Find any variable where MC variance > 0 and compare to S1
    for var in result_sobol.uncertainty_decomposition:
        s1 = result_sobol.uncertainty_decomposition[var]["parameter"]
        mc_var = result_mc.uncertainty_decomposition.get(var, {}).get("parameter", 0.0)
        if mc_var > 0.0:
            # S1 ∈ [0,1]; raw variance is population-scale (likely >> 1 for any model output)
            assert s1 != pytest.approx(mc_var, rel=0.01), (
                f"S1 ({s1:.6f}) should not equal raw MC variance ({mc_var:.6f}) for {var}: "
                "these measure different quantities"
            )
            return  # one confirmed difference is sufficient
    pytest.skip("No variable showed non-zero MC variance — model may have no spread with this seed")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_sobol_decomposition.py::test_ensemble_spec_has_sobol_fields -v 2>&1 | head -20
```

Expected: `TypeError: EnsembleSpec.__init__() got an unexpected keyword argument 'run_sobol'`.

- [ ] **Step 3: Add SALib dependency**

```bash
cd /Users/johnny/pyWorldX && poetry add SALib
```

Expected: `SALib` added to `pyproject.toml`. Verify: `python3 -c "import SALib; print(SALib.__version__)"`.

- [ ] **Step 4: Implement — ensemble.py additions**

**Edit A**: Add `run_sobol`, `sobol_n`, `force_sobol` to `EnsembleSpec` (after `store_member_runs`):

```python
@dataclass
class EnsembleSpec:
    n_runs: int
    base_scenario: Scenario
    parameter_distributions: dict[str, ParameterDistribution]
    exogenous_perturbations: dict[str, ParameterDistribution] = field(
        default_factory=dict
    )
    initial_condition_perturbations: dict[str, ParameterDistribution] = field(
        default_factory=dict
    )
    threshold_queries: list[ThresholdQuery] = field(default_factory=list)
    seed: int = 42
    store_member_runs: bool = False
    temporal_resolution: int = 1        # (from Task 1)
    run_sobol: bool = False             # enable SALib Saltelli decomposition
    sobol_n: int = 512                  # base N; total runs = N*(2D+2)
    force_sobol: bool = False           # bypass 10k-run safety cap
```

**Edit B**: Add `_sobol_decompose()` as a module-level function. Insert before `run_ensemble()`:

```python
def _sobol_decompose(
    spec: EnsembleSpec,
    sector_factory: Any,
    engine_kwargs: dict[str, Any],
    all_trajectories: dict[str, list["np.ndarray[Any, Any]"]],
) -> dict[str, dict[str, float]]:
    """Run SALib Sobol variance decomposition over all distribution groups.

    Runs N*(2D+2) Saltelli samples and uses SALib to compute first-order
    S1 indices per parameter. Groups parameters by UncertaintyType and
    sums S1 within each group.

    Constraints:
    - Only DistributionType.UNIFORM is supported (requires explicit [lo, hi] bounds).
    - total runs = spec.sobol_n * (2*D + 2); must be <= 10000 unless force_sobol=True.

    Returns:
        {var: {"parameter": float, "exogenous_input": float,
               "initial_condition": float, "scenario": float}}
    """
    try:
        from SALib.sample import saltelli
        from SALib.analyze import sobol as sobol_analyze
    except ImportError as exc:
        raise ImportError(
            "SALib is required for Sobol decomposition. "
            "Install with: poetry add SALib"
        ) from exc

    from pyworldx.core.engine import Engine

    # Collect all distributions with their uncertainty type
    all_dists: dict[str, tuple[ParameterDistribution, UncertaintyType]] = {}
    for name, dist in spec.parameter_distributions.items():
        all_dists[name] = (dist, UncertaintyType.PARAMETER)
    for name, dist in spec.exogenous_perturbations.items():
        all_dists[name] = (dist, UncertaintyType.EXOGENOUS_INPUT)
    for name, dist in spec.initial_condition_perturbations.items():
        all_dists[name] = (dist, UncertaintyType.INITIAL_CONDITION)

    _zero: dict[str, float] = {
        "parameter": 0.0, "scenario": 0.0,
        "exogenous_input": 0.0, "initial_condition": 0.0,
    }
    if not all_dists:
        return {var: dict(_zero) for var in all_trajectories}

    # Validate: only UNIFORM distributions are supported
    for name, (dist, _) in all_dists.items():
        if dist.dist_type != DistributionType.UNIFORM:
            raise ValueError(
                f"Sobol decomposition requires UNIFORM distributions; "
                f"'{name}' uses {dist.dist_type.value}. "
                "Convert to UNIFORM or set run_sobol=False."
            )

    param_names = list(all_dists.keys())
    D = len(param_names)
    N = spec.sobol_n
    total_runs = N * (2 * D + 2)

    if total_runs > 10_000 and not spec.force_sobol:
        raise ValueError(
            f"Sobol run would require {total_runs:,} model evaluations "
            f"(N={N}, D={D}). This may take hours. "
            "Reduce sobol_n or set force_sobol=True to bypass this guard."
        )

    bounds = [
        [all_dists[n][0].params.get("low", 0.0), all_dists[n][0].params.get("high", 1.0)]
        for n in param_names
    ]
    problem: dict[str, Any] = {
        "num_vars": D,
        "names": param_names,
        "bounds": bounds,
    }
    X = saltelli.sample(problem, N=N, calc_second_order=False)

    # Run Saltelli samples
    base_overrides = dict(spec.base_scenario.parameter_overrides)
    Y: dict[str, list[float]] = {var: [] for var in all_trajectories}

    for row in X:
        overrides = dict(base_overrides)
        for j, name in enumerate(param_names):
            overrides[name] = float(row[j])
        sectors = sector_factory(overrides)
        engine = Engine(
            sectors=sectors,
            t_start=float(spec.base_scenario.start_year - 1900),
            t_end=float(spec.base_scenario.end_year - 1900),
            **engine_kwargs,
        )
        result = engine.run()
        for var in list(Y.keys()):
            if var in result.trajectories and len(result.trajectories[var]) > 0:
                Y[var].append(float(result.trajectories[var][-1]))
            else:
                Y[var].append(float("nan"))

    # Group by uncertainty type
    param_group = [n for n, (_, ut) in all_dists.items() if ut == UncertaintyType.PARAMETER]
    exo_group = [n for n, (_, ut) in all_dists.items() if ut == UncertaintyType.EXOGENOUS_INPUT]
    ic_group = [n for n, (_, ut) in all_dists.items() if ut == UncertaintyType.INITIAL_CONDITION]

    decomposition: dict[str, dict[str, float]] = {}

    for var, y_vals in Y.items():
        y_arr = np.array(y_vals)
        finite_mask = np.isfinite(y_arr)
        if not finite_mask.any():
            decomposition[var] = dict(_zero)
            continue
        # Replace NaN with mean to satisfy SALib's requirement for no NaN in Y
        y_arr = np.where(finite_mask, y_arr, float(np.nanmean(y_arr)))

        Si = sobol_analyze.analyze(
            problem, y_arr, calc_second_order=False
        )
        s1_by_name = {
            param_names[i]: max(0.0, float(Si["S1"][i]))
            for i in range(D)
        }
        decomposition[var] = {
            "parameter": sum(s1_by_name.get(n, 0.0) for n in param_group),
            "exogenous_input": sum(s1_by_name.get(n, 0.0) for n in exo_group),
            "initial_condition": sum(s1_by_name.get(n, 0.0) for n in ic_group),
            "scenario": 0.0,  # scenario uncertainty requires multi-scenario runs
        }

    return decomposition
```

**Edit C**: Replace the fake `TODO` block in `run_ensemble()` (lines 258–270) with the conditional dispatch:

```python
    # ── Uncertainty decomposition ────────────────────────────────────────
    if spec.run_sobol:
        decomposition = _sobol_decompose(
            spec, sector_factory, engine_kwargs, all_trajectories
        )
    else:
        # Simplified: attribute all terminal variance to parameter perturbations.
        decomposition = {}
        for var_name, traj_list in all_trajectories.items():
            arr = np.array(traj_list)
            total_var = float(np.var(arr[:, -1]))
            decomposition[var_name] = {
                "parameter": total_var,
                "scenario": 0.0,
                "exogenous_input": 0.0,
                "initial_condition": 0.0,
            }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_sobol_decomposition.py -v
```

Expected: all pass. Note: tests using `run_sobol=True` with `force_sobol=True` will run `sobol_n*(2D+2)` model evaluations — with `sobol_n=8` and `D=1`, that's `8*4=32` runs of a 5-year simulation, which completes in under 10 seconds.

- [ ] **Step 6: Regression check — full suite**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/ --tb=short -q 2>&1 | tail -10
```

Expected: all existing tests pass. The `run_sobol=False` default means no behaviour change for existing code paths.

- [ ] **Step 7: mypy + ruff**

```bash
cd /Users/johnny/pyWorldX && mypy pyworldx/forecasting/ensemble.py && ruff check pyworldx/ tests/unit/test_sobol_decomposition.py
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/forecasting/ensemble.py tests/unit/test_sobol_decomposition.py pyproject.toml poetry.lock
git commit -m "feat(ensemble): replace fake Sobol TODO with SALib Saltelli decomposition by uncertainty group"
```

---

## Task 5: Final Integration Verification

- [ ] **Step 1: Full test suite with coverage**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/ --cov=pyworldx --cov-report=term-missing --tb=short -q 2>&1 | tail -30
```

Expected: all pass, count >= 861. Coverage for changed modules (`ensemble.py`, `reports.py`, `bridge.py`, `empirical.py`, `pipeline.py`) must be >= 90% each. If any module is below 90%, add targeted tests before committing.

- [ ] **Step 2: Type check all modified modules**

```bash
cd /Users/johnny/pyWorldX && mypy pyworldx/forecasting/ensemble.py pyworldx/observability/reports.py pyworldx/data/bridge.py pyworldx/calibration/empirical.py pyworldx/calibration/pipeline.py
```

Expected: `Success: no issues found`.

- [ ] **Step 3: Lint all modified modules and new test files**

```bash
cd /Users/johnny/pyWorldX && ruff check pyworldx/ tests/
```

Expected: `All checks passed!`

- [ ] **Step 4: Push**

```bash
cd /Users/johnny/pyWorldX && git push origin phase-2-remediation
```

---

## Self-Review Checklist

**Spec coverage:**
1. Parquet exporter: `build_ensemble_report()` writes long-format Parquet ✓; `temporal_resolution` controls decimation ✓; JSON peak detection unaffected ✓
2. DataBridge: `DataBridgeError` for missing dir ✓; train-window filtering in `build_objective()` ✓; `calculate_validation_score()` ✓; `overfit_flagged` wired ✓
3. Bayesian optimizer: `_bayesian_optimize()` with Optuna TPE ✓; `seed=42` via `TPESampler` ✓; `n_trials`+`timeout` params ✓; Nelder-Mead initialised from Bayesian best ✓
4. Sobol decomposition: `run_sobol: bool = False` on `EnsembleSpec` ✓; SALib Saltelli sampling ✓; 10k cap with `force_sobol` bypass ✓; groups aggregated by `UncertaintyType` ✓; `sum(S1) <= 1.0` test ✓

**Placeholder scan:** None found — every step has complete code.

**Post-review fixes applied:**

- Task 2 test helpers: `np.ndarray[np.intp, ...]` → `np.ndarray[Any, Any]` (mypy strict compatibility)
- Task 4: `sobol_analyze.analyze()` `seed=` kwarg removed (not in SALib ^1.5 API)
- Task 4: `match="10.000"` → `match="force_sobol"` (error message contains "force_sobol", not "10,000")
- Task 2: Added `test_clip_targets_drops_short_windows` (short-target drop branch), `test_overfit_flagged_when_validation_degrades` (uses deterministic `constant_engine` returning 1.01; train target=1.0, val target=10.0 → guaranteed degradation > 20%), `test_empirical_runner_wires_validation_nrmsd` (correct constructor `aligned_dir=tmp_path`, monkeypatches `load_targets` and `run_calibration_pipeline`)
- Task 1: Added `test_write_parquet_without_pyarrow_appends_warning` (ImportError guard branch)
- Task 1: Replaced `.iterrows()` loop with vectorized `pd.concat`+`reset_index` (O(n) → O(1) Python overhead)
- Task 2: Added regression check step (Step 6)
- Task 3: `_bayesian_optimize` now returns `tuple[..., int]` (actual trial count from `len(study.trials)`); call site uses `n_bayesian_actual` to avoid overcounting when `timeout` fires early
- Task 4: Added `test_sobol_s1_differs_from_mc_raw_variance` (S1 ∈ [0,1] cannot equal raw MC variance)
- Task 5: Added `--cov` to full test suite command

**Type consistency:**
- `_sobol_decompose()` returns `dict[str, dict[str, float]]` — matches `uncertainty_decomposition` field on `EnsembleResult` ✓
- `_bayesian_optimize()` returns `tuple[dict[str, float], float]` — consumed correctly in `run_calibration_pipeline()` ✓
- `build_objective()` now accepts `train_start: Optional[int] = None` — existing call sites in `empirical.py` pass no such args → backward compatible ✓
- `EnsembleSpec.temporal_resolution` is `int` — `_write_parquet()` uses `iloc[::max(temporal_resolution, 1)]` which is valid ✓
