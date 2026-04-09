"""Tests for OWID connector."""

from __future__ import annotations


import pandas as pd
import pytest

from data_pipeline.connectors.owid import (
    KEY_SEARCHES,
    search_owid,
)
from data_pipeline.transforms.normalize import normalize_owid, normalize_source


@pytest.mark.network
class TestOwidSearch:
    """Tests for OWID search API."""
    
    def test_search_returns_results(self):
        """OWID search should return indicator results."""
        results = search_owid("primary energy", limit=5)
        assert len(results) > 0
        assert "title" in results[0]
        assert "metadata" in results[0]
    
    def test_search_has_parquet_url(self):
        """Search results should include parquet_url in metadata."""
        results = search_owid("primary energy", limit=5)
        # At least one result should have parquet_url
        has_parquet = any(
            r.get("metadata", {}).get("parquet_url", "") 
            for r in results
        )
        assert has_parquet
    
    def test_search_keys(self):
        """Search results should have expected keys."""
        results = search_owid("co2", limit=3)
        for r in results:
            assert "title" in r
            assert "indicator_id" in r
            assert "metadata" in r


class TestOwidKeys:
    """Tests for OWID predefined search keys."""
    
    def test_has_all_expected_keys(self):
        """Should have all pyWorldX search keys."""
        expected = [
            "primary_energy",
            "fossil_co2",
            "co2_per_capita",
            "gdp_maddison",
            "population",
            "life_expectancy",
        ]
        for key in expected:
            assert key in KEY_SEARCHES
    
    def test_each_key_has_query(self):
        """Each search key should have a query string."""
        for key, params in KEY_SEARCHES.items():
            assert "q" in params
            assert params["q"]
            assert "kind" in params


class TestOwidNormalization:
    """Tests for OWID data normalization."""
    
    def test_normalizes_parquet_data(self):
        """Should normalize OWID parquet data with standard columns."""
        df = pd.DataFrame({
            "country": ["World", "USA", "China"],
            "year": [2020, 2020, 2020],
            "energy_consumption": [100.0, 200.0, 300.0],
        })
        result = normalize_owid(df)
        
        assert "year" in result.columns
        assert "value" in result.columns
        assert "country_code" in result.columns
        assert len(result) == 3
    
    def test_filters_to_world_when_present(self):
        """Should detect World rows."""
        df = pd.DataFrame({
            "country": ["World", "USA"],
            "year": [2020, 2020],
            "value": [100.0, 200.0],
        })
        result = normalize_source(df, "owid_search_primary_energy")
        
        assert "year" in result.columns
        assert "value" in result.columns
    
    def test_handles_metadata_only(self):
        """Search metadata without year column should pass through."""
        df = pd.DataFrame({
            "title": ["Test indicator"],
            "indicator_id": [12345],
            "snippet": ["Test description"],
        })
        result = normalize_owid(df)
        
        # Should return as-is since no year column
        assert len(result) == 1
        assert "year" not in result.columns
