"""Comprehensive integration tests for the full data pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.storage.parquet_store import write_raw
from data_pipeline.transforms.chain import run_all_transforms
from data_pipeline.transforms.normalize import NORMALIZER_REGISTRY
from data_pipeline.alignment.initial_conditions import extract_initial_conditions
from data_pipeline.calibration.nrmsd import nrmsd_direct, nrmsd_change_rate


# ── Normalizer Coverage Tests ─────────────────────────────────────────

class TestAllNormalizers:
    """Ensure all expected normalizers are registered."""
    
    def test_world_bank_normalizer(self):
        assert "world_bank_" in NORMALIZER_REGISTRY
    
    def test_fred_normalizer(self):
        assert "fred_" in NORMALIZER_REGISTRY
    
    def test_gcp_normalizer(self):
        assert "gcp_" in NORMALIZER_REGISTRY
    
    def test_ceds_normalizer(self):
        assert "ceds_" in NORMALIZER_REGISTRY
    
    def test_noaa_normalizer(self):
        assert "noaa_" in NORMALIZER_REGISTRY
    
    def test_nasa_giss_normalizer(self):
        assert "nasa_giss" in NORMALIZER_REGISTRY
    
    def test_faostat_normalizer(self):
        assert "faostat_" in NORMALIZER_REGISTRY
    
    def test_primap_normalizer(self):
        assert "primap_hist" in NORMALIZER_REGISTRY
    
    def test_climate_trace_normalizer(self):
        assert "climate_trace" in NORMALIZER_REGISTRY
    
    def test_carbon_atlas_normalizer(self):
        assert "global_carbon_atlas" in NORMALIZER_REGISTRY
    
    def test_owid_normalizer(self):
        assert "owid_" in NORMALIZER_REGISTRY
    
    def test_eia_normalizer(self):
        assert "eia_" in NORMALIZER_REGISTRY
    
    def test_undp_normalizer(self):
        assert "undp_hdr" in NORMALIZER_REGISTRY
    
    def test_oecd_normalizer(self):
        assert "oecd_" in NORMALIZER_REGISTRY
    
    def test_edgar_normalizer(self):
        assert "edgar_" in NORMALIZER_REGISTRY
    
    def test_gapminder_normalizer(self):
        assert "gapminder_" in NORMALIZER_REGISTRY
    
    def test_ihme_gbd_normalizer(self):
        assert "ihme_gbd_" in NORMALIZER_REGISTRY
    
    def test_hmd_normalizer(self):
        assert "hmd_" in NORMALIZER_REGISTRY
    
    def test_imf_weo_normalizer(self):
        assert "imf_" in NORMALIZER_REGISTRY
    
    def test_nebel_normalizer(self):
        assert "nebel_" in NORMALIZER_REGISTRY
    
    def test_usgs_normalizer(self):
        assert "usgs_" in NORMALIZER_REGISTRY
    
    def test_comtrade_normalizer(self):
        assert "comtrade_" in NORMALIZER_REGISTRY


# ── Transform Chain Tests ────────────────────────────────────────────

class TestTransformChainEdgeCases:
    """Edge cases for transform chain."""
    
    def test_empty_dataframe_returns_empty(self):
        """Empty input should produce empty output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            aligned_dir = Path(tmpdir) / "aligned"
            db_path = Path(tmpdir) / "metadata.db"
            raw_dir.mkdir()
            aligned_dir.mkdir()
            init_db(db_path)
            
            # Write empty raw file
            pd.DataFrame().to_parquet(raw_dir / "test_empty.parquet")
            
            results = run_all_transforms(raw_dir, aligned_dir, db_path)
            assert results == {}
    
    def test_invalid_source_id_returns_empty(self):
        """Unknown source ID should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            aligned_dir = Path(tmpdir) / "aligned"
            db_path = Path(tmpdir) / "metadata.db"
            raw_dir.mkdir()
            aligned_dir.mkdir()
            init_db(db_path)
            
            # Write data with no mapping
            df = pd.DataFrame({
                "year": [2020],
                "value": [100.0],
            })
            df.to_parquet(raw_dir / "unknown_source.parquet")
            
            results = run_all_transforms(raw_dir, aligned_dir, db_path)
            assert results == {}
    
    def test_multiple_sources_processed(self):
        """Multiple sources should all be transformed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            aligned_dir = Path(tmpdir) / "aligned"
            db_path = Path(tmpdir) / "metadata.db"
            raw_dir.mkdir()
            aligned_dir.mkdir()
            init_db(db_path)
            
            # Write GCP data
            gcp = pd.DataFrame({
                "country": ["World"],
                "country_code": ["World"],
                "year": [2020],
                "co2_mt": [34000.0],
                "source_id": ["gcp_fossil_co2"],
                "source_variable": ["fossil_co2_emissions"],
                "unit": ["Mt_CO2"],
            })
            gcp.to_parquet(raw_dir / "gcp_fossil_co2.parquet")
            
            # Write NOAA data
            noaa = pd.DataFrame({
                "year": [2020],
                "co2_ppm": [414.0],
                "source_id": ["noaa_co2_annual"],
                "source_variable": ["co2_annual"],
            })
            noaa.to_parquet(raw_dir / "noaa_co2_annual.parquet")
            
            results = run_all_transforms(raw_dir, aligned_dir, db_path)
            
            # Both should be transformed
            assert "gcp_fossil_co2" in results
            assert "noaa_co2_annual" in results


