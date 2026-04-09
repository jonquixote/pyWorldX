"""Tests for NASA Earthdata connector."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.connectors.nasa_earthdata import (
    DATASETS,
    fetch_nasa_earthdata,
)
from data_pipeline.config import PipelineConfig
from data_pipeline.storage.parquet_store import write_raw


class TestNasaEarthdataDatasets:
    """Tests for NASA Earthdata dataset definitions."""
    
    def test_has_expected_datasets(self):
        """Should have key dataset definitions."""
        assert "giss_temp" in DATASETS
        assert "merra2" in DATASETS
        assert "ceres_ebaf" in DATASETS
    
    def test_each_dataset_has_required_fields(self):
        """Each dataset should have name, url, format, coverage."""
        for key, info in DATASETS.items():
            assert "name" in info
            assert "url" in info
            assert "format" in info
            assert "coverage" in info
            assert "note" in info
    
    def test_giss_temp_references_nasa_giss(self):
        """GISTEMP dataset should note it's already in nasa_giss connector."""
        assert "nasa_giss" in DATASETS["giss_temp"]["note"].lower()


class TestNasaEarthdataFetcher:
    """Tests for the NASA Earthdata fetch function."""
    
    def test_unknown_dataset_returns_error(self):
        """Unknown dataset should return error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(
                raw_dir=Path(tmpdir) / "raw",
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            config.raw_dir.mkdir()
            
            result = fetch_nasa_earthdata(config, dataset="nonexistent")
            assert result.status == "error"
    
    def test_missing_file_returns_skipped(self):
        """Missing local file should return skipped status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(
                raw_dir=Path(tmpdir) / "raw",
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            config.raw_dir.mkdir()
            
            result = fetch_nasa_earthdata(config, dataset="merra2")
            assert result.status == "skipped"
            assert "File not found" in result.error_message
    
    def test_existing_file_returns_success(self):
        """Existing local file should return success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            # Create a dummy file
            dummy_file = raw_dir / "nasa_earthdata_merra2.nc"
            dummy_file.write_bytes(b"dummy netcdf content")
            
            config = PipelineConfig(
                raw_dir=raw_dir,
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            
            result = fetch_nasa_earthdata(config, dataset="merra2")
            assert result.status == "success"
            assert result.records_fetched == 1
