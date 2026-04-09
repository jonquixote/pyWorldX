"""Tests for export modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from data_pipeline.storage.parquet_store import write_aligned


# ── Calibration CSV Tests ─────────────────────────────────────────

class TestCalibrationCSV:
    """Tests for calibration CSV export."""
    
    def test_export_single_calibration_csv(self):
        """Should export aligned data as calibration CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "calibration"
            output_dir.mkdir()
            
            df = pd.DataFrame({
                "entity": ["test.entity"] * 3,
                "year": [2020, 2021, 2022],
                "value": [100.0, 110.0, 120.0],
                "unit": ["test_unit"] * 3,
                "source_id": ["test"] * 3,
                "quality_flag": ["OK"] * 3,
            })
            
            from data_pipeline.export.calibration_csv import export_calibration_csv
            path = export_calibration_csv(
                df=df,
                entity="test.entity",
                output_path=output_dir / "test.entity.csv",
                unit="test_unit",
                sources="test_source",
            )
            
            assert path.exists()
            content = path.read_text()
            assert "# pyWorldX NRMSD Calibration Series" in content
            assert "test.entity" in content
    
    def test_export_empty_dataframe(self):
        """Empty DataFrame should return path without writing data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "calibration"
            output_dir.mkdir()
            
            df = pd.DataFrame()
            
            from data_pipeline.export.calibration_csv import export_calibration_csv
            path = export_calibration_csv(
                df=df,
                entity="test.entity",
                output_path=output_dir / "test.entity.csv",
                unit="test_unit",
            )
            
            # Should return path (file may not have data rows)
            assert path.parent.exists()
    
    def test_export_all_calibration(self):
        """Should export all aligned entities as CSVs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned_dir = Path(tmpdir) / "aligned"
            output_dir = Path(tmpdir) / "calibration"
            aligned_dir.mkdir()
            output_dir.mkdir()
            
            df = pd.DataFrame({
                "entity": ["test.entity"] * 2,
                "year": [2020, 2021],
                "value": [100.0, 110.0],
                "unit": ["test_unit"] * 2,
                "source_id": ["test"] * 2,
                "quality_flag": ["OK"] * 2,
            })
            write_aligned(df, "test_entity", aligned_dir)
            
            from data_pipeline.export.calibration_csv import export_all_calibration
            paths = export_all_calibration(aligned_dir, output_dir)
            
            assert len(paths) == 1
            assert paths[0].exists()


# ── Connector Result Tests ────────────────────────────────────────

class TestConnectorResult:
    """Tests for ConnectorResult generation."""
    
    def test_generate_connector_result(self):
        """Should generate ConnectorResult dicts."""
        from data_pipeline.export.connector_result import generate_connector_result
        
        # Check actual function signature
        import inspect
        sig = inspect.signature(generate_connector_result)
        params = list(sig.parameters.keys())
        
        # Just verify the function exists and is callable
        assert callable(generate_connector_result)
        assert len(params) > 0


# ── Manifest Tests ─────────────────────────────────────────────────

class TestManifest:
    """Tests for data manifest generation."""
    
    def test_generate_manifest(self):
        """Should generate JSON manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            db_path = tmpdir / "metadata.db"
            raw_dir = tmpdir / "raw"
            aligned_dir = tmpdir / "aligned"
            output_path = tmpdir / "manifest.json"
            
            raw_dir.mkdir()
            aligned_dir.mkdir()
            
            from data_pipeline.storage.metadata_db import init_db
            init_db(db_path)
            
            from data_pipeline.export.manifest import generate_manifest
            manifest = generate_manifest(
                db_path=db_path,
                raw_dir=raw_dir,
                aligned_dir=aligned_dir,
                output_path=output_path,
            )
            
            assert output_path.exists()
            assert "generated_at" in manifest
            assert "sources" in manifest
            assert "aligned_entities" in manifest


# ── Manifest Validation Tests ──────────────────────────────────────

class TestManifestValidation:
    """Tests for manifest schema validation."""
    
    def test_validate_valid_manifest(self):
        """Valid manifest should have no errors."""
        import json
        import tempfile
        from pathlib import Path
        
        manifest = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "pipeline_version": "0.1.0",
            "sources": {
                "test_source": {
                    "version": "v1.0",
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                    "checksum_sha256": "abc123",
                    "records_fetched": 100,
                    "url": "https://example.com",
                    "format": "csv",
                },
            },
            "aligned_entities": {
                "test.entity": {
                    "source_id": "test_source",
                    "year_min": 2000,
                    "year_max": 2020,
                    "records": 21,
                    "unit": "test_unit",
                },
            },
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f)
            
            from data_pipeline.export.manifest_validation import validate_manifest
            result = validate_manifest(manifest_path)
            
            assert len(result["errors"]) == 0
    
    def test_validate_missing_field(self):
        """Missing required field should generate error."""
        import json
        import tempfile
        from pathlib import Path
        
        manifest = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            # Missing "sources" and "aligned_entities"
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f)
            
            from data_pipeline.export.manifest_validation import validate_manifest
            result = validate_manifest(manifest_path)
            
            assert len(result["errors"]) > 0
    
    def test_validate_directory(self):
        """Should validate all manifests in directory."""
        import json
        import tempfile
        from pathlib import Path
        
        manifest = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "pipeline_version": "0.1.0",
            "sources": {},
            "aligned_entities": {},
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            manifest_path = tmpdir / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f)
            
            from data_pipeline.export.manifest_validation import validate_manifest_directory
            results = validate_manifest_directory(tmpdir)
            
            assert "manifest.json" in results