# ── Initial Conditions Tests ────────────────────────────────────────

class TestInitialConditionsEdgeCases:
    """Edge cases for initial conditions extraction."""
    
    def test_missing_entity_returns_default(self):
        """Entity without aligned data should use default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned_dir = Path(tmpdir)
            
            conditions = extract_initial_conditions(aligned_dir, target_year=1900)
            
            # All should use defaults
            for entity, info in conditions.items():
                assert info["source"] == "default"
    
    def test_target_year_future(self):
        """Future target year should use closest available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned_dir = Path(tmpdir)
            
            # Create aligned data for recent years only
            df = pd.DataFrame({
                "entity": ["emissions.co2_fossil"],
                "year": [2020],
                "value": [35000.0],
                "unit": ["Mt_CO2"],
                "source_id": ["gcp_fossil_co2"],
                "quality_flag": ["OK"],
            })
            df.to_parquet(aligned_dir / "emissions_co2_fossil.parquet")
            
            conditions = extract_initial_conditions(aligned_dir, target_year=1900)
            
            # Should use 2020 data (closest available)
            co2 = conditions.get("emissions.co2_fossil")
            assert co2 is not None
            assert co2["year"] == 2020
    
    def test_all_sector_initial_conditions_present(self):
        """Should return conditions for all expected sectors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned_dir = Path(tmpdir)
            
            conditions = extract_initial_conditions(aligned_dir, target_year=1900)
            
            # Should have entries for all expected sectors
            expected_entities = [
                "population.total",
                "emissions.co2_fossil",
                "atmospheric.co2",
                "temperature.anomaly",
                "food.supply.kcal_per_capita",
            ]
            for entity in expected_entities:
                assert entity in conditions, f"Missing {entity}"


# ── NRMSD Tests ─────────────────────────────────────────────────────

class TestNRMSDEdgeCases:
    """Edge cases for NRMSD computation."""
    
    def test_identical_series_zero_nrmsd(self):
        """Identical series should give NRMSD = 0."""
        data = [100.0, 200.0, 300.0, 400.0, 500.0]
        assert nrmsd_direct(data, data) == pytest.approx(0.0)
    
    def test_single_point_returns_zero(self):
        """Single point should give NRMSD = 0 if identical."""
        assert nrmsd_direct([1.0], [1.0]) == pytest.approx(0.0)
    
    def test_empty_series_returns_nan(self):
        """Empty series should return NaN."""
        assert pd.isna(nrmsd_direct([], []))
    
    def test_change_rate_with_constant_series(self):
        """Constant series should have zero change rate."""
        model = [100.0, 100.0, 100.0, 100.0]
        reference = [100.0, 100.0, 100.0, 100.0]
        # Change rates are all zero, so NRMSD of zeros
        # This should either be 0 or NaN depending on implementation
        result = nrmsd_change_rate(model, reference)
        assert result == pytest.approx(0.0, abs=1e-6) or pd.isna(result)


# ── Full Pipeline Tests ─────────────────────────────────────────────

class TestFullPipeline:
    """End-to-end pipeline tests."""
    
    def test_pipeline_produces_aligned_output(self):
        """Full pipeline should produce aligned Parquet files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / "raw",
                aligned_dir=tmpdir / "aligned",
                cache_dir=tmpdir / "cache",
                metadata_db=tmpdir / "metadata.db",
            )
            config.raw_dir.mkdir()
            config.aligned_dir.mkdir()
            init_db(config.metadata_db)
            
            # Write test data
            gcp = pd.DataFrame({
                "country": ["World"],
                "country_code": ["World"],
                "year": [2020],
                "co2_mt": [34000.0],
                "source_id": ["gcp_fossil_co2"],
                "source_variable": ["fossil_co2_emissions"],
                "unit": ["Mt_CO2"],
            })
            write_raw(gcp, "gcp_fossil_co2", config.raw_dir)
            
            # Run transforms
            results = run_all_transforms(
                config.raw_dir, config.aligned_dir, config.metadata_db
            )
            
            # Should produce aligned output
            assert len(results) > 0
            
            # Aligned files should exist
            aligned_files = list(config.aligned_dir.glob("*.parquet"))
            assert len(aligned_files) > 0
    
    def test_initial_conditions_from_pipeline_output(self):
        """Should extract initial conditions from pipeline output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            config = PipelineConfig(
                raw_dir=tmpdir / "raw",
                aligned_dir=tmpdir / "aligned",
                cache_dir=tmpdir / "cache",
                metadata_db=tmpdir / "metadata.db",
            )
            config.raw_dir.mkdir()
            config.aligned_dir.mkdir()
            init_db(config.metadata_db)
            
            # Write test data
            gcp = pd.DataFrame({
                "country": ["World"],
                "country_code": ["World"],
                "year": [2020],
                "co2_mt": [34000.0],
                "source_id": ["gcp_fossil_co2"],
                "source_variable": ["fossil_co2_emissions"],
                "unit": ["Mt_CO2"],
            })
            write_raw(gcp, "gcp_fossil_co2", config.raw_dir)
            
            # Run transforms
            run_all_transforms(
                config.raw_dir, config.aligned_dir, config.metadata_db
            )
            
            # Extract initial conditions
            conditions = extract_initial_conditions(config.aligned_dir)
            assert len(conditions) > 0
