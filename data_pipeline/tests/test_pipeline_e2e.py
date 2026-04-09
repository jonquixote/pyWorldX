"""End-to-end pipeline integration tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.storage.parquet_store import write_raw, read_raw, list_sources
from data_pipeline.transforms.chain import run_transform_chain, run_all_transforms
from data_pipeline.transforms.normalize import normalize_source
from data_pipeline.alignment.initial_conditions import extract_initial_conditions
from data_pipeline.calibration.nrmsd import nrmsd_direct


@pytest.fixture
def full_pipeline_workspace():
    """Create a complete pipeline workspace with multiple test sources."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        raw_dir = tmpdir / "raw"
        aligned_dir = tmpdir / "aligned"
        cache_dir = tmpdir / "cache"
        db_path = tmpdir / "metadata.db"
        
        raw_dir.mkdir()
        aligned_dir.mkdir()
        cache_dir.mkdir()
        init_db(db_path)
        
        # GCP-style CO2 data
        gcp = pd.DataFrame({
            "country": ["World", "World", "World", "World", "World"],
            "country_code": ["World", "World", "World", "World", "World"],
            "year": [2018, 2019, 2020, 2021, 2022],
            "co2_mt": [33000.0, 34000.0, 33500.0, 35000.0, 36000.0],
            "source_id": ["gcp_fossil_co2"] * 5,
            "source_variable": ["fossil_co2_emissions"] * 5,
            "unit": ["Mt_CO2"] * 5,
        })
        write_raw(gcp, "gcp_fossil_co2", raw_dir)
        
        # NOAA-style CO2 data
        noaa = pd.DataFrame({
            "year": [2018, 2019, 2020, 2021, 2022],
            "co2_ppm": [408.5, 411.4, 414.2, 416.5, 418.6],
            "source_id": ["noaa_co2_annual"] * 5,
            "source_variable": ["co2_annual"] * 5,
        })
        write_raw(noaa, "noaa_co2_annual", raw_dir)
        
        # NASA GISS temperature
        nasa = pd.DataFrame({
            "year": list(range(1880, 1885)),
            "anomaly_c": [-0.16, -0.09, -0.11, -0.18, -0.28],
            "source_id": ["nasa_giss"] * 5,
            "source_variable": ["temp_anomaly"] * 5,
        })
        write_raw(nasa, "nasa_giss", raw_dir)
        
        # FAOSTAT-style food data
        fao = pd.DataFrame({
            "year": list(range(2010, 2015)),
            "value": [2825.19, 2845.39, 2850.37, 2856.01, 2886.77],
            "item": ["Grand Total"] * 5,
            "element": ["Food supply (kcal/capita/day)"] * 5,
            "area_code": ["5000"] * 5,
            "source_id": ["faostat_food_balance"] * 5,
            "source_variable": ["food_balance"] * 5,
            "unit": ["kcal/cap/d"] * 5,
        })
        write_raw(fao, "faostat_food_balance", raw_dir)
        
        # FRED-style GDP data (quarterly)
        fred = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=8, freq="QE"),
            "value": [19000.0, 19500.0, 20000.0, 20500.0, 21000.0, 21500.0, 22000.0, 22500.0],
            "source_id": ["fred_GDP"] * 8,
            "source_variable": ["GDP"] * 8,
        })
        write_raw(fred, "fred_GDP", raw_dir)
        
        yield raw_dir, aligned_dir, db_path


