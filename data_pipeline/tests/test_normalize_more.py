"""Tests for additional normalizers (OECD, OWID)."""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.transforms.normalize import (
    normalize_oecd,
    normalize_owid,
)


# ── OECD Normalizer Tests ─────────────────────────────────────────

class TestNormalizeOecd:
    def test_maps_ref_area_to_iso3(self):
        """REF_AREA indices should map to ISO3 country codes."""
        df = pd.DataFrame({
            "REF_AREA": ["0", "12", "37"],
            "TIME_PERIOD": ["70", "71", "72"],
            "OBS_VALUE": [1000.0, 2000.0, 3000.0],
        })
        result = normalize_oecd(df)
        assert result["country_code"].tolist() == ["AUS", "DEU", "USA"]

    def test_maps_time_period_to_year(self):
        """TIME_PERIOD indices should map to actual years (base 1949)."""
        df = pd.DataFrame({
            "REF_AREA": ["37", "37", "37"],
            "TIME_PERIOD": ["0", "1", "75"],
            "OBS_VALUE": [100.0, 110.0, 200.0],
        })
        result = normalize_oecd(df)
        assert result["year"].tolist() == [1949, 1950, 2024]

    def test_renames_obs_value(self):
        """OBS_VALUE should become value column."""
        df = pd.DataFrame({
            "REF_AREA": ["37"],
            "TIME_PERIOD": ["70"],
            "OBS_VALUE": [5000.0],
        })
        result = normalize_oecd(df)
        assert "value" in result.columns
        assert result["value"].iloc[0] == pytest.approx(5000.0)

    def test_drops_null_values(self):
        """Should drop rows with missing year or value."""
        df = pd.DataFrame({
            "REF_AREA": ["37", "37", "37"],
            "TIME_PERIOD": ["70", None, "72"],
            "OBS_VALUE": [100.0, 200.0, None],
        })
        result = normalize_oecd(df)
        assert len(result) == 1
        assert result["year"].iloc[0] == 1949 + 70


# ── OWID Normalizer Tests ──────────────────────────────────────────

class TestNormalizeOwid:
    def test_handles_parquet_data(self):
        """Should normalize OWID parquet data with country, year, value."""
        df = pd.DataFrame({
            "country": ["World", "USA", "China"],
            "year": [2020, 2020, 2020],
            "energy_consumption": [100.0, 200.0, 300.0],
        })
        result = normalize_owid(df)
        assert "year" in result.columns
        assert "value" in result.columns
        assert len(result) == 3

    def test_filters_to_world(self):
        """Search results should be left as-is (no year column)."""
        df = pd.DataFrame({
            "title": ["Test indicator"],
            "indicator_id": [12345],
            "snippet": ["Test snippet"],
        })
        result = normalize_owid(df)
        assert len(result) == 1

    def test_finds_value_column(self):
        """Should find the data column when not named 'value'."""
        df = pd.DataFrame({
            "country": ["World"],
            "year": [2020],
            "co2_emissions": [5000.0],
        })
        result = normalize_owid(df)
        assert "value" in result.columns
        assert result["value"].iloc[0] == pytest.approx(5000.0)

    def test_converts_country_to_country_code(self):
        """Should rename country to country_code."""
        df = pd.DataFrame({
            "country": ["USA"],
            "year": [2020],
            "value": [100.0],
        })
        result = normalize_owid(df)
        assert "country_code" in result.columns
        assert result["country_code"].iloc[0] == "USA"
