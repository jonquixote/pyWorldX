"""Tests for connector normalization layer — additional coverage."""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.transforms.normalize import (
    normalize_carbon_atlas,
    normalize_ceds,
    normalize_primap,
    normalize_undp,
)


# ── CEDS Normalizer Tests ──────────────────────────────────────────

class TestNormalizeCeds:
    def test_melts_wide_format(self):
        """CEDS has xYYYY columns that should be melted and aggregated."""
        df = pd.DataFrame({
            "em": ["SO2"] * 3,
            "sector": ["1A1a", "1A1a", "1A1a"],
            "fuel": ["biomass", "coal", "oil"],
            "units": ["ktSO2"] * 3,
            "x2020": [10.0, 100.0, 200.0],
            "x2021": [12.0, 110.0, 210.0],
            "source_id": ["ceds_so2"] * 3,
            "value": [1.0, 2.0, 3.0],  # Conflicting column
        })
        result = normalize_ceds(df)
        assert "year" in result.columns
        assert "value" in result.columns
        # Aggregated by year: 310 for 2020, 332 for 2021
        assert len(result) == 2
        assert result[result["year"] == 2020]["value"].iloc[0] == pytest.approx(310.0)
        assert result[result["year"] == 2021]["value"].iloc[0] == pytest.approx(332.0)
        assert "country_code" in result.columns
        assert all(result["country_code"] == "World")

    def test_handles_no_year_columns(self):
        """If no xYYYY columns, return as-is."""
        df = pd.DataFrame({
            "em": ["SO2"],
            "sector": ["1A1a"],
            "units": ["ktSO2"],
        })
        result = normalize_ceds(df)
        assert len(result) == 1


# ── Carbon Atlas Normalizer Tests ──────────────────────────────────

class TestNormalizeCarbonAtlas:
    def test_filters_to_world_or_aggregates(self):
        """If no World row, sum all countries."""
        df = pd.DataFrame({
            "country": ["USA", "China"],
            "year": [2020, 2020],
            "total": [5000.0, 10000.0],
        })
        result = normalize_carbon_atlas(df)
        assert len(result) == 1
        assert result["value"].iloc[0] == pytest.approx(15000.0)
        assert result["country_code"].iloc[0] == "World"

    def test_drops_null_values_before_aggregation(self):
        """Should drop null values before summing."""
        df = pd.DataFrame({
            "country": ["USA", "China", "India"],
            "year": [2020, 2020, 2020],
            "total": [5000.0, None, 3000.0],
        })
        result = normalize_carbon_atlas(df)
        assert len(result) == 1
        assert result["value"].iloc[0] == pytest.approx(8000.0)


# ── PRIMAP Normalizer Tests ─────────────────────────────────────────

class TestNormalizePrimap:
    def test_melts_wide_format(self):
        """PRIMAP has year columns that should be melted and aggregated."""
        df = pd.DataFrame({
            "area_(iso3)": ["EARTH", "EARTH"],
            "unit": ["CH4 * gigagram / a"] * 2,
            "1990": [100.0, 200.0],
            "1991": [110.0, 210.0],
            "source_id": ["primap_hist"] * 2,
        })
        result = normalize_primap(df)
        assert "year" in result.columns
        assert "value" in result.columns
        # Aggregated by year: 300 for 1990, 320 for 1991
        assert len(result) == 2
        assert result[result["year"] == 1990]["value"].iloc[0] == pytest.approx(300.0)
        assert result[result["year"] == 1991]["value"].iloc[0] == pytest.approx(320.0)

    def test_filters_to_earth(self):
        """Should filter to EARTH aggregate code."""
        df = pd.DataFrame({
            "area_(iso3)": ["EARTH", "USA"],
            "unit": ["CO2 * gigagram / a"] * 2,
            "1990": [1000.0, 500.0],
            "1991": [1100.0, 550.0],
            "source_id": ["primap_hist"] * 2,
        })
        result = normalize_primap(df)
        assert len(result) == 2  # Only EARTH rows
        assert all(result["country_code"] == "EARTH")

    def test_aggregates_by_year(self):
        """Should aggregate across IPCC categories."""
        df = pd.DataFrame({
            "area_(iso3)": ["EARTH"] * 3,
            "unit": ["CO2 * gigagram / a"] * 3,
            "1990": [1000.0, 500.0, 200.0],
            "1991": [1100.0, 550.0, 220.0],
            "source_id": ["primap_hist"] * 3,
        })
        result = normalize_primap(df)
        assert len(result) == 2  # 2 years
        assert result[result["year"] == 1990]["value"].iloc[0] == pytest.approx(1700.0)


# ── UNDP Normalizer Tests ───────────────────────────────────────────

class TestNormalizeUndp:
    def test_melts_hdi_columns(self):
        """UNDP has hdi_YYYY columns that should be melted and averaged."""
        df = pd.DataFrame({
            "iso3": ["USA", "China"],
            "country": ["United States", "China"],
            "hdi_2020": [0.92, 0.76],
            "hdi_2021": [0.93, 0.77],
            "hdi_2022": [0.94, 0.78],
        })
        result = normalize_undp(df)
        assert "year" in result.columns
        assert "value" in result.columns
        # Aggregated to World average: (0.92+0.76)/2=0.84 for 2020
        assert len(result) == 3
        assert result[result["year"] == 2020]["value"].iloc[0] == pytest.approx(0.84, abs=0.01)
        assert result[result["year"] == 2022]["value"].iloc[0] == pytest.approx(0.86, abs=0.01)

    def test_handles_no_hdi_columns(self):
        """If no hdi_YYYY columns, return as-is."""
        df = pd.DataFrame({
            "iso3": ["USA"],
            "country": ["United States"],
        })
        result = normalize_undp(df)
        assert len(result) == 1
