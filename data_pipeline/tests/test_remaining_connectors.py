"""Tests for remaining connectors without dedicated test files."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.parquet_store import write_raw, read_raw
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.transforms.normalize import (
    NORMALIZER_REGISTRY,
    normalize_source,
    normalize_imf_weo,
    normalize_nebel_2023,
    normalize_usgs,
)


# ── Normalizer Tests ──────────────────────────────────────────────────

class TestIMFWEONormalizer:
    """Tests for IMF WEO normalization."""
    
    def test_passes_through_metadata(self):
        """WEO metadata should pass through unchanged."""
        df = pd.DataFrame({
            "source_id": ["imf_weo"],
            "source_variable": ["imf_weo"],
            "sheet_name": ["Historical"],
        })
        result = normalize_imf_weo(df)
        assert len(result) == 1
        assert "source_id" in result.columns
    
    def test_handles_date_column(self):
        """Should convert Date column to year."""
        df = pd.DataFrame({
            "Date": [2020, 2021, 2022],
            "value": [100.0, 110.0, 120.0],
        })
        result = normalize_imf_weo(df)
        assert "year" in result.columns


class TestNebel2023Normalizer:
    """Tests for Nebel 2023 normalization."""
    
    def test_passes_through_metadata(self):
        """Nebel metadata should pass through unchanged."""
        df = pd.DataFrame({
            "source_id": ["nebel_2023_supplement"],
            "source_variable": ["supplement"],
            "url": ["https://example.com"],
        })
        result = normalize_nebel_2023(df)
        assert len(result) == 1
        assert result["source_id"].iloc[0] == "nebel_2023_supplement"


class TestUSGSNormalizer:
    """Tests for USGS normalization."""
    
    def test_passes_through_metadata(self):
        """USGS metadata should pass through unchanged."""
        df = pd.DataFrame({
            "source_id": ["usgs_mcs"],
            "url": ["https://example.com"],
            "fetched_at": ["2026-04-08T00:00:00+00:00"],
        })
        result = normalize_usgs(df)
        assert len(result) == 1
    
    def test_extracts_year_from_fetched_at(self):
        """Should extract year from fetched_at."""
        df = pd.DataFrame({
            "source_id": ["usgs_mcs"],
            "fetched_at": ["2026-04-08T00:00:00+00:00"],
        })
        result = normalize_usgs(df)
        assert "year" in result.columns


# ── Connector Fetch Tests ─────────────────────────────────────────────

@pytest.mark.network
class TestIMFWEOConnector:
    """Tests for IMF WEO connector."""
    
    def test_auto_download_works(self):
        """IMF WEO should auto-download from the working URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            config = PipelineConfig(
                raw_dir=raw_dir,
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            
            from data_pipeline.connectors.imf_weo import fetch_imf_weo
            result = fetch_imf_weo(config)
            # IMF URL is working, so this should succeed
            assert result.status == "success"
            assert result.records_fetched == 2


class TestNasaEarthdataConnector:
    """Tests for NASA Earthdata connector."""
    
    def test_fetch_with_local_file(self):
        """Should process local NetCDF file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            # Create a dummy file
            dummy_file = raw_dir / "nasa_earthdata_merra2.nc"
            dummy_file.write_bytes(b"dummy content")
            
            config = PipelineConfig(
                raw_dir=raw_dir,
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            
            from data_pipeline.connectors.nasa_earthdata import fetch_nasa_earthdata
            result = fetch_nasa_earthdata(config, dataset="merra2")
            assert result.status == "success"
            assert result.records_fetched == 1


@pytest.mark.network
class TestGapminderConnector:
    """Tests for Gapminder connector."""
    
    def test_auto_fetch_works(self):
        """Should fetch population data via World Bank."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            config = PipelineConfig(
                raw_dir=raw_dir,
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            init_db(config.metadata_db)
            
            from data_pipeline.connectors.gapminder import fetch_gapminder
            result = fetch_gapminder(config, indicator="population")
            assert result.status == "success"
            assert result.records_fetched > 0


@pytest.mark.network
class TestUNPopulationConnector:
    """Tests for UN Population connector."""
    
    def test_auto_fetch_works(self):
        """Should fetch population data via HDX."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            config = PipelineConfig(
                raw_dir=raw_dir,
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            init_db(config.metadata_db)
            
            from data_pipeline.connectors.un_population import fetch_un_population
            result = fetch_un_population(config)
            assert result.status == "success"
            assert result.records_fetched > 0


@pytest.mark.network
class TestUNIDOConnector:
    """Tests for UNIDO connector."""
    
    def test_auto_fetch_works(self):
        """Should fetch manufacturing data via World Bank."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            config = PipelineConfig(
                raw_dir=raw_dir,
                aligned_dir=Path(tmpdir) / "aligned",
                cache_dir=Path(tmpdir) / "cache",
                metadata_db=Path(tmpdir) / "metadata.db",
            )
            init_db(config.metadata_db)
            
            from data_pipeline.connectors.unido import fetch_unido
            result = fetch_unido(config, indicator="manufacturing_value_added")
            assert result.status == "success"
            assert result.records_fetched > 0


