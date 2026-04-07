"""Tests for forecasting extras: thresholds, summaries, uncertainty."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from pyworldx.core.result import RunResult
from pyworldx.forecasting.ensemble import (
    EnsembleResult,
    ThresholdQuery,
    ThresholdQueryResult,
    UncertaintyType,
    UndeclaredThresholdQueryError,
)
from pyworldx.forecasting.summaries import compute_summary, extract_percentile_band
from pyworldx.forecasting.thresholds import probability_of_threshold
from pyworldx.forecasting.uncertainty import decompose_uncertainty
from pyworldx.observability.reports import ForecastReport


class TestProbabilityOfThreshold:
    def test_declared_threshold(self) -> None:
        query = ThresholdQuery("test_q", "R", "below", 5e11, 2050)
        result = EnsembleResult(
            members=None,
            summary={},
            threshold_results={
                "test_q": ThresholdQueryResult(
                    query=query, probability=0.75, member_count=15
                )
            },
            uncertainty_decomposition={},
        )
        prob = probability_of_threshold(result, "test_q")
        assert prob == 0.75

    def test_undeclared_raises(self) -> None:
        result = EnsembleResult(
            members=None,
            summary={},
            threshold_results={},
            uncertainty_decomposition={},
        )
        with pytest.raises(UndeclaredThresholdQueryError):
            probability_of_threshold(result, "nonexistent")


class TestComputeSummary:
    def test_produces_correct_columns(self) -> None:
        rng = np.random.default_rng(42)
        trajectories = {
            "X": [rng.random(10) for _ in range(20)],
        }
        summary = compute_summary(trajectories)
        assert "X" in summary
        df = summary["X"]
        expected_cols = {"mean", "median", "p05", "p25", "p75", "p95", "min", "max"}
        assert expected_cols == set(df.columns)

    def test_with_time_index(self) -> None:
        t = np.arange(5, dtype=float)
        trajectories = {
            "Y": [np.ones(5) for _ in range(3)],
        }
        summary = compute_summary(trajectories, time_index=t)
        df = summary["Y"]
        assert df.index.name == "t"
        assert len(df) == 5

    def test_empty_trajectories_skipped(self) -> None:
        trajectories = {"Z": []}
        summary = compute_summary(trajectories)
        assert "Z" not in summary


class TestExtractPercentileBand:
    def test_returns_arrays(self) -> None:
        trajectories = {
            "X": [np.arange(10, dtype=float) + i for i in range(20)],
        }
        summary = compute_summary(trajectories)
        lower, upper = extract_percentile_band(summary, "X")
        assert isinstance(lower, np.ndarray)
        assert isinstance(upper, np.ndarray)
        assert len(lower) == 10
        assert len(upper) == 10
        # p05 should be <= p95
        assert np.all(lower <= upper)

    def test_missing_variable_raises(self) -> None:
        summary: dict[str, pd.DataFrame] = {}
        with pytest.raises(KeyError):
            extract_percentile_band(summary, "nonexistent")


class TestDecomposeUncertainty:
    def test_returns_dict(self) -> None:
        t = np.arange(5, dtype=float)
        results = [
            RunResult(
                time_index=t,
                trajectories={"X": np.array([1.0, 2.0, 3.0, 4.0, 5.0]) + i},
            )
            for i in range(10)
        ]
        labels = [
            {"param_a": UncertaintyType.PARAMETER} for _ in range(10)
        ]
        decomp = decompose_uncertainty(results, labels, variables=["X"])
        assert "X" in decomp
        assert isinstance(decomp["X"], dict)
        assert "parameter" in decomp["X"]

    def test_empty_results(self) -> None:
        decomp = decompose_uncertainty([], [])
        assert decomp == {}


class TestForecastReport:
    def test_to_json_produces_valid_json(self) -> None:
        report = ForecastReport(
            report_type="deterministic",
            final_values={"POP": 8e9},
            peak_values={"POP": 8e9},
            peak_times={"POP": 2050.0},
            warnings=["test warning"],
        )
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["report_type"] == "deterministic"
        assert parsed["final_values"]["POP"] == 8e9
        assert "test warning" in parsed["warnings"]

    def test_ensemble_report(self) -> None:
        report = ForecastReport(
            report_type="ensemble",
            ensemble_size=100,
            percentile_bands={"X": {"mean": 1.0, "p05": 0.5, "p95": 1.5}},
        )
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["report_type"] == "ensemble"
        assert parsed["ensemble_size"] == 100
        assert "X" in parsed["percentile_bands"]
