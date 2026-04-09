"""Tests for initial conditions extraction."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.alignment.initial_conditions import (
    extract_initial_conditions,
    extract_sector_initial_conditions,
    report_initial_conditions,
)


@pytest.fixture
def temp_aligned_store():
    """Create a temporary aligned Parquet store with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aligned_dir = Path(tmpdir)

        # Create test population data
        pop_df = pd.DataFrame({
            "entity": ["population.total"] * 3,
            "year": [2010, 2015, 2020],
            "value": [7e9, 7.3e9, 7.8e9],
            "unit": ["persons"] * 3,
            "source_id": ["test"] * 3,
            "quality_flag": ["OK"] * 3,
        })
        pop_df.to_parquet(aligned_dir / "population_total.parquet", index=False)

        # Create test CO2 data
        co2_df = pd.DataFrame({
            "entity": ["emissions.co2_fossil"] * 3,
            "year": [1900, 1950, 2000],
            "value": [2000.0, 6000.0, 25000.0],
            "unit": ["Mt_CO2"] * 3,
            "source_id": ["test"] * 3,
            "quality_flag": ["OK"] * 3,
        })
        co2_df.to_parquet(aligned_dir / "emissions_co2_fossil.parquet", index=False)

        yield aligned_dir


class TestExtractInitialConditions:
    def test_extracts_aligned_value(self, temp_aligned_store):
        """Should extract value closest to target year."""
        results = extract_initial_conditions(temp_aligned_store, target_year=2010)
        assert "population.total" in results
        pop = results["population.total"]
        assert pop["value"] == pytest.approx(7e9)
        assert pop["source"] == "aligned"
        assert pop["year"] == 2010

    def test_uses_default_when_no_data(self, temp_aligned_store):
        """Should use default when entity has no aligned data."""
        results = extract_initial_conditions(temp_aligned_store, target_year=1900)
        assert "food.supply.kcal_per_capita" in results
        food = results["food.supply.kcal_per_capita"]
        assert food["source"] == "default"
        assert food["value"] == pytest.approx(2400.0)

    def test_finds_closest_year(self, temp_aligned_store):
        """Should find closest year to target."""
        results = extract_initial_conditions(temp_aligned_store, target_year=1900)
        assert "emissions.co2_fossil" in results
        co2 = results["emissions.co2_fossil"]
        assert co2["year"] == 1900
        assert co2["value"] == pytest.approx(2000.0)


class TestExtractSectorInitialConditions:
    def test_groups_by_sector(self, temp_aligned_store):
        """Should group initial conditions by sector."""
        by_sector = extract_sector_initial_conditions(temp_aligned_store, target_year=2010)
        assert "population" in by_sector
        assert "POP" in by_sector["population"]
        assert by_sector["population"]["POP"] == pytest.approx(7e9)

        assert "pollution" in by_sector
        assert "PPOL" in by_sector["pollution"]


class TestReportInitialConditions:
    def test_generates_readable_report(self, temp_aligned_store):
        """Should generate a human-readable report."""
        report = report_initial_conditions(temp_aligned_store, target_year=2010)
        assert "population.total" in report
        assert "7000000000.00" in report
        assert "aligned" in report
