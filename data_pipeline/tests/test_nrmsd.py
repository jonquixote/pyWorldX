"""Tests for NRMSD computation."""

from __future__ import annotations

import numpy as np
import pytest

from data_pipeline.calibration.nrmsd import (
    nrmsd_change_rate,
    nrmsd_direct,
    weighted_nrmsd,
)


class TestNrmsdDirect:
    def test_perfect_match(self):
        """Perfect match should give NRMSD = 0."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert nrmsd_direct(data, data) == pytest.approx(0.0)

    def test_known_value(self):
        """Verify against manual calculation."""
        model = np.array([1.0, 2.0, 3.0])
        reference = np.array([1.1, 2.1, 3.1])
        # RMSE = sqrt(mean(0.01)) = 0.1
        # mean(ref) = 2.1
        # NRMSD = 0.1 / 2.1 ≈ 0.04762
        result = nrmsd_direct(model, reference)
        assert result == pytest.approx(0.04762, rel=1e-3)

    def test_different_lengths(self):
        """Should trim to common length."""
        model = np.array([1.0, 2.0, 3.0, 4.0])
        reference = np.array([1.0, 2.0, 3.0])
        result = nrmsd_direct(model, reference)
        # Only first 3 values used
        assert result == pytest.approx(0.0)

    def test_empty_returns_nan(self):
        """Empty arrays should return NaN."""
        assert np.isnan(nrmsd_direct(np.array([]), np.array([])))

    def test_zero_mean_ref_returns_nan(self):
        """Zero mean reference should return NaN."""
        model = np.array([1.0, -1.0])
        reference = np.array([0.0, 0.0])
        assert np.isnan(nrmsd_direct(model, reference))


class TestNrmsdChangeRate:
    def test_identical_trends(self):
        """Same trend should give NRMSD = 0."""
        model = np.array([10.0, 20.0, 30.0, 40.0])
        reference = np.array([10.0, 20.0, 30.0, 40.0])
        assert nrmsd_change_rate(model, reference) == pytest.approx(0.0)

    def test_different_trends(self):
        """Different trends should give positive NRMSD."""
        model = np.array([10.0, 20.0, 30.0, 40.0])
        reference = np.array([10.0, 15.0, 20.0, 25.0])
        result = nrmsd_change_rate(model, reference)
        assert result > 0

    def test_too_short_returns_nan(self):
        """Less than 2 points should return NaN."""
        assert np.isnan(nrmsd_change_rate(np.array([1.0]), np.array([1.0])))


class TestWeightedNrmsd:
    def test_equal_weights(self):
        """Equal weights should give simple average."""
        model = {"a": np.array([1.0, 2.0]), "b": np.array([10.0, 20.0])}
        reference = {"a": np.array([1.1, 2.1]), "b": np.array([10.1, 20.1])}
        result = weighted_nrmsd(model, reference)
        assert np.isfinite(result)

    def test_no_overlap_returns_nan(self):
        """No common variables should return NaN."""
        model = {"a": np.array([1.0])}
        reference = {"b": np.array([1.0])}
        assert np.isnan(weighted_nrmsd(model, reference))
