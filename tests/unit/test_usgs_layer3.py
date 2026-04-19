"""Tests for Phase 4: USGS Layer 3 cross-validation integration.

Covers:
  - USGS compute_resource_extraction_index / compute_reserve_depletion_ratio
  - EmpiricalCalibrationRunner.load_usgs_targets / cross_validate_usgs
  - Layer 3 wiring into run() pipeline
  - DataBridge ENTITY_TO_ENGINE_MAP and NRMSD_METHOD for USGS proxies
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from pyworldx.data.bridge import (
    ENTITY_TO_ENGINE_MAP,
    NRMSD_METHOD,
)
from pyworldx.calibration.empirical import (
    EmpiricalCalibrationReport,
    EmpiricalCalibrationRunner,
)
from data_pipeline.alignment.map import ONTOLOGY_MAP


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_usgs_csv(tmp_path: Path) -> Path:
    """Create a minimal world_production.csv for testing."""
    usgs_dir = tmp_path / "usgs"
    usgs_dir.mkdir(exist_ok=True)

    rows = []
    for year in [2020, 2021, 2022, 2023, 2024]:
        # Two commodities with world totals
        rows.append({
            "commodity": "copper",
            "mcs_year": year,
            "source": "A",
            "table_type": "mine",
            "country_raw": "World",
            "country_clean": "World",
            "is_world_total": True,
            "mine_production_current_year": 20000.0 + (year - 2020) * 500,
            "reserves": 880000.0,
        })
        rows.append({
            "commodity": "zinc",
            "mcs_year": year,
            "source": "A",
            "table_type": "mine",
            "country_raw": "World",
            "country_clean": "World",
            "is_world_total": True,
            "mine_production_current_year": 13000.0 + (year - 2020) * 200,
            "reserves": 250000.0,
        })

    df = pd.DataFrame(rows)
    csv_path = usgs_dir / "world_production.csv"
    df.to_csv(csv_path, index=False)
    return usgs_dir


def _trivial_engine(params: dict[str, float]):
    """Engine that produces simple trajectories."""
    time = np.arange(1900, 2101, dtype=float)
    scale = params.get("scale", 1.0)
    return {
        "POP": np.linspace(1.0, 3.0, len(time)) * scale,
        "NR": np.linspace(1.0, 0.1, len(time)) * scale,
        "resource_extraction_index": np.linspace(100, 300, len(time)) * scale,
        "reserve_depletion_ratio": np.linspace(0.01, 0.05, len(time)) * scale,
    }, time


# ═══════════════════════════════════════════════════════════════════════
# USGS compute functions
# ═══════════════════════════════════════════════════════════════════════

class TestComputeResourceExtractionIndex:
    def test_with_valid_data(self, tmp_path):
        from data_pipeline.connectors.usgs import compute_resource_extraction_index

        usgs_dir = _make_usgs_csv(tmp_path)
        index = compute_resource_extraction_index(str(usgs_dir))
        assert isinstance(index, pd.Series)
        assert len(index) >= 3
        assert index.name == "resource_extraction_index"
        # First year should be base = 100
        assert index.iloc[0] == pytest.approx(100.0)
        # Should increase over time (production growing)
        assert index.iloc[-1] > index.iloc[0]

    def test_empty_on_missing_file(self, tmp_path):
        from data_pipeline.connectors.usgs import compute_resource_extraction_index

        index = compute_resource_extraction_index(str(tmp_path))
        assert index.empty

    def test_monotonic_increase(self, tmp_path):
        from data_pipeline.connectors.usgs import compute_resource_extraction_index

        usgs_dir = _make_usgs_csv(tmp_path)
        index = compute_resource_extraction_index(str(usgs_dir))
        for i in range(len(index) - 1):
            assert index.iloc[i + 1] >= index.iloc[i]


class TestComputeReserveDepletionRatio:
    def test_with_valid_data(self, tmp_path):
        from data_pipeline.connectors.usgs import compute_reserve_depletion_ratio

        usgs_dir = _make_usgs_csv(tmp_path)
        ratio = compute_reserve_depletion_ratio(str(usgs_dir))
        assert isinstance(ratio, pd.Series)
        assert len(ratio) >= 3
        assert ratio.name == "reserve_depletion_ratio"
        # Ratio should be small (production << reserves)
        assert all(0 < r < 1 for r in ratio)

    def test_empty_on_missing_file(self, tmp_path):
        from data_pipeline.connectors.usgs import compute_reserve_depletion_ratio

        ratio = compute_reserve_depletion_ratio(str(tmp_path))
        assert ratio.empty


# ═══════════════════════════════════════════════════════════════════════
# Bridge USGS mappings
# ═══════════════════════════════════════════════════════════════════════

class TestBridgeUSGSMappings:
    def test_extraction_index_in_entity_map(self):
        assert "resources.extraction_index" in ENTITY_TO_ENGINE_MAP
        entry = ENTITY_TO_ENGINE_MAP["resources.extraction_index"]
        engine_var = entry["engine_var"] if isinstance(entry, dict) else entry
        assert engine_var == "resource_extraction_index"

    def test_depletion_ratio_in_entity_map(self):
        assert "resources.depletion_ratio" in ENTITY_TO_ENGINE_MAP
        entry = ENTITY_TO_ENGINE_MAP["resources.depletion_ratio"]
        engine_var = entry["engine_var"] if isinstance(entry, dict) else entry
        assert engine_var == "reserve_depletion_ratio"

    def test_nrmsd_methods_assigned(self):
        assert NRMSD_METHOD["resource_extraction_index"] == "change_rate"
        assert NRMSD_METHOD["reserve_depletion_ratio"] == "change_rate"


class TestAlignmentMapUSGSProxies:
    def test_extraction_index_mapped(self):
        assert "usgs_resource_extraction_index" in ONTOLOGY_MAP
        mapping = ONTOLOGY_MAP["usgs_resource_extraction_index"][0]
        assert mapping.entity == "resources.extraction_index"
        assert mapping.quality_flag == "PROXY"

    def test_depletion_ratio_mapped(self):
        assert "usgs_reserve_depletion_ratio" in ONTOLOGY_MAP
        mapping = ONTOLOGY_MAP["usgs_reserve_depletion_ratio"][0]
        assert mapping.entity == "resources.depletion_ratio"
        assert mapping.quality_flag == "PROXY"


# ═══════════════════════════════════════════════════════════════════════
# EmpiricalCalibrationRunner Layer 3
# ═══════════════════════════════════════════════════════════════════════

class TestRunnerLoadUSGSTargets:
    def test_load_with_valid_data(self, tmp_path):
        usgs_dir = _make_usgs_csv(tmp_path)
        runner = EmpiricalCalibrationRunner(
            aligned_dir=tmp_path,
            usgs_data_dir=usgs_dir,
        )
        targets = runner.load_usgs_targets(weight=0.5)
        assert len(targets) == 2
        names = {t.variable_name for t in targets}
        assert "resource_extraction_index" in names
        assert "reserve_depletion_ratio" in names
        for t in targets:
            assert t.weight == 0.5
            assert t.source.startswith("usgs:")

    def test_load_with_no_data(self, tmp_path):
        runner = EmpiricalCalibrationRunner(
            aligned_dir=tmp_path,
            usgs_data_dir=tmp_path,  # no CSV here
        )
        targets = runner.load_usgs_targets()
        assert targets == []

    def test_load_default_dir_graceful(self, tmp_path):
        """Without usgs_data_dir set, uses default which may not exist."""
        runner = EmpiricalCalibrationRunner(aligned_dir=tmp_path)
        # Should not raise even if default path doesn't have data
        targets = runner.load_usgs_targets()
        # May or may not find data depending on real project state
        assert isinstance(targets, list)


class TestRunnerCrossValidateUSGS:
    def test_with_valid_data(self, tmp_path):
        usgs_dir = _make_usgs_csv(tmp_path)
        runner = EmpiricalCalibrationRunner(
            aligned_dir=tmp_path,
            usgs_data_dir=usgs_dir,
            normalize=False,
        )
        result = runner.cross_validate_usgs(
            _trivial_engine, {"scale": 1.0},
        )
        assert result is not None
        assert result.n_targets >= 1

    def test_none_without_data(self, tmp_path):
        runner = EmpiricalCalibrationRunner(
            aligned_dir=tmp_path,
            usgs_data_dir=tmp_path,
        )
        result = runner.cross_validate_usgs(
            _trivial_engine, {"scale": 1.0},
        )
        assert result is None


class TestReportLayerFields:
    def test_report_has_usgs_fields(self):
        report = EmpiricalCalibrationReport()
        assert report.usgs_targets_loaded == 0
        assert report.usgs_result is None

    def test_report_with_usgs_populated(self):
        from pyworldx.data.bridge import BridgeResult
        report = EmpiricalCalibrationReport(
            usgs_targets_loaded=2,
            usgs_result=BridgeResult(
                per_variable_nrmsd={"resource_extraction_index": 0.1},
                composite_nrmsd=0.1,
                n_targets=1,
                coverage={"resource_extraction_index": (2019, 2023)},
            ),
        )
        assert report.usgs_targets_loaded == 2
        assert report.usgs_result.composite_nrmsd == 0.1
