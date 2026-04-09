"""Tests for EDGAR connector."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db


@pytest.mark.network
class TestEDGARConnector:
    """Tests for EDGAR GHG emissions connector."""
    
    def test_fetch_co2(self):
        """Should fetch CO2 data from EDGAR."""
        from data_pipeline.connectors.edgar import fetch_edgar
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / 'raw',
                aligned_dir=tmpdir / 'aligned',
                cache_dir=tmpdir / 'cache',
                metadata_db=tmpdir / 'metadata.db',
            )
            config.raw_dir.mkdir()
            init_db(config.metadata_db)
            
            result = fetch_edgar(config, gas="co2")
            assert result.status == "success"
            assert result.records_fetched > 0
    
    def test_unknown_gas_returns_error(self):
        """Unknown gas should return error."""
        from data_pipeline.connectors.edgar import fetch_edgar
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / 'raw',
                aligned_dir=tmpdir / 'aligned',
                cache_dir=tmpdir / 'cache',
                metadata_db=tmpdir / 'metadata.db',
            )
            config.raw_dir.mkdir()
            init_db(config.metadata_db)
            
            result = fetch_edgar(config, gas="unknown")
            assert result.status == "error"


class TestEDGARNormalizer:
    """Tests for EDGAR normalizer."""
    
    def test_normalizer_registered(self):
        """EDGAR normalizer should be registered."""
        from data_pipeline.transforms.normalize import NORMALIZER_REGISTRY
        assert "edgar_" in NORMALIZER_REGISTRY
    
    def test_normalizer_handles_data(self):
        """Should normalize EDGAR data."""
        import pandas as pd
        from data_pipeline.transforms.normalize import normalize_source
        
        df = pd.DataFrame({
            "country_code": ["USA", "CHN", "World"],
            "year": [2020, 2020, 2020],
            "value": [5000.0, 10000.0, 15000.0],
            "source_id": ["edgar_co2"] * 3,
            "source_variable": ["co2"] * 3,
        })
        result = normalize_source(df, "edgar_co2")
        assert "year" in result.columns
        assert "value" in result.columns
        assert "country_code" in result.columns
