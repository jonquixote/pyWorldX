"""Tests for the connector normalization layer."""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.transforms.normalize import (
    NORMALIZER_REGISTRY,
    normalize_fred,
    normalize_world_bank,
    normalize_source,
)


@pytest.fixture
def world_bank_raw():
    """Simulate raw World Bank API output."""
    return pd.DataFrame({
        "indicator": [{"id": "SP.POP.TOTL", "value": "Population, total"}] * 5,
        "country": [{"id": "1W", "value": "World"}] * 5,
        "countryiso3code": ["WLD"] * 5,
        "date": [2020, 2019, 2018, 2017, 2016],
        "value": [7.85e9, 7.78e9, 7.70e9, 7.62e9, 7.55e9],
        "unit": ["persons"] * 5,
        "obs_status": [""] * 5,
        "decimal": [0] * 5,
        "source_id": ["world_bank_SP.POP.TOTL"] * 5,
        "source_variable": ["SP.POP.TOTL"] * 5,
    })


@pytest.fixture
def fred_raw():
    """Simulate raw FRED quarterly data."""
    return pd.DataFrame({
        "realtime_start": ["2025-01-01"] * 8,
        "realtime_end": ["2025-01-01"] * 8,
        "date": [
            "2024-01-01", "2024-04-01", "2024-07-01", "2024-10-01",
            "2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01",
        ],
        "value": [125.0, 126.0, 127.0, 128.0, 129.0, 130.0, 131.0, 132.0],
        "source_id": ["fred_GDPDEF"] * 8,
        "source_variable": ["GDPDEF"] * 8,
    })


@pytest.fixture
def wide_data():
    """Simulate wide format data with year columns."""
    return pd.DataFrame({
        "country": ["USA", "China"],
        "x2020": [100.0, 200.0],
        "x2021": [110.0, 220.0],
        "x2022": [120.0, 240.0],
        "units": ["kt"] * 2,
        "source_id": ["ceds_so2"] * 2,
        "value": [1.0, 2.0],  # Conflicting column
    })


# ── World Bank Normalizer Tests ───────────────────────────────────

class TestNormalizeWorldBank:
    def test_extracts_year_and_value(self, world_bank_raw):
        """Should extract year and value from World Bank format."""
        result = normalize_world_bank(world_bank_raw)
        assert "year" in result.columns
        assert "value" in result.columns
        assert len(result) == 5
        assert result["year"].iloc[0] == 2020
        assert result["value"].iloc[0] == pytest.approx(7.85e9)

    def test_extracts_country_code(self, world_bank_raw):
        """Should extract countryiso3code as country_code."""
        result = normalize_world_bank(world_bank_raw)
        assert "country_code" in result.columns
        assert all(result["country_code"] == "WLD")

    def test_drops_missing_values(self):
        """Should drop rows with NaN value."""
        df = pd.DataFrame({
            "countryiso3code": ["WLD", "WLD", "WLD"],
            "date": [2020, 2019, 2018],
            "value": [100.0, None, 300.0],
            "source_id": ["test"] * 3,
        })
        result = normalize_world_bank(df)
        assert len(result) == 2
        assert all(result["value"].notna())


# ── FRED Normalizer Tests ──────────────────────────────────────────

class TestNormalizeFred:
    def test_aggregates_quarterly_to_annual(self, fred_raw):
        """Should aggregate quarterly data to annual mean."""
        result = normalize_fred(fred_raw)
        assert len(result) == 2  # 2024 and 2025
        # Check annual mean for 2024
        val_2024 = result[result["year"] == 2024]["value"].values[0]
        assert val_2024 == pytest.approx(126.5)

    def test_handles_date_format(self, fred_raw):
        """Should parse date strings correctly."""
        result = normalize_fred(fred_raw)
        assert "year" in result.columns
        assert result["year"].dtype in [int, "int32", "int64"]

    def test_drops_missing_values(self):
        """Should drop rows with NaN value."""
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-04-01", "2024-07-01"],
            "value": [100.0, None, 300.0],
        })
        result = normalize_fred(df)
        assert len(result) == 1
        assert result["value"].iloc[0] == pytest.approx(200.0)


# ── Generic Source Tests ───────────────────────────────────────────

class TestNormalizeSource:
    def test_falls_through_without_normalizer(self):
        """Unknown source should return data as-is."""
        df = pd.DataFrame({"year": [2020, 2021], "value": [100.0, 200.0]})
        result = normalize_source(df, "unknown_source")
        assert len(result) == 2

    def test_prefix_matching(self):
        """Should match by prefix (e.g. fred_ matches fred_GDPDEF)."""
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-04-01"],
            "value": [100.0, 200.0],
        })
        result = normalize_source(df, "fred_GDPDEF")
        assert "year" in result.columns
        assert "value" in result.columns
        assert len(result) == 1  # Aggregated to annual mean
