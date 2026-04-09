"""Tests for quality modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db
from data_pipeline.storage.parquet_store import write_raw


# ── Coverage Tests ─────────────────────────────────────────────────

class TestCoverage:
    """Tests for year coverage checks."""
    
    def test_compute_coverage_with_data(self):
        """Should compute coverage percentage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            df = pd.DataFrame({
                "year": list(range(2000, 2021)),
                "value": range(21),
            })
            write_raw(df, "test_source", raw_dir)
            
            from data_pipeline.quality.coverage import compute_coverage
            coverage = compute_coverage(raw_dir)
            assert len(coverage) == 1
    
    def test_compute_coverage_empty_dir(self):
        """Empty directory should return empty DataFrame."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            
            from data_pipeline.quality.coverage import compute_coverage
            coverage = compute_coverage(raw_dir)
            assert len(coverage) == 0


# ── Freshness Tests ────────────────────────────────────────────────

class TestFreshness:
    """Tests for data freshness checks."""
    
    def test_compute_freshness(self):
        """Should compute freshness for all sources."""
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
            
            from data_pipeline.quality.freshness import compute_freshness
            freshness = compute_freshness(config.metadata_db)
            # Should return DataFrame (may be empty)
            assert freshness is not None


# ── Consistency Tests ──────────────────────────────────────────────

class TestConsistency:
    """Tests for cross-source consistency checks."""
    
    def test_check_flow_consistency_exists(self):
        """Should have consistency check function."""
        from data_pipeline.quality.consistency import check_flow_consistency
        assert callable(check_flow_consistency)
    
    def test_check_stock_level_agreement_exists(self):
        """Should have stock level agreement function."""
        from data_pipeline.quality.consistency import check_stock_level_agreement
        assert callable(check_stock_level_agreement)


# ── Report Tests ───────────────────────────────────────────────────

class TestReport:
    """Tests for quality report generation."""
    
    def test_generate_report(self):
        """Should generate markdown quality report."""
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
            
            from data_pipeline.quality.report import generate_report
            report = generate_report(config, output_path=output_path)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "Quality Report" in content or "Coverage" in content
