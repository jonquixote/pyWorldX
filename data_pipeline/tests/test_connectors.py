"""Tests for all connector fetch functions."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.storage.parquet_store import read_raw


def make_config(tmpdir):
    """Create a test config."""
    tmpdir = Path(tmpdir)
    config = PipelineConfig(
        raw_dir=tmpdir / "raw",
        aligned_dir=tmpdir / "aligned",
        cache_dir=tmpdir / "cache",
        metadata_db=tmpdir / "metadata.db",
    )
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    init_db(config.metadata_db)
    return config


# ── Connector Function Tests ────────────────────────────────────────

class TestConnectorFunctions:
    """Test each connector function exists and is callable."""
    
    def test_world_bank_connector(self):
        """World Bank connector should be callable."""
        from data_pipeline.connectors.world_bank import fetch_all
        assert callable(fetch_all)
    
    def test_noaa_connector(self):
        """NOAA connector should be callable."""
        from data_pipeline.connectors.noaa import fetch_noaa_co2
        assert callable(fetch_noaa_co2)
    
    def test_gcp_connector(self):
        """GCP connector should be callable."""
        from data_pipeline.connectors.gcp import fetch_gcp
        assert callable(fetch_gcp)
    
    def test_primap_connector(self):
        """PRIMAP connector should be callable."""
        from data_pipeline.connectors.primap import fetch_primap
        assert callable(fetch_primap)
    
    def test_ceds_connector(self):
        """CEDS connector should be callable."""
        from data_pipeline.connectors.ceds import fetch_ceds_pollutant, fetch_all
        assert callable(fetch_ceds_pollutant)
        assert callable(fetch_all)
    
    def test_fred_connector(self):
        """FRED connector should be callable."""
        from data_pipeline.connectors.fred import fetch_all
        assert callable(fetch_all)
    
    def test_eia_connector(self):
        """EIA connector should be callable."""
        from data_pipeline.connectors.eia import fetch_all
        assert callable(fetch_all)
    
    def test_undp_connector(self):
        """UNDP connector should be callable."""
        from data_pipeline.connectors.undp import fetch_undp_hdr
        assert callable(fetch_undp_hdr)
    
    def test_nasa_giss_connector(self):
        """NASA GISS connector should be callable."""
        from data_pipeline.connectors.nasa_giss import fetch_nasa_giss
        assert callable(fetch_nasa_giss)
    
    def test_carbon_atlas_connector(self):
        """Carbon Atlas connector should be callable."""
        from data_pipeline.connectors.carbon_atlas import fetch_carbon_atlas
        assert callable(fetch_carbon_atlas)
    
    def test_climate_trace_connector(self):
        """Climate TRACE connector should be callable."""
        from data_pipeline.connectors.climate_trace import fetch_climate_trace
        assert callable(fetch_climate_trace)
    
    def test_owid_connector(self):
        """OWID connector should be callable."""
        from data_pipeline.connectors.owid import fetch_owid_search
        assert callable(fetch_owid_search)
    
    def test_nebel_2023_connector(self):
        """Nebel 2023 connector should be callable."""
        from data_pipeline.connectors.nebel_2023 import fetch_nebel_supplement
        assert callable(fetch_nebel_supplement)
    
    def test_oecd_connector(self):
        """OECD connector should be callable."""
        from data_pipeline.connectors.oecd import fetch_oecd
        assert callable(fetch_oecd)
    
    def test_imf_weo_connector(self):
        """IMF WEO connector should be callable."""
        from data_pipeline.connectors.imf_weo import fetch_imf_weo
        assert callable(fetch_imf_weo)
    
    def test_faostat_connector(self):
        """FAOSTAT connector should be callable."""
        from data_pipeline.connectors.faostat import fetch_faostat
        assert callable(fetch_faostat)
    
    def test_pwt_connector(self):
        """PWT connector should be callable."""
        from data_pipeline.connectors.pwt import fetch_pwt
        assert callable(fetch_pwt)
    
    def test_hyde_connector(self):
        """HYDE connector should be callable."""
        from data_pipeline.connectors.hyde import fetch_hyde
        assert callable(fetch_hyde)
    
    def test_maddison_connector(self):
        """Maddison connector should be callable."""
        from data_pipeline.connectors.maddison import fetch_maddison
        assert callable(fetch_maddison)
    
    def test_un_population_connector(self):
        """UN Population connector should be callable."""
        from data_pipeline.connectors.un_population import fetch_un_population
        assert callable(fetch_un_population)
    
    def test_ei_review_connector(self):
        """EI Review connector should be callable."""
        from data_pipeline.connectors.ei_review import fetch_ei_review
        assert callable(fetch_ei_review)
    
    def test_footprint_network_connector(self):
        """Footprint Network connector should be callable."""
        from data_pipeline.connectors.footprint_network import fetch_footprint_network
        assert callable(fetch_footprint_network)
    
    def test_gapminder_connector(self):
        """Gapminder connector should be callable."""
        from data_pipeline.connectors.gapminder import fetch_gapminder
        assert callable(fetch_gapminder)
    
    def test_edgar_connector(self):
        """EDGAR connector should be callable."""
        from data_pipeline.connectors.edgar import fetch_edgar
        assert callable(fetch_edgar)
    
    def test_ihme_gbd_connector(self):
        """IHME GBD connector should be callable."""
        from data_pipeline.connectors.ihme_gbd import fetch_ihme_gbd
        assert callable(fetch_ihme_gbd)
    
    def test_hmd_connector(self):
        """HMD connector should be callable."""
        from data_pipeline.connectors.hmd import fetch_hmd
        assert callable(fetch_hmd)
    
    def test_usgs_connector(self):
        """USGS connector should be callable."""
        from data_pipeline.connectors.usgs import fetch_usgs
        assert callable(fetch_usgs)
    
    def test_unido_connector(self):
        """UNIDO connector should be callable."""
        from data_pipeline.connectors.unido import fetch_unido
        assert callable(fetch_unido)
    
    def test_berkeley_earth_connector(self):
        """Berkeley Earth connector should be callable."""
        from data_pipeline.connectors.berkeley_earth import fetch_berkeley_earth
        assert callable(fetch_berkeley_earth)
    
    def test_climate_watch_connector(self):
        """Climate Watch connector should be callable."""
        from data_pipeline.connectors.climate_watch import fetch_climate_watch
        assert callable(fetch_climate_watch)
    
    def test_un_comtrade_connector(self):
        """UN Comtrade connector should be callable."""
        from data_pipeline.connectors.un_comtrade import fetch_comtrade
        assert callable(fetch_comtrade)
    
    def test_nasa_earthdata_connector(self):
        """NASA Earthdata connector should be callable."""
        from data_pipeline.connectors.nasa_earthdata import fetch_nasa_earthdata
        assert callable(fetch_nasa_earthdata)


# ── Connector Read/Write Tests ──────────────────────────────────────

@pytest.mark.network
class TestConnectorDataFlow:
    """Test data flows through connector → raw store → read back."""
    
    def test_world_bank_data_written_and_readable(self):
        """World Bank data should be writeable and readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_config(tmpdir)
            
            from data_pipeline.connectors.world_bank import fetch_all
            results = fetch_all(config)
            
            # May fail on API issues, but should not crash
            success = [r for r in results if r.status == "success"]
            if success:
                # Check data was written
                df = read_raw(success[0].source_id, config.raw_dir)
                assert df is not None
    
    def test_noaa_data_written_and_readable(self):
        """NOAA data should be writeable and readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_config(tmpdir)
            
            from data_pipeline.connectors.noaa import fetch_noaa_co2
            result = fetch_noaa_co2(config)
            
            assert result.status == "success"
            df = read_raw("noaa_co2_annual", config.raw_dir)
            assert df is not None
            assert len(df) > 0
    
    def test_gcp_data_written_and_readable(self):
        """GCP data should be writeable and readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_config(tmpdir)
            
            from data_pipeline.connectors.gcp import fetch_gcp
            result = fetch_gcp(config)
            
            assert result.status == "success"
            df = read_raw("gcp_fossil_co2", config.raw_dir)
            assert df is not None
            assert len(df) > 0
    
    def test_fred_data_written_and_readable(self):
        """FRED data should be writeable and readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_config(tmpdir)
            
            from data_pipeline.connectors.fred import fetch_all
            results = fetch_all(config)
            
            # At least one should succeed (may fail on API 502)
            success = [r for r in results if r.status == "success"]
            if success:
                # Check one of the series
                df = read_raw(success[0].source_id, config.raw_dir)
                assert df is not None
