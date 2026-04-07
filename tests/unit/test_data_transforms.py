"""Tests for data transformation pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pyworldx.data.transforms.gap_fill import (
    GapFillMethod,
    detect_gaps,
    fill_gaps,
)
from pyworldx.data.transforms.interpolation import interpolate_annual
from pyworldx.data.transforms.normalization import per_capita, z_score
from pyworldx.data.transforms.units import convert_series_units, normalize_to_base_year


class TestConvertSeriesUnits:
    def test_multiplies_by_factor(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0], index=[2000, 2001, 2002])
        result = convert_series_units(s, "km", "m", factor=1000.0)
        expected = pd.Series([1000.0, 2000.0, 3000.0], index=[2000, 2001, 2002])
        pd.testing.assert_series_equal(result, expected)

    def test_transform_log(self) -> None:
        s = pd.Series([10.0], index=[2000])
        log: list[str] = []
        convert_series_units(s, "millions", "persons", factor=1e6, transform_log=log)
        assert len(log) == 1
        assert "unit_convert" in log[0]


class TestNormalizeToBaseYear:
    def test_base_year_equals_one(self) -> None:
        s = pd.Series([100.0, 200.0, 300.0], index=[2000, 2001, 2002])
        result = normalize_to_base_year(s, base_year=2000)
        assert result.loc[2000] == 1.0
        assert result.loc[2001] == 2.0

    def test_missing_base_year_raises(self) -> None:
        s = pd.Series([100.0], index=[2000])
        try:
            normalize_to_base_year(s, base_year=1999)
            assert False, "Should have raised"
        except ValueError:
            pass


class TestInterpolateAnnual:
    def test_fills_gaps(self) -> None:
        s = pd.Series([10.0, 30.0], index=[2000, 2002])
        result = interpolate_annual(s)
        assert len(result) == 3
        assert abs(result.loc[2001] - 20.0) < 1e-10

    def test_empty_series(self) -> None:
        s = pd.Series(dtype=float)
        result = interpolate_annual(s)
        assert result.empty


class TestPerCapita:
    def test_division(self) -> None:
        total = pd.Series([100.0, 200.0], index=[2000, 2001])
        pop = pd.Series([10.0, 20.0], index=[2000, 2001])
        result = per_capita(total, pop)
        assert result.loc[2000] == 10.0
        assert result.loc[2001] == 10.0

    def test_common_index(self) -> None:
        total = pd.Series([100.0, 200.0, 300.0], index=[2000, 2001, 2002])
        pop = pd.Series([10.0, 20.0], index=[2000, 2001])
        result = per_capita(total, pop)
        assert len(result) == 2


class TestZScore:
    def test_mean_approximately_zero(self) -> None:
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = z_score(s)
        assert abs(result.mean()) < 1e-10

    def test_std_approximately_one(self) -> None:
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = z_score(s)
        # pandas std uses ddof=1 by default
        assert abs(result.std() - 1.0) < 1e-10


class TestFillGaps:
    def test_linear_fill(self) -> None:
        s = pd.Series([1.0, np.nan, 3.0], index=[0, 1, 2])
        result = fill_gaps(s, method=GapFillMethod.LINEAR)
        assert abs(result.iloc[1] - 2.0) < 1e-10

    def test_constant_fill(self) -> None:
        s = pd.Series([1.0, np.nan, 3.0], index=[0, 1, 2])
        result = fill_gaps(s, method=GapFillMethod.CONSTANT, constant_value=0.0)
        assert result.iloc[1] == 0.0

    def test_no_gaps_returns_same(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        result = fill_gaps(s)
        pd.testing.assert_series_equal(result, s)

    def test_transform_log_recorded(self) -> None:
        s = pd.Series([1.0, np.nan, 3.0])
        log: list[str] = []
        fill_gaps(s, method=GapFillMethod.LINEAR, transform_log=log)
        assert len(log) == 1
        assert "gap_fill" in log[0]


class TestDetectGaps:
    def test_finds_contiguous_nan_blocks(self) -> None:
        s = pd.Series([1.0, np.nan, np.nan, 4.0, np.nan, 6.0])
        gaps = detect_gaps(s)
        assert len(gaps) == 2
        # First gap: starts at index 1, length 2
        assert gaps[0] == (1, 2)
        # Second gap: starts at index 4, length 1
        assert gaps[1] == (4, 1)

    def test_no_gaps(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        gaps = detect_gaps(s)
        assert gaps == []

    def test_trailing_gap(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan, np.nan])
        gaps = detect_gaps(s)
        assert len(gaps) == 1
        assert gaps[0] == (2, 2)
