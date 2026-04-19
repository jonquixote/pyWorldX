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
