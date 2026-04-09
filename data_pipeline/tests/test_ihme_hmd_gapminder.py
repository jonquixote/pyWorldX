"""Tests for IHME GBD, HMD, and Gapminder connectors."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.transforms.normalize import NORMALIZER_REGISTRY, normalize_source


@pytest.mark.network
class TestIHMEGBDConnector:
    """Tests for IHME GBD connector."""
    
    def test_fetch_dalys(self):
        """Should fetch DALYs data via OWID."""
        from data_pipeline.connectors.ihme_gbd import fetch_ihme_gbd
        
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
            
            result = fetch_ihme_gbd(config, indicator="dalys")
            assert result.status == "success"
            assert result.records_fetched > 0
    
    def test_unknown_indicator_returns_error(self):
        """Unknown indicator should return error."""
        from data_pipeline.connectors.ihme_gbd import fetch_ihme_gbd
        
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
            
            result = fetch_ihme_gbd(config, indicator="unknown")
            assert result.status == "error"


@pytest.mark.network
class TestHMDConnector:
    """Tests for HMD connector."""
    
    def test_fetch_life_expectancy(self):
        """Should fetch life expectancy data via OWID."""
        from data_pipeline.connectors.hmd import fetch_hmd
        
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
            
            result = fetch_hmd(config, indicator="life_expectancy")
            assert result.status == "success"
            assert result.records_fetched > 0


@pytest.mark.network
class TestGapminderConnector:
    """Tests for Gapminder connector."""
    
    def test_fetch_population(self):
        """Should fetch population data via World Bank."""
        from data_pipeline.connectors.gapminder import fetch_gapminder
        
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
            
            result = fetch_gapminder(config, indicator="population")
            assert result.status == "success"
            assert result.records_fetched > 0


class TestNewNormalizers:
    """Tests for new normalizers."""
    
    def test_ihme_gbd_normalizer_registered(self):
        """IHME GBD normalizer should be registered."""
        assert "ihme_gbd_" in NORMALIZER_REGISTRY
    
    def test_hmd_normalizer_registered(self):
        """HMD normalizer should be registered."""
        assert "hmd_" in NORMALIZER_REGISTRY
    
    def test_gapminder_normalizer_registered(self):
        """Gapminder normalizer should be registered."""
        assert "gapminder_" in NORMALIZER_REGISTRY
    
    def test_ihme_gbd_normalizer(self):
        """Should normalize IHME GBD data."""
        df = pd.DataFrame({
            "entity": ["USA", "China"],
            "year": [2020, 2020],
            "value": [100.0, 200.0],
        })
        result = normalize_source(df, "ihme_gbd_dalys")
        assert "country_code" in result.columns
        assert result["country_code"].tolist() == ["USA", "China"]
    
    def test_hmd_normalizer(self):
        """Should normalize HMD data."""
        df = pd.DataFrame({
            "entity": ["USA", "UK"],
            "year": [2020, 2020],
            "value": [78.0, 81.0],
        })
        result = normalize_source(df, "hmd_life_expectancy")
        assert "country_code" in result.columns
    
    def test_gapminder_normalizer(self):
        """Should normalize Gapminder data."""
        df = pd.DataFrame({
            "date": ["2020", "2021"],
            "value": ["7.8e9", "7.9e9"],
            "countryiso3code": ["WLD", "WLD"],
        })
        result = normalize_source(df, "gapminder_population")
        assert "year" in result.columns
        assert "value" in result.columns
        assert "country_code" in result.columns
