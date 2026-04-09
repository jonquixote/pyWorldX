"""Tests for Nebel 2023 calibration transform module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.storage.parquet_store import write_raw


class TestNebelTransforms:
    """Tests for Nebel 2023 calibration reconstruction functions."""
    
    def test_reconstruct_industrial_output_callable(self):
        """Should be callable."""
        from data_pipeline.transforms.nebcal_transform import reconstruct_industrial_output
        assert callable(reconstruct_industrial_output)
    
    def test_reconstruct_food_production_callable(self):
        """Should be callable."""
        from data_pipeline.transforms.nebcal_transform import reconstruct_food_production
        assert callable(reconstruct_food_production)
    
    def test_reconstruct_pollution_proxy_callable(self):
        """Should be callable."""
        from data_pipeline.transforms.nebcal_transform import reconstruct_pollution_proxy
        assert callable(reconstruct_pollution_proxy)
    
    def test_reconstruct_service_output_callable(self):
        """Should be callable."""
        from data_pipeline.transforms.nebcal_transform import reconstruct_service_output
        assert callable(reconstruct_service_output)
    
    def test_reconstruct_food_production_raises_not_implemented(self):
        """Should raise NotImplementedError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            from data_pipeline.transforms.nebcal_transform import reconstruct_food_production
            with pytest.raises(NotImplementedError):
                reconstruct_food_production(raw_dir)
    
    def test_reconstruct_service_output_raises_not_implemented(self):
        """Should raise NotImplementedError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            from data_pipeline.transforms.nebcal_transform import reconstruct_service_output
            with pytest.raises(NotImplementedError):
                reconstruct_service_output(raw_dir)
    
    def test_reconstruct_industrial_output_raises_if_missing(self):
        """Should raise FileNotFoundError if no GDP data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            from data_pipeline.transforms.nebcal_transform import reconstruct_industrial_output
            with pytest.raises(FileNotFoundError):
                reconstruct_industrial_output(raw_dir)
    
    def test_reconstruct_pollution_proxy_raises_if_missing(self):
        """Should raise FileNotFoundError if no CO2 data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            from data_pipeline.transforms.nebcal_transform import reconstruct_pollution_proxy
            with pytest.raises(FileNotFoundError):
                reconstruct_pollution_proxy(raw_dir)
    
    def test_reconstruct_pollution_proxy_with_gcp_data(self):
        """Should reconstruct pollution proxy from GCP data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            # Write mock GCP data
            gcp = pd.DataFrame({
                "country": ["World"] * 5,
                "country_code": ["World"] * 5,
                "year": [1970, 1980, 1990, 2000, 2010],
                "co2_mt": [14000.0, 19000.0, 22000.0, 26000.0, 33000.0],
            })
            write_raw(gcp, "gcp_fossil_co2", raw_dir)
            
            from data_pipeline.transforms.nebcal_transform import reconstruct_pollution_proxy
            result = reconstruct_pollution_proxy(raw_dir, co2_sources=["gcp_fossil_co2"])
            
            assert "year" in result.columns
            assert "country_code" in result.columns
            assert "pollution_index" in result.columns
            assert len(result) > 0
            # 1970 should be base = 1.0
            base = result[result["year"] == 1970]
            if len(base) > 0:
                assert base["pollution_index"].iloc[0] == pytest.approx(1.0)
    
    def test_module_imports(self):
        """Module should import all required dependencies."""
        from data_pipeline.transforms import nebcal_transform
        assert hasattr(nebcal_transform, "reconstruct_industrial_output")
        assert hasattr(nebcal_transform, "reconstruct_food_production")
        assert hasattr(nebcal_transform, "reconstruct_pollution_proxy")
        assert hasattr(nebcal_transform, "reconstruct_service_output")