class TestClimateTRACEConnector:
    """Tests for Climate TRACE connector."""
    
    def test_normalizer_exists(self):
        """Should have a normalizer registered."""
        assert "climate_trace" in NORMALIZER_REGISTRY
    
    def test_normalizer_handles_data(self):
        """Should normalize Climate TRACE data."""
        df = pd.DataFrame({
            "sector_name": ["Power", "Roads"],
            "subsector_name": ["Coal", "Passenger"],
            "jan._2026_total": [1000.0, 500.0],
            "prev._month": [900.0, 450.0],
            "jan._2025_total": [950.0, 480.0],
            "2026_ytd": [1000.0, 500.0],
            "2025_ytd": [950.0, 480.0],
            "2024_ytd": [900.0, 460.0],
            "2023_ytd": [850.0, 440.0],
            "2022_ytd": [800.0, 420.0],
            "source_id": ["climate_trace"] * 2,
            "source_variable": ["climate_trace_emissions"] * 2,
        })
        result = normalize_source(df, "climate_trace")
        assert "year" in result.columns
        assert "value" in result.columns
        assert "country_code" in result.columns


class TestEIAConnector:
    """Tests for EIA connector."""
    
    def test_normalizer_exists(self):
        """Should have a normalizer registered."""
        assert "eia_" in NORMALIZER_REGISTRY
    
    def test_normalizer_handles_string_values(self):
        """Should convert string values to numeric."""
        df = pd.DataFrame({
            "period": ["2020", "2020", "2021", "2021"],
            "msn": ["TOTCB", "TOTCB", "TOTCB", "TOTCB"],
            "seriesDescription": ["Total Energy"] * 4,
            "value": ["90.0", "100.0", "95.0", "105.0"],
            "unit": ["Quadrillion Btu"] * 4,
            "source_id": ["eia_total_energy"] * 4,
            "source_variable": ["total_energy"] * 4,
        })
        result = normalize_source(df, "eia_total_energy")
        assert "year" in result.columns
        assert "value" in result.columns
        # Should aggregate to 2 years
        assert len(result) == 2


class TestCarbonAtlasConnector:
    """Tests for Carbon Atlas connector."""
    
    def test_normalizer_exists(self):
        """Should have a normalizer registered."""
        assert "global_carbon_atlas" in NORMALIZER_REGISTRY
    
    def test_normalizer_aggregates_world(self):
        """Should aggregate to World total."""
        df = pd.DataFrame({
            "country": ["USA", "China", "India"],
            "year": [2020, 2020, 2020],
            "total": [5000.0, 10000.0, 2500.0],
            "source_id": ["global_carbon_atlas"] * 3,
            "source_variable": ["land_use_co2_flux"] * 3,
        })
        result = normalize_source(df, "global_carbon_atlas")
        assert len(result) == 1
        assert result["country_code"].iloc[0] == "World"
        assert result["value"].iloc[0] == pytest.approx(17500.0)


class TestOECDConnector:
    """Tests for OECD connector."""
    
    def test_normalizer_exists(self):
        """Should have a normalizer registered."""
        assert "oecd_" in NORMALIZER_REGISTRY
    
    def test_normalizer_maps_codes(self):
        """Should map REF_AREA codes to ISO3."""
        df = pd.DataFrame({
            "REF_AREA": ["0", "12", "37"],
            "TIME_PERIOD": ["70", "71", "72"],
            "OBS_VALUE": [1000.0, 2000.0, 3000.0],
            "source_id": ["oecd_sna_table4"] * 3,
            "source_variable": ["sna_table4"] * 3,
        })
        result = normalize_source(df, "oecd_sna_table4")
        assert result["country_code"].tolist() == ["AUS", "DEU", "USA"]
        assert result["year"].tolist() == [2019, 2020, 2021]
