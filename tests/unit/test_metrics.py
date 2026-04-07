"""Tests for NRMSD calibration metrics."""

from __future__ import annotations

import pandas as pd
import pytest

from pyworldx.calibration.metrics import (
    NEBEL_2023_BOUNDS,
    NEBEL_2023_CALIBRATION_CONFIG,
    NEBEL_2023_TOTAL_NRMSD_BOUND,
    CalibrationResult,
    CrossValidationConfig,
    nrmsd_change_rate,
    nrmsd_direct,
    weighted_nrmsd,
)


class TestNrmsdDirect:
    def test_perfect_match(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0])
        assert nrmsd_direct(s, s) == 0.0

    def test_known_value(self) -> None:
        true = pd.Series([1.0, 2.0, 3.0, 4.0])
        pred = pd.Series([1.1, 2.1, 3.1, 4.1])
        result = nrmsd_direct(true, pred)
        # RMSD = 0.1, mean(true) = 2.5, NRMSD = 0.04
        assert abs(result - 0.04) < 1e-10

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            nrmsd_direct(pd.Series(dtype=float), pd.Series(dtype=float))

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="length mismatch"):
            nrmsd_direct(pd.Series([1.0]), pd.Series([1.0, 2.0]))

    def test_zero_mean_raises(self) -> None:
        with pytest.raises(ValueError, match="zero"):
            nrmsd_direct(pd.Series([1.0, -1.0]), pd.Series([1.0, -1.0]))


class TestNrmsdChangeRate:
    def test_identical_series(self) -> None:
        s = pd.Series([100.0, 110.0, 121.0, 133.1])
        result = nrmsd_change_rate(s, s)
        assert result == 0.0

    def test_different_growth_rates(self) -> None:
        true = pd.Series([100.0, 110.0, 121.0, 133.1])
        pred = pd.Series([100.0, 115.0, 132.25, 152.09])
        result = nrmsd_change_rate(true, pred)
        assert result > 0


class TestWeightedNrmsd:
    def test_equal_weights(self) -> None:
        metrics = {"a": 0.1, "b": 0.2, "c": 0.3}
        weights = {"a": 1.0, "b": 1.0, "c": 1.0}
        result = weighted_nrmsd(metrics, weights)
        assert abs(result - 0.2) < 1e-10

    def test_weighted(self) -> None:
        metrics = {"a": 0.1, "b": 0.5}
        weights = {"a": 3.0, "b": 1.0}
        result = weighted_nrmsd(metrics, weights)
        expected = (0.1 * 3.0 + 0.5 * 1.0) / 4.0
        assert abs(result - expected) < 1e-10

    def test_zero_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            weighted_nrmsd({"a": 0.1}, {"b": 1.0})


class TestCrossValidation:
    def test_default_config(self) -> None:
        cfg = CrossValidationConfig()
        assert cfg.train_start == 1970
        assert cfg.train_end == 2010

    def test_nebel_config(self) -> None:
        assert NEBEL_2023_CALIBRATION_CONFIG.train_start == 1970
        assert NEBEL_2023_CALIBRATION_CONFIG.train_end == 2020


class TestConstants:
    def test_nebel_bounds_exist(self) -> None:
        assert "population" in NEBEL_2023_BOUNDS
        assert NEBEL_2023_BOUNDS["population"] == (0.019, "direct")

    def test_total_bound(self) -> None:
        assert NEBEL_2023_TOTAL_NRMSD_BOUND == 0.2719

    def test_calibration_result(self) -> None:
        cr = CalibrationResult(
            parameters={"a": 1.0},
            nrmsd_scores={"pop": 0.01},
            total_nrmsd=0.01,
            train_config=CrossValidationConfig(),
            iterations=10,
            converged=True,
        )
        assert cr.converged
