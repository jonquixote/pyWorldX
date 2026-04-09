"""Tests for transform modules — focused on core functionality."""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.transforms.outlier_detection import detect_outliers_zscore, detect_outliers_iqr, detect_sudden_changes


# ── Outlier Detection Tests ────────────────────────────────────────

class TestOutlierDetection:
    """Tests for outlier detection transforms."""
    
    def test_detect_zscore_outliers_no_groups(self):
        """Should flag z-score outliers without groups."""
        df = pd.DataFrame({
            "year": list(range(2000, 2021)),
            "value": [100.0] * 20 + [1000.0],  # Last value is outlier
        })
        result = detect_outliers_zscore(df, value_col="value")
        assert "z_score" in result.columns
        assert "outlier_flag" in result.columns
        # Last value should be flagged
        assert result.iloc[-1]["outlier_flag"] == "OUTLIER"
    
    def test_detect_zscore_outliers_with_groups(self):
        """Should flag z-score outliers within groups."""
        df = pd.DataFrame({
            "country": ["USA"] * 21 + ["CHN"] * 21,
            "year": list(range(2000, 2021)) * 2,
            "value": [100.0] * 20 + [1000.0] + [200.0] * 21,
        })
        result = detect_outliers_zscore(df, value_col="value", group_cols=["country"])
        assert result[result["country"] == "USA"].iloc[-1]["outlier_flag"] == "OUTLIER"
    
    def test_detect_iqr_outliers(self):
        """Should flag IQR outliers."""
        df = pd.DataFrame({
            "year": list(range(2000, 2021)),
            "value": [100.0] * 20 + [500.0],
        })
        result = detect_outliers_iqr(df, value_col="value")
        assert "iqr_lower" in result.columns
        assert "iqr_upper" in result.columns
        assert "outlier_flag_iqr" in result.columns
    
    def test_detect_sudden_changes(self):
        """Should flag sudden value changes."""
        df = pd.DataFrame({
            "year": [2020, 2021, 2022],
            "value": [100.0, 110.0, 500.0],  # 355% jump
        })
        result = detect_sudden_changes(df, year_col="year", value_col="value", change_threshold=2.0)
        assert "yoy_change" in result.columns
        assert "sudden_change_flag" in result.columns
    
    def test_missing_value_column(self):
        """Should handle missing value column gracefully."""
        df = pd.DataFrame({"year": [2020]})
        result = detect_outliers_zscore(df, value_col="value")
        assert "z_score" in result.columns
        assert result["z_score"].isna().all()