class TestEndToEndPipeline:
    """Full end-to-end pipeline tests."""
    
    def test_full_transform_chain(self, full_pipeline_workspace):
        """Run transform chain on all sources and verify output."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        # Run all transforms
        results = run_all_transforms(raw_dir, aligned_dir, db_path)
        
        # Should produce aligned output for multiple sources
        assert len(results) > 0
        
        # Check GCP transformed correctly
        assert "gcp_fossil_co2" in results
        gcp_paths = results["gcp_fossil_co2"]
        assert len(gcp_paths) >= 1
        
        gcp_aligned = pd.read_parquet(gcp_paths[0])
        assert "year" in gcp_aligned.columns
        assert "value" in gcp_aligned.columns
        assert len(gcp_aligned) == 5
    
    def test_noaa_transformation(self, full_pipeline_workspace):
        """NOAA data should transform to atmospheric.co2 entity."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        paths = run_transform_chain("noaa_co2_annual", raw_dir, aligned_dir, db_path)
        assert len(paths) == 1
        
        df = pd.read_parquet(paths[0])
        assert len(df) == 5
        assert df["year"].tolist() == [2018, 2019, 2020, 2021, 2022]
        assert abs(df["value"].iloc[0] - 408.5) < 0.1
    
    def test_nasa_giss_transformation(self, full_pipeline_workspace):
        """NASA GISS should transform to temperature.anomaly."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        paths = run_transform_chain("nasa_giss", raw_dir, aligned_dir, db_path)
        assert len(paths) == 1
        
        df = pd.read_parquet(paths[0])
        assert len(df) == 5
        assert df["year"].iloc[0] == 1880
        assert abs(df["value"].iloc[0] - (-0.16)) < 0.01
    
    def test_faostat_transformation(self, full_pipeline_workspace):
        """FAOSTAT should produce food supply entity."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        paths = run_transform_chain("faostat_food_balance", raw_dir, aligned_dir, db_path)
        assert len(paths) >= 1
        
        # Check food supply entity exists
        food_paths = [p for p in paths if "food" in p.name.lower() or "kcal" in p.name.lower()]
        assert len(food_paths) >= 1
    
    def test_fred_quarterly_to_annual(self, full_pipeline_workspace):
        """FRED quarterly data should aggregate to annual."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        paths = run_transform_chain("fred_GDP", raw_dir, aligned_dir, db_path)
        assert len(paths) == 1
        
        df = pd.read_parquet(paths[0])
        # 8 quarters → 2 years
        assert len(df) == 2
        assert set(df["year"].tolist()) == {2020, 2021}
    
    def test_initial_conditions_extraction(self, full_pipeline_workspace):
        """Should extract initial conditions from aligned data."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        # First transform everything
        run_all_transforms(raw_dir, aligned_dir, db_path)
        
        # Then extract initial conditions
        conditions = extract_initial_conditions(aligned_dir, target_year=1900)
        
        # Should have entries for mapped entities
        assert len(conditions) > 0
        
        # Some should use defaults (no 1900 data available)
        defaults = [c for c in conditions.values() if c["source"] == "default"]
        aligned = [c for c in conditions.values() if c["source"] == "aligned"]
        
        # At least some should use defaults
        assert len(defaults) > 0
    
    def test_nrmsd_computation_on_aligned_data(self, full_pipeline_workspace):
        """NRMSD should compute on aligned data."""
        raw_dir, aligned_dir, db_path = full_pipeline_workspace
        
        # Transform GCP
        gcp_paths = run_transform_chain("gcp_fossil_co2", raw_dir, aligned_dir, db_path)
        gcp = pd.read_parquet(gcp_paths[0])
        
        # Transform NOAA
        noaa_paths = run_transform_chain("noaa_co2_annual", raw_dir, aligned_dir, db_path)
        noaa = pd.read_parquet(noaa_paths[0])
        
        # Both should have year and value
        assert "year" in gcp.columns
        assert "value" in gcp.columns
        assert "year" in noaa.columns
        assert "value" in noaa.columns
        
        # NRMSD should compute (even if values are very different)
        merged = gcp.merge(noaa, on="year", suffixes=("_gcp", "_noaa"))
        if len(merged) >= 2:
            nrmsd = nrmsd_direct(merged["value_gcp"], merged["value_noaa"])
            assert np.isfinite(nrmsd)
    
    def test_empty_workspace_handles_gracefully(self):
        """Empty workspace should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            aligned_dir = Path(tmpdir) / "aligned"
            db_path = Path(tmpdir) / "metadata.db"
            raw_dir.mkdir()
            aligned_dir.mkdir()
            init_db(db_path)
            
            # Run all transforms on empty workspace
            results = run_all_transforms(raw_dir, aligned_dir, db_path)
            assert results == {}
            
            # Extract initial conditions from empty aligned
            conditions = extract_initial_conditions(aligned_dir)
            # Should return all defaults
            assert len(conditions) > 0
