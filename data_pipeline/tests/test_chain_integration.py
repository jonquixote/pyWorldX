"""Tests for the transform chain end-to-end integration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.transforms.chain import run_transform_chain, run_all_transforms
from data_pipeline.storage.metadata_db import init_db


@pytest.fixture
def temp_pipeline():
    """Create a temporary pipeline workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        raw_dir = tmpdir / "raw"
        aligned_dir = tmpdir / "aligned"
        db_path = tmpdir / "metadata.db"
        raw_dir.mkdir()
        aligned_dir.mkdir()
        init_db(db_path)
        yield raw_dir, aligned_dir, db_path


class TestTransformChainIntegration:
    """Integration tests for the full transform chain."""
    
    def test_gcp_through_chain(self, temp_pipeline):
        """GCP data should flow through normalization → transform → aligned."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        # Create GCP-style raw data
        df = pd.DataFrame({
            "country": ["World", "World", "World"],
            "country_code": ["World", "World", "World"],
            "year": [2020, 2021, 2022],
            "co2_mt": [34000.0, 35000.0, 36000.0],
            "source_id": ["gcp_fossil_co2"] * 3,
            "source_variable": ["fossil_co2_emissions"] * 3,
            "unit": ["Mt_CO2"] * 3,
        })
        df.to_parquet(raw_dir / "gcp_fossil_co2.parquet", index=False)
        
        # Run transform chain
        paths = run_transform_chain("gcp_fossil_co2", raw_dir, aligned_dir, db_path)
        
        assert len(paths) == 1
        result = pd.read_parquet(paths[0])
        assert len(result) == 3
        assert "year" in result.columns
        assert "value" in result.columns
        assert result["year"].tolist() == [2020, 2021, 2022]
    
    def test_fred_through_chain(self, temp_pipeline):
        """FRED quarterly data should be aggregated to annual."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        # Create FRED-style quarterly data
        dates = pd.date_range("2020-01-01", periods=8, freq="QE")
        df = pd.DataFrame({
            "date": dates,
            "value": [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0],
            "source_id": ["fred_GDPDEF"] * 8,
            "source_variable": ["GDPDEF"] * 8,
        })
        df.to_parquet(raw_dir / "fred_GDPDEF.parquet", index=False)
        
        # Run transform chain
        paths = run_transform_chain("fred_GDPDEF", raw_dir, aligned_dir, db_path)
        
        assert len(paths) == 1
        result = pd.read_parquet(paths[0])
        # Should have 2 years (2020, 2021) with quarterly means
        assert len(result) == 2
        assert result[result["year"] == 2020]["value"].iloc[0] == pytest.approx(103.0)
        assert result[result["year"] == 2021]["value"].iloc[0] == pytest.approx(111.0)
    
    def test_primap_through_chain(self, temp_pipeline):
        """PRIMAP wide format should be melted and aggregated."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        # Create PRIMAP-style wide data
        df = pd.DataFrame({
            "area_(iso3)": ["EARTH", "EARTH"],
            "unit": ["CO2 * gigagram / a"] * 2,
            "1990": [1000.0, 500.0],
            "1991": [1100.0, 550.0],
            "source_id": ["primap_hist"] * 2,
            "source_variable": ["ghg_emissions_multi_gas"] * 2,
        })
        df.to_parquet(raw_dir / "primap_hist.parquet", index=False)
        
        # Run transform chain
        paths = run_transform_chain("primap_hist", raw_dir, aligned_dir, db_path)
        
        assert len(paths) == 1
        result = pd.read_parquet(paths[0])
        assert len(result) == 2  # 2 years
        assert result[result["year"] == 1990]["value"].iloc[0] == pytest.approx(1.5)  # kt → Mt
    
    def test_ceds_through_chain(self, temp_pipeline):
        """CEDS wide format should be melted and aggregated."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        # Create CEDS-style wide data
        df = pd.DataFrame({
            "em": ["SO2"] * 3,
            "sector": ["1A1a", "1A1a", "1A1a"],
            "fuel": ["biomass", "coal", "oil"],
            "units": ["ktSO2"] * 3,
            "x2020": [10.0, 100.0, 200.0],
            "x2021": [12.0, 110.0, 210.0],
            "source_id": ["ceds_so2"] * 3,
            "source_variable": ["so2_emissions"] * 3,
        })
        df.to_parquet(raw_dir / "ceds_so2.parquet", index=False)
        
        # Run transform chain
        paths = run_transform_chain("ceds_so2", raw_dir, aligned_dir, db_path)
        
        assert len(paths) == 1
        result = pd.read_parquet(paths[0])
        assert len(result) == 2  # 2 years
        assert result[result["year"] == 2020]["value"].iloc[0] == pytest.approx(310.0)
    
    def test_empty_raw_returns_empty(self, temp_pipeline):
        """Empty raw file should return no aligned output."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        # Create empty DataFrame
        df = pd.DataFrame()
        df.to_parquet(raw_dir / "test_empty.parquet", index=False)
        
        paths = run_transform_chain("test_empty", raw_dir, aligned_dir, db_path)
        assert len(paths) == 0
    
    def test_no_mapping_returns_empty(self, temp_pipeline):
        """Source without ontology mapping should return no aligned output."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        df = pd.DataFrame({
            "year": [2020, 2021],
            "value": [100.0, 200.0],
            "source_id": ["unknown_source"] * 2,
        })
        df.to_parquet(raw_dir / "unknown_source.parquet", index=False)
        
        paths = run_transform_chain("unknown_source", raw_dir, aligned_dir, db_path)
        assert len(paths) == 0


class TestRunAllTransforms:
    """Test the run_all_transforms function."""
    
    def test_processes_multiple_sources(self, temp_pipeline):
        """Should process all sources in raw store."""
        raw_dir, aligned_dir, db_path = temp_pipeline
        
        # Create multiple raw sources
        gcp = pd.DataFrame({
            "country": ["World"],
            "country_code": ["World"],
            "year": [2020],
            "co2_mt": [34000.0],
            "source_id": ["gcp_fossil_co2"],
            "source_variable": ["fossil_co2_emissions"],
            "unit": ["Mt_CO2"],
        })
        gcp.to_parquet(raw_dir / "gcp_fossil_co2.parquet", index=False)
        
        noaa = pd.DataFrame({
            "year": [2020],
            "co2_ppm": [414.0],
            "source_id": ["noaa_co2_annual"],
            "source_variable": ["co2_annual"],
        })
        noaa.to_parquet(raw_dir / "noaa_co2_annual.parquet", index=False)
        
        # Run all transforms
        results = run_all_transforms(raw_dir, aligned_dir, db_path)
        
        assert "gcp_fossil_co2" in results
        assert "noaa_co2_annual" in results
        assert len(results["gcp_fossil_co2"]) == 1
        assert len(results["noaa_co2_annual"]) == 1
