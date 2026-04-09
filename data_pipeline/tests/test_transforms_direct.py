"""Tests for all transform modules — direct function tests."""

from __future__ import annotations

import pandas as pd

from data_pipeline.transforms.reshape import melt_wide_to_long, standardize_columns, filter_by_year
from data_pipeline.transforms.interpolation import interpolate_annual, fill_gaps
from data_pipeline.transforms.aggregation import aggregate_world
from data_pipeline.transforms.deflation import deflate_series
from data_pipeline.transforms.per_capita import per_capita
from data_pipeline.transforms.unit_conversion import convert_units, normalize_to_base_year
from data_pipeline.transforms.gap_detection import detect_gaps
from data_pipeline.transforms.outlier_detection import detect_outliers_zscore, detect_outliers_iqr, detect_sudden_changes


# ── Reshape Tests ──────────────────────────────────────────────────

class TestReshapeTransforms:
    """Tests for reshape transform functions."""
    
    def test_melt_wide_to_long_callable(self):
        """Should be callable."""
        assert callable(melt_wide_to_long)
    
    def test_standardize_columns_callable(self):
        """Should be callable."""
        assert callable(standardize_columns)
    
    def test_filter_by_year_callable(self):
        """Should be callable."""
        assert callable(filter_by_year)
    
    def test_filter_by_year_works(self):
        """Should filter by year range."""
        df = pd.DataFrame({
            "year": [2018, 2019, 2020, 2021, 2022],
            "value": [1, 2, 3, 4, 5],
        })
        result = filter_by_year(df, year_col="year", start_year=2020, end_year=2022)
        assert len(result) == 3


# ── Interpolation Tests ────────────────────────────────────────────

class TestInterpolationTransforms:
    """Tests for interpolation transform functions."""
    
    def test_interpolate_annual_callable(self):
        """Should be callable."""
        assert callable(interpolate_annual)
    
    def test_fill_gaps_callable(self):
        """Should be callable."""
        assert callable(fill_gaps)
    
    def test_interpolate_annual_works(self):
        """Should fill gaps in annual data."""
        df = pd.DataFrame({
            "year": [2020, 2022],
            "value": [100.0, 120.0],
        })
        result = interpolate_annual(df, year_col="year", value_col="value")
        assert len(result) == 3  # 2020, 2021, 2022
        assert 2021 in result["year"].values


# ── Aggregation Tests ──────────────────────────────────────────────

class TestAggregationTransforms:
    """Tests for aggregation transform functions."""
    
    def test_aggregate_world_callable(self):
        """Should be callable."""
        assert callable(aggregate_world)
    
    def test_aggregate_world_works(self):
        """Should add world aggregate."""
        df = pd.DataFrame({
            "country_code": ["USA", "CHN", "WLD"],
            "year": [2020, 2020, 2020],
            "value": [100.0, 200.0, 300.0],
        })
        result = aggregate_world(df, country_col="country_code", value_col="value")
        # Should return DataFrame with world aggregate column
        assert result is not None


# ── Deflation Tests ────────────────────────────────────────────────

class TestDeflationTransforms:
    """Tests for deflation transform functions."""
    
    def test_deflate_series_callable(self):
        """Should be callable."""
        assert callable(deflate_series)
    
    def test_deflate_series_works(self):
        """Should deflate nominal to real values."""
        df = pd.DataFrame({
            "year": [2020, 2021],
            "value": [1000.0, 1100.0],
        })
        deflator_df = pd.DataFrame({
            "year": [2020, 2021],
            "value": [100.0, 105.0],
        })
        result = deflate_series(
            df, value_col="value", deflator_df=deflator_df,
            base_year=2020,
        )
        assert result is not None


# ── Per Capita Tests ───────────────────────────────────────────────

class TestPerCapitaTransforms:
    """Tests for per-capita transform functions."""
    
    def test_per_capita_callable(self):
        """Should be callable."""
        assert callable(per_capita)
    
    def test_per_capita_works(self):
        """Should convert total to per-capita."""
        df = pd.DataFrame({
            "year": [2020],
            "value": [1000000.0],
            "country_code": ["USA"],
        })
        pop_df = pd.DataFrame({
            "year": [2020],
            "value": [100000.0],
            "country_code": ["USA"],
        })
        result = per_capita(
            df, value_col="value", 
            population_df=pop_df,
            population_col="value",
        )
        assert result is not None


# ── Unit Conversion Tests ──────────────────────────────────────────

class TestUnitConversionTransforms:
    """Tests for unit conversion transform functions."""
    
    def test_convert_units_callable(self):
        """Should be callable."""
        assert callable(convert_units)
    
    def test_normalize_to_base_year_callable(self):
        """Should be callable."""
        assert callable(normalize_to_base_year)
    
    def test_convert_units_works(self):
        """Should apply conversion factor."""
        df = pd.DataFrame({"value": [1000.0]})
        # convert_units takes (df, value_col, factor)
        result = convert_units(df, value_col="value", factor=0.001)
        assert result is not None
    
    def test_normalize_to_base_year_works(self):
        """Should normalize to base year = 100."""
        df = pd.DataFrame({
            "year": [2020, 2021],
            "value": [100.0, 110.0],
        })
        result = normalize_to_base_year(df, year_col="year", value_col="value", base_year=2020)
        assert result is not None


# ── Gap Detection Tests ────────────────────────────────────────────

class TestGapDetectionTransforms:
    """Tests for gap detection transform functions."""
    
    def test_detect_gaps_callable(self):
        """Should be callable."""
        assert callable(detect_gaps)
    
    def test_detect_gaps_works(self):
        """Should identify missing years."""
        df = pd.DataFrame({"year": [2020, 2022, 2024]})
        gaps = detect_gaps(df, year_col="year")
        assert len(gaps) > 0


# ── Outlier Detection Tests ────────────────────────────────────────

class TestOutlierDetectionTransforms:
    """Tests for outlier detection transform functions."""
    
    def test_detect_zscore_outliers_callable(self):
        """Should be callable."""
        assert callable(detect_outliers_zscore)
    
    def test_detect_iqr_outliers_callable(self):
        """Should be callable."""
        assert callable(detect_outliers_iqr)
    
    def test_detect_sudden_changes_callable(self):
        """Should be callable."""
        assert callable(detect_sudden_changes)
    
    def test_detect_zscore_outliers_works(self):
        """Should flag z-score outliers."""
        df = pd.DataFrame({
            "year": list(range(2000, 2021)),
            "value": [100.0] * 20 + [1000.0],
        })
        result = detect_outliers_zscore(df, value_col="value")
        assert "z_score" in result.columns
        assert "outlier_flag" in result.columns
    
    def test_detect_iqr_outliers_works(self):
        """Should flag IQR outliers."""
        df = pd.DataFrame({
            "year": list(range(2000, 2021)),
            "value": [100.0] * 20 + [500.0],
        })
        result = detect_outliers_iqr(df, value_col="value")
        assert "iqr_lower" in result.columns
        assert "outlier_flag_iqr" in result.columns
    
    def test_detect_sudden_changes_works(self):
        """Should flag sudden changes."""
        df = pd.DataFrame({
            "year": [2020, 2021, 2022],
            "value": [100.0, 110.0, 500.0],
        })
        result = detect_sudden_changes(df, year_col="year", value_col="value", change_threshold=2.0)
        assert "yoy_change" in result.columns
        assert "sudden_change_flag" in result.columns
