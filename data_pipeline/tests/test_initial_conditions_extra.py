"""Tests for initial conditions extraction — additional coverage."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.alignment.initial_conditions import (
    extract_initial_conditions,
    extract_sector_initial_conditions,
)


@pytest.fixture
def temp_aligned_store_multi():
    """Create a temporary aligned store with multiple entities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aligned_dir = Path(tmpdir)
        
        # Population data
        pop_df = pd.DataFrame({
            "entity": ["population.total"] * 10,
            "year": list(range(2010, 2020)),
            "value": [6.9e9 + i * 80e6 for i in range(10)],
            "unit": ["persons"] * 10,
            "source_id": ["faostat"] * 10,
            "quality_flag": ["OK"] * 10,
        })
        pop_df.to_parquet(aligned_dir / "population_total.parquet", index=False)
        
        # CO2 emissions data
        co2_df = pd.DataFrame({
            "entity": ["emissions.co2_fossil"] * 274,
            "year": list(range(1750, 2024)),
            "value": [20.0 + i * 100 for i in range(274)],
            "unit": ["kt_CO2"] * 274,
            "source_id": ["gcp"] * 274,
            "quality_flag": ["OK"] * 274,
        })
        co2_df.to_parquet(aligned_dir / "emissions_co2_fossil.parquet", index=False)
        
        # Temperature anomaly
        temp_df = pd.DataFrame({
            "entity": ["temperature.anomaly"] * 146,
            "year": list(range(1880, 2026)),
            "value": [-0.2 + (i - 73) * 0.01 for i in range(146)],
            "unit": ["degC_anomaly"] * 146,
            "source_id": ["nasa_giss"] * 146,
            "quality_flag": ["OK"] * 146,
        })
        temp_df.to_parquet(aligned_dir / "temperature_anomaly.parquet", index=False)
        
        # Food supply
        food_df = pd.DataFrame({
            "entity": ["food.supply.kcal_per_capita"] * 14,
            "year": list(range(2010, 2024)),
            "value": [2800.0 + i * 15 for i in range(14)],
            "unit": ["kcal/capita/day"] * 14,
            "source_id": ["faostat"] * 14,
            "quality_flag": ["OK"] * 14,
        })
        food_df.to_parquet(aligned_dir / "food_supply_kcal_per_capita.parquet", index=False)
        
        yield aligned_dir


class TestExtractInitialConditionsMulti:
    """Tests for initial conditions with multiple entities."""
    
    def test_extracts_all_mapped_entities(self, temp_aligned_store_multi):
        """Should extract values for all mapped entities."""
        results = extract_initial_conditions(temp_aligned_store_multi, target_year=1900)
        
        # Check all expected entities are present
        assert "population.total" in results
        assert "emissions.co2_fossil" in results
        assert "temperature.anomaly" in results
        assert "food.supply.kcal_per_capita" in results
        assert "atmospheric.co2" in results  # Has default value
    
    def test_finds_closest_year_for_each(self, temp_aligned_store_multi):
        """Should find closest year to target for each entity."""
        results = extract_initial_conditions(temp_aligned_store_multi, target_year=1900)
        
        # Emissions has data for 1900
        co2 = results["emissions.co2_fossil"]
        assert co2["year"] == 1900
        
        # Temperature has data for 1900
        temp = results["temperature.anomaly"]
        assert temp["year"] == 1900
        
        # Population only has 2010+, should use 2010
        pop = results["population.total"]
        assert pop["year"] == 2010
    
    def test_uses_defaults_for_missing_entities(self, temp_aligned_store_multi):
        """Should use default values for entities without aligned data."""
        results = extract_initial_conditions(temp_aligned_store_multi, target_year=1900)
        
        # atmospheric.co2 has no aligned data
        co2 = results["atmospheric.co2"]
        assert co2["source"] == "default"
        assert co2["value"] == pytest.approx(295.0)
    
    def test_sector_grouping(self, temp_aligned_store_multi):
        """Should group initial conditions by sector."""
        by_sector = extract_sector_initial_conditions(temp_aligned_store_multi, target_year=1900)
        
        assert "population" in by_sector
        assert "pollution" in by_sector
        assert "agriculture" in by_sector
        
        assert "POP" in by_sector["population"]
        assert "PPOL" in by_sector["pollution"]
        assert "PPOL_atmospheric" in by_sector["pollution"]
        assert "temp_anomaly" in by_sector["pollution"]
        assert "food_supply_per_capita" in by_sector["agriculture"]
    
    def test_target_year_2000(self, temp_aligned_store_multi):
        """Should find data closer to year 2000."""
        results = extract_initial_conditions(temp_aligned_store_multi, target_year=2000)
        
        # Population should use 2010 (closest available)
        pop = results["population.total"]
        assert pop["year"] == 2010
        
        # Emissions should use 2000
        co2 = results["emissions.co2_fossil"]
        assert co2["year"] == 2000
    
    def test_target_year_1750(self, temp_aligned_store_multi):
        """Should find data from earliest available year."""
        results = extract_initial_conditions(temp_aligned_store_multi, target_year=1750)
        
        # Emissions has 1750
        co2 = results["emissions.co2_fossil"]
        assert co2["year"] == 1750
        
        # Temperature starts at 1880
        temp = results["temperature.anomaly"]
        assert temp["year"] == 1880
