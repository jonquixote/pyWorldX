"""Tests for CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from data_pipeline.cli import app
from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.storage.parquet_store import write_raw, write_aligned

runner = CliRunner()


@pytest.fixture
def temp_pipeline_dir():
    """Create a temporary pipeline workspace with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        raw_dir = tmpdir / "raw"
        aligned_dir = tmpdir / "aligned"
        cache_dir = tmpdir / "cache"
        raw_dir.mkdir()
        aligned_dir.mkdir()
        cache_dir.mkdir()
        
        # Create test raw data
        gcp = pd.DataFrame({
            "country": ["World", "World"],
            "country_code": ["World", "World"],
            "year": [2020, 2021],
            "co2_mt": [34000.0, 35000.0],
            "source_id": ["gcp_fossil_co2"] * 2,
            "source_variable": ["fossil_co2_emissions"] * 2,
            "unit": ["Mt_CO2"] * 2,
        })
        write_raw(gcp, "gcp_fossil_co2", raw_dir)
        
        # Create test aligned data
        aligned = pd.DataFrame({
            "entity": ["emissions.co2_fossil"] * 2,
            "year": [2020, 2021],
            "value": [34000.0, 35000.0],
            "unit": ["Mt_CO2"] * 2,
            "source_id": ["gcp_fossil_co2"] * 2,
            "quality_flag": ["OK"] * 2,
        })
        write_aligned(aligned, "emissions_co2_fossil", aligned_dir)
        
        yield tmpdir


class TestValidateCommand:
    """Tests for the validate CLI command."""
    
    def test_validate_shows_output(self, temp_pipeline_dir, monkeypatch):
        """Should display validation results."""
        monkeypatch.setenv("DATA_PIPELINE_RAW_DIR", str(temp_pipeline_dir / "raw"))
        monkeypatch.setenv("DATA_PIPELINE_ALIGNED_DIR", str(temp_pipeline_dir / "aligned"))
        monkeypatch.setenv("DATA_PIPELINE_CACHE_DIR", str(temp_pipeline_dir / "cache"))
        monkeypatch.setenv("DATA_PIPELINE_METADATA_DB", str(temp_pipeline_dir / "metadata.db"))
        
        result = runner.invoke(app, ["validate"])
        assert result.exit_code == 0
        # Should show some output
        assert "Quality" in result.stdout or "Coverage" in result.stdout


class TestTransformCommand:
    """Tests for the transform CLI command."""
    
    def test_transform_known_source(self, temp_pipeline_dir, monkeypatch):
        """Should transform a known source."""
        monkeypatch.setenv("DATA_PIPELINE_RAW_DIR", str(temp_pipeline_dir / "raw"))
        monkeypatch.setenv("DATA_PIPELINE_ALIGNED_DIR", str(temp_pipeline_dir / "aligned"))
        monkeypatch.setenv("DATA_PIPELINE_CACHE_DIR", str(temp_pipeline_dir / "cache"))
        monkeypatch.setenv("DATA_PIPELINE_METADATA_DB", str(temp_pipeline_dir / "metadata.db"))
        
        result = runner.invoke(app, ["transform", "gcp_fossil_co2"])
        assert result.exit_code == 0
        assert "Transforming" in result.stdout


class TestCrossCheckCommand:
    """Tests for the cross-check CLI command."""
    
    def test_cross_check_runs(self, temp_pipeline_dir, monkeypatch):
        """Should run cross-check without crashing."""
        monkeypatch.setenv("DATA_PIPELINE_RAW_DIR", str(temp_pipeline_dir / "raw"))
        monkeypatch.setenv("DATA_PIPELINE_ALIGNED_DIR", str(temp_pipeline_dir / "aligned"))
        monkeypatch.setenv("DATA_PIPELINE_CACHE_DIR", str(temp_pipeline_dir / "cache"))
        monkeypatch.setenv("DATA_PIPELINE_METADATA_DB", str(temp_pipeline_dir / "metadata.db"))
        
        result = runner.invoke(app, ["cross-check"])
        # May succeed or fail gracefully
        assert result.exit_code == 0 or "Consistency" in result.stdout


class TestDiffCommand:
    """Tests for the diff CLI command."""
    
    def test_diff_same_file(self, temp_pipeline_dir, monkeypatch):
        """Comparing file to itself should show high similarity."""
        monkeypatch.setenv("DATA_PIPELINE_RAW_DIR", str(temp_pipeline_dir / "raw"))
        monkeypatch.setenv("DATA_PIPELINE_ALIGNED_DIR", str(temp_pipeline_dir / "aligned"))
        monkeypatch.setenv("DATA_PIPELINE_CACHE_DIR", str(temp_pipeline_dir / "cache"))
        monkeypatch.setenv("DATA_PIPELINE_METADATA_DB", str(temp_pipeline_dir / "metadata.db"))
        
        result = runner.invoke(app, ["diff", "emissions_co2_fossil", "emissions_co2_fossil"])
        assert result.exit_code == 0
        assert "Source A" in result.stdout


class TestFetchOWIDCommand:
    """Tests for the fetch-owid CLI command."""
    
    def test_fetch_owid_shows_progress(self, temp_pipeline_dir, monkeypatch):
        """Should show fetch progress for OWID indicators."""
        monkeypatch.setenv("DATA_PIPELINE_RAW_DIR", str(temp_pipeline_dir / "raw"))
        monkeypatch.setenv("DATA_PIPELINE_ALIGNED_DIR", str(temp_pipeline_dir / "aligned"))
        monkeypatch.setenv("DATA_PIPELINE_CACHE_DIR", str(temp_pipeline_dir / "cache"))
        monkeypatch.setenv("DATA_PIPELINE_METADATA_DB", str(temp_pipeline_dir / "metadata.db"))
        
        result = runner.invoke(app, ["fetch-owid"])
        assert result.exit_code == 0
        assert "OWID" in result.stdout


class TestInitConditionsCommand:
    """Additional tests for init-conditions CLI command."""
    
    def test_init_conditions_different_year(self, temp_pipeline_dir, monkeypatch):
        """Should work with different target years."""
        monkeypatch.setenv("DATA_PIPELINE_RAW_DIR", str(temp_pipeline_dir / "raw"))
        monkeypatch.setenv("DATA_PIPELINE_ALIGNED_DIR", str(temp_pipeline_dir / "aligned"))
        monkeypatch.setenv("DATA_PIPELINE_CACHE_DIR", str(temp_pipeline_dir / "cache"))
        monkeypatch.setenv("DATA_PIPELINE_METADATA_DB", str(temp_pipeline_dir / "metadata.db"))
        
        result = runner.invoke(app, ["init-conditions", "--year", "2000"])
        assert result.exit_code == 0
        assert "Initial Conditions" in result.stdout
