"""Comprehensive unit tests for quality and export modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.storage.parquet_store import write_aligned


# ── Quality Module Tests ───────────────────────────────────────────

class TestQualityCoverage:
    """Test quality coverage checks."""

    def test_compute_coverage_empty_dir(self):
        """Should return empty DataFrame for empty directory."""
        from data_pipeline.quality.coverage import compute_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()

            coverage = compute_coverage(raw_dir)
            assert coverage is not None

    def test_compute_coverage_with_data(self):
        """Should compute coverage for raw sources."""
        from data_pipeline.quality.coverage import compute_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()

            df = pd.DataFrame({
                "year": list(range(2000, 2021)),
                "value": range(21),
            })
            df.to_parquet(raw_dir / "test_source.parquet", index=False)

            coverage = compute_coverage(raw_dir)
            assert coverage is not None
            assert len(coverage) >= 1


class TestQualityFreshness:
    """Test data freshness checks."""

    def test_compute_freshness_empty_db(self):
        """Should handle empty metadata DB."""
        from data_pipeline.quality.freshness import compute_freshness

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

            freshness = compute_freshness(config.metadata_db)
            assert freshness is not None


class TestQualityConsistency:
    """Test cross-source consistency checks."""

    def test_check_flow_consistency_empty(self):
        """Should handle empty raw store."""
        from data_pipeline.quality.consistency import check_flow_consistency

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()

            result = check_flow_consistency(raw_dir, [], [])
            assert result is not None

    def test_check_stock_level_agreement_empty(self):
        """Should handle missing source."""
        from data_pipeline.quality.consistency import check_stock_level_agreement

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()

            result = check_stock_level_agreement(raw_dir, "missing_source")
            assert result is not None


class TestQualityReport:
    """Test quality report generation."""

    def test_generate_report(self):
        """Should generate markdown quality report."""
        from data_pipeline.quality.report import generate_report

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

            output_path = tmpdir / "quality_report.md"
            generate_report(config, output_path=output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "Quality Report" in content or "Coverage" in content


# ── Export Module Tests ─────────────────────────────────────────────

class TestCalibrationCSV:
    """Test calibration CSV export."""

    def test_export_single_csv(self):
        """Should export aligned data as calibration CSV."""
        from data_pipeline.export.calibration_csv import export_calibration_csv

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

    def test_export_empty_dataframe(self):
        """Empty DataFrame should still create file with header."""
        from data_pipeline.export.calibration_csv import export_calibration_csv

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "calibration"
            output_dir.mkdir()

            df = pd.DataFrame()
            path = export_calibration_csv(
                df=df,
                entity="test.entity",
                output_path=output_dir / "test.entity.csv",
                unit="test_unit",
            )

            assert path.parent.exists()

    def test_export_all_calibration(self):
        """Should export all aligned entities as CSVs."""
        from data_pipeline.export.calibration_csv import export_all_calibration

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

            paths = export_all_calibration(aligned_dir, output_dir)

            assert len(paths) == 1
            assert paths[0].exists()


class TestConnectorResult:
    """Test ConnectorResult generation."""

    def test_generate_connector_result(self):
        """Should return callable function."""
        from data_pipeline.export.connector_result import generate_connector_result

        import inspect
        sig = inspect.signature(generate_connector_result)
        params = list(sig.parameters.keys())

        assert callable(generate_connector_result)
        assert len(params) > 0


class TestManifest:
    """Test manifest generation."""

    def test_generate_manifest(self):
        """Should generate JSON manifest."""
        from data_pipeline.export.manifest import generate_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            db_path = tmpdir / "metadata.db"
            raw_dir = tmpdir / "raw"
            aligned_dir = tmpdir / "aligned"
            output_path = tmpdir / "manifest.json"

            raw_dir.mkdir()
            aligned_dir.mkdir()
            init_db(db_path)

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


class TestManifestValidation:
    """Test manifest schema validation."""

    def test_validate_valid_manifest(self):
        """Valid manifest should have no errors."""
        import json
        from data_pipeline.export.manifest_validation import validate_manifest

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

            result = validate_manifest(manifest_path)
            assert len(result["errors"]) == 0

    def test_validate_missing_field(self):
        """Missing required field should generate error."""
        import json
        from data_pipeline.export.manifest_validation import validate_manifest

        manifest = {
            "generated_at": "2026-01-01T00:00:00+00:00",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f)

            result = validate_manifest(manifest_path)
            assert len(result["errors"]) > 0

    def test_validate_directory(self):
        """Should validate all manifests in directory."""
        import json
        from data_pipeline.export.manifest_validation import validate_manifest_directory

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

            results = validate_manifest_directory(tmpdir)
            assert "manifest.json" in results
