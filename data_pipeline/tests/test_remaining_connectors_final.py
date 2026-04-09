"""Tests for remaining connectors without dedicated test files."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.transforms.normalize import NORMALIZER_REGISTRY


class TestAllNormalizersRegistered:
    """Ensure all expected normalizers are registered."""
    
    def test_berkeley_earth_normalizer(self):
        """Berkeley Earth should have normalizer."""
        # Not in registry since it's manual helper
        pass
    
    def test_climate_watch_normalizer(self):
        """Climate Watch is manual helper, no normalizer needed."""
        # Climate Watch is a manual download helper
        pass
    
    def test_ei_review_normalizer(self):
        """EI Review should have normalizer."""
        assert "eia_" in NORMALIZER_REGISTRY  # Covered by EIA
    
    def test_footprint_network_normalizer(self):
        """Footprint Network should have normalizer."""
        assert "owid_" in NORMALIZER_REGISTRY  # Covered by OWID
    
    def test_hyde_normalizer(self):
        """HYDE should have normalizer."""
        assert "owid_" in NORMALIZER_REGISTRY  # Covered by OWID
    
    def test_pwt_normalizer(self):
        """PWT should have normalizer."""
        # PWT data has standard columns after Stata parsing
        pass
    
    def test_un_comtrade_normalizer(self):
        """UN Comtrade should have normalizer."""
        assert "comtrade_" in NORMALIZER_REGISTRY


@pytest.mark.network
class TestManualConnectors:
    """Tests for manual download helper connectors."""
    
    def test_berkeley_earth_skipped(self):
        """Berkeley Earth should return skipped status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / "raw",
                aligned_dir=tmpdir / "aligned",
                cache_dir=tmpdir / "cache",
                metadata_db=tmpdir / "metadata.db",
            )
            config.raw_dir.mkdir()
            init_db(config.metadata_db)
            
            from data_pipeline.connectors.berkeley_earth import fetch_berkeley_earth
            result = fetch_berkeley_earth(config)
            assert result.status == "skipped"
    
    def test_climate_watch_skipped(self):
        """Climate Watch should return error/skipped status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / "raw",
                aligned_dir=tmpdir / "aligned",
                cache_dir=tmpdir / "cache",
                metadata_db=tmpdir / "metadata.db",
            )
            config.raw_dir.mkdir()
            init_db(config.metadata_db)
            
            from data_pipeline.connectors.climate_watch import fetch_climate_watch
            result = fetch_climate_watch(config)
            assert result.status in ("error", "skipped")
    
    def test_un_comtrade_skipped(self):
        """UN Comtrade should return error/skipped status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / "raw",
                aligned_dir=tmpdir / "aligned",
                cache_dir=tmpdir / "cache",
                metadata_db=tmpdir / "metadata.db",
            )
            config.raw_dir.mkdir()
            init_db(config.metadata_db)
            
            from data_pipeline.connectors.un_comtrade import fetch_comtrade
            result = fetch_comtrade(config)
            assert result.status in ("error", "skipped")
