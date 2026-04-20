"""Tests for Phase 2: DataBridge, World3ReferenceConnector, EmpiricalCalibrationRunner.

Covers:
  - DataBridge: target loading, NRMSD comparison, objective building, normalization
  - World3ReferenceConnector: trajectory access, interpolation, calibration targets
  - EmpiricalCalibrationRunner: reference validation, quick evaluation
  - Alignment map: world3_reference entries present
"""

from __future__ import annotations


import numpy as np
import pandas as pd
import pytest

from pyworldx.data.bridge import (
    BridgeResult,
    CalibrationTarget,
    DataBridge,
    ENTITY_TO_ENGINE_MAP,
    NRMSD_METHOD,
)
from data_pipeline.connectors.world3_reference import (
    World3ReferenceConnector,
)
from pyworldx.calibration.empirical import (
    EmpiricalCalibrationReport,
    EmpiricalCalibrationRunner,
)
from data_pipeline.alignment.map import ONTOLOGY_MAP


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_target(
    name: str = "POP",
    years: np.ndarray | None = None,
    values: np.ndarray | None = None,
    weight: float = 1.0,
    method: str = "direct",
) -> CalibrationTarget:
    if years is None:
        years = np.array([1900, 1950, 2000, 2050, 2100])
    if values is None:
        values = np.array([1.0, 2.0, 3.0, 2.5, 2.0])
    return CalibrationTarget(
        variable_name=name,
        years=years,
        values=values,
        unit="test_units",
        weight=weight,
        source="test",
        nrmsd_method=method,
    )


def _trivial_engine(params: dict[str, float]):
    """Engine factory that produces simple trajectories for testing."""
    time = np.arange(1900, 2101, dtype=float)
    scale = params.get("scale", 1.0)
    trajs = {
        "POP": np.linspace(1.0, 3.0, len(time)) * scale,
        "industrial_output": np.linspace(100, 1000, len(time)) * scale,
        "pollution_index": np.linspace(0.1, 10.0, len(time)) * scale,
    }
    return trajs, time


# ═══════════════════════════════════════════════════════════════════════
# DataBridge tests
# ═══════════════════════════════════════════════════════════════════════

class TestCalibrationTarget:
    def test_defaults(self):
        t = CalibrationTarget(
            variable_name="POP",
            years=np.array([2000]),
            values=np.array([6e9]),
            unit="persons",
        )
        assert t.weight == 1.0
        assert t.nrmsd_method == "direct"
        assert t.source == ""

    def test_all_fields(self):
        t = _make_target(weight=2.5, method="change_rate")
        assert t.weight == 2.5
        assert t.nrmsd_method == "change_rate"


class TestEntityMapping:
    def test_all_engine_targets_exist(self):
        """Every engine variable in ENTITY_TO_ENGINE_MAP has an NRMSD method."""
        for entry in ENTITY_TO_ENGINE_MAP.values():
            if isinstance(entry, dict):
                engine_var = entry.get("engine_var")
                if not engine_var or entry.get("excluded_from_objective"):
                    continue
            else:
                engine_var = entry

            assert engine_var in NRMSD_METHOD, (
                f"Engine variable {engine_var} missing from NRMSD_METHOD"
            )

    def test_expected_mappings(self):
        assert ENTITY_TO_ENGINE_MAP["population.total"]["engine_var"] == "POP"
        assert ENTITY_TO_ENGINE_MAP["gdp.current_usd"]["engine_var"] == "industrial_output"
        assert ENTITY_TO_ENGINE_MAP["emissions.co2_fossil"]["engine_var"] == "pollution_generation"
        assert ENTITY_TO_ENGINE_MAP["hdi.human_development_index"]["engine_var"] == "human_welfare_index"


class TestDataBridgeCompare:
    def test_perfect_match_zero_nrmsd(self):
        bridge = DataBridge(normalize=False)
        years = np.array([1900, 1950, 2000])
        values = np.array([1.0, 2.0, 3.0])
        target = _make_target(years=years, values=values)

        engine_traj = np.array([1.0, 2.0, 3.0])
        engine_time = np.array([1900, 1950, 2000], dtype=float)

        result = bridge.compare([target], {"POP": engine_traj}, engine_time)
        assert isinstance(result, BridgeResult)
        assert result.n_targets == 1
        assert result.composite_nrmsd == pytest.approx(0.0, abs=1e-10)
        assert result.per_variable_nrmsd["POP"] == pytest.approx(0.0, abs=1e-10)

    def test_nonzero_nrmsd(self):
        bridge = DataBridge(normalize=False)
        years = np.array([1900, 1950, 2000])
        obs = np.array([1.0, 2.0, 3.0])
        target = _make_target(years=years, values=obs)

        model = np.array([1.1, 2.2, 3.3])
        time = np.array([1900, 1950, 2000], dtype=float)

        result = bridge.compare([target], {"POP": model}, time)
        assert result.composite_nrmsd > 0

    def test_missing_variable_skipped(self):
        bridge = DataBridge(normalize=False)
        target = _make_target(name="NONEXISTENT")
        result = bridge.compare([target], {"POP": np.array([1.0])}, np.array([2000.0]))
        assert result.n_targets == 0
        assert np.isnan(result.composite_nrmsd)

    def test_weighted_composite(self):
        bridge = DataBridge(normalize=False)
        years = np.array([1900, 1950, 2000])
        t1 = _make_target(name="POP", years=years, values=np.array([1.0, 2.0, 3.0]), weight=2.0)
        t2 = _make_target(
            name="industrial_output", years=years,
            values=np.array([100.0, 200.0, 300.0]), weight=1.0,
            method="direct",
        )

        trajs = {
            "POP": np.array([1.0, 2.0, 3.0]),      # perfect match
            "industrial_output": np.array([110.0, 220.0, 330.0]),  # 10% off
        }
        time = np.array([1900, 1950, 2000], dtype=float)

        result = bridge.compare([t1, t2], trajs, time)
        assert result.n_targets == 2
        # POP NRMSD = 0, so composite = (2*0 + 1*nrmsd_io) / 3
        assert result.per_variable_nrmsd["POP"] == pytest.approx(0.0, abs=1e-10)
        assert result.per_variable_nrmsd["industrial_output"] > 0
        expected_composite = (
            2.0 * 0.0 + 1.0 * result.per_variable_nrmsd["industrial_output"]
        ) / 3.0
        assert result.composite_nrmsd == pytest.approx(expected_composite, abs=1e-10)

    def test_coverage_recorded(self):
        bridge = DataBridge(normalize=False)
        years = np.array([1960, 1980, 2000, 2020])
        target = _make_target(years=years, values=np.ones(4))
        trajs = {"POP": np.ones(201)}
        time = np.arange(1900, 2101, dtype=float)

        result = bridge.compare([target], trajs, time)
        assert result.coverage["POP"] == (1960, 2020)

    def test_change_rate_method(self):
        bridge = DataBridge(normalize=False)
        years = np.array([1970, 1980, 1990, 2000])
        obs = np.array([100.0, 120.0, 144.0, 172.8])  # 20% growth each decade
        target = _make_target(years=years, values=obs, method="change_rate")

        # Engine matches perfectly
        time = np.array([1970, 1980, 1990, 2000], dtype=float)
        result = bridge.compare([target], {"POP": obs.copy()}, time)
        assert result.per_variable_nrmsd["POP"] == pytest.approx(0.0, abs=1e-10)

    def test_normalization_to_reference_year(self):
        bridge = DataBridge(reference_year=1970, normalize=True)
        years = np.array([1950, 1970, 1990])
        obs = np.array([100.0, 200.0, 300.0])
        target = _make_target(years=years, values=obs)

        # Engine has same shape but different scale
        engine = np.array([50.0, 100.0, 150.0])
        time = np.array([1950, 1970, 1990], dtype=float)

        result = bridge.compare([target], {"POP": engine}, time)
        # After normalizing to 1970: obs=[0.5, 1.0, 1.5], engine=[0.5, 1.0, 1.5]
        assert result.per_variable_nrmsd["POP"] == pytest.approx(0.0, abs=1e-10)


class TestDataBridgeBuildObjective:
    def test_returns_callable(self):
        bridge = DataBridge(normalize=False)
        target = _make_target()
        obj = bridge.build_objective([target], _trivial_engine)
        assert callable(obj)

    def test_objective_returns_float(self):
        bridge = DataBridge(normalize=False)
        target = _make_target()
        obj = bridge.build_objective([target], _trivial_engine)
        val = obj({"scale": 1.0})
        assert isinstance(val, float)
        assert np.isfinite(val)

    def test_objective_inf_on_exception(self):
        bridge = DataBridge(normalize=False)
        target = _make_target()

        def failing_engine(params):
            raise RuntimeError("boom")

        obj = bridge.build_objective([target], failing_engine)
        assert obj({}) == float("inf")


class TestDataBridgeLoadTargetsFromResults:
    def test_loads_from_result_dict(self):
        bridge = DataBridge()

        class FakeResult:
            series = pd.Series(
                [1e9, 2e9, 3e9, 4e9],
                index=[1970, 1980, 1990, 2000],
            )
            unit = "persons"

        results = {"population.total": FakeResult()}
        targets = bridge.load_targets_from_results(results)
        assert len(targets) == 1
        assert targets[0].variable_name == "POP"
        assert targets[0].unit == "persons"
        assert len(targets[0].years) == 4

    def test_skips_unmapped_entities(self):
        bridge = DataBridge()

        class FakeResult:
            series = pd.Series([1, 2, 3], index=[2000, 2001, 2002])
            unit = "widgets"

        results = {"nonexistent.entity": FakeResult()}
        targets = bridge.load_targets_from_results(results)
        assert len(targets) == 0


try:
    import pyarrow  # noqa: F401
    _HAS_PYARROW = True
except ImportError:
    _HAS_PYARROW = False

try:
    import duckdb  # noqa: F401
    _HAS_DUCKDB = True
except ImportError:
    _HAS_DUCKDB = False


@pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow required for parquet tests")
class TestDataBridgeLoadTargets:
    def test_load_from_aligned_parquet(self, tmp_path):
        """Integration test: write a parquet file and load targets from it."""
        aligned = tmp_path / "aligned"
        aligned.mkdir()

        df = pd.DataFrame({
            "year": [1970, 1980, 1990, 2000, 2010],
            "value": [3.7e9, 4.4e9, 5.3e9, 6.1e9, 6.9e9],
            "country_code": ["WLD"] * 5,
            "unit": ["persons"] * 5,
        })
        df.to_parquet(aligned / "population_total.parquet")

        bridge = DataBridge(entity_map={"population.total": {"engine_var": "POP", "unit": "persons", "nrmsd_method": "direct"}})
        targets = bridge.load_targets(aligned, sector="population")
        pop_targets = [t for t in targets if t.variable_name == "POP"]
        assert len(pop_targets) == 1
        assert len(pop_targets[0].years) == 5
        assert pop_targets[0].source == "pipeline:population.total"

    def test_skips_short_series(self, tmp_path):
        aligned = tmp_path / "aligned"
        aligned.mkdir()

        df = pd.DataFrame({
            "year": [2000, 2010],
            "value": [1.0, 2.0],
            "country_code": ["WLD", "WLD"],
        })
        df.to_parquet(aligned / "population_total.parquet")

        bridge = DataBridge(entity_map={"population.total": {"engine_var": "POP", "unit": "persons", "nrmsd_method": "direct"}})
        targets = bridge.load_targets(aligned, sector="population")
        # Only 2 data points — should be skipped (minimum is 3)
        pop_targets = [t for t in targets if t.variable_name == "POP"]
        assert len(pop_targets) == 0


# ═══════════════════════════════════════════════════════════════════════
# World3ReferenceConnector tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorld3ReferenceConnector:
    def setup_method(self):
        self.connector = World3ReferenceConnector()

    def test_available_variables(self):
        variables = self.connector.available_variables()
        assert len(variables) == 8
        expected = {
            "population", "industrial_output", "food_per_capita",
            "nr_fraction_remaining", "pollution_index", "life_expectancy",
            "human_welfare_index", "ecological_footprint",
        }
        assert set(variables) == expected

    def test_fetch_returns_series(self):
        series = self.connector.fetch("population")
        assert isinstance(series, pd.Series)
        assert series.name == "population"
        assert len(series) == 21  # decadal 1900-2100
        assert series.index[0] == 1900
        assert series.index[-1] == 2100

    def test_fetch_nonexistent_returns_none(self):
        assert self.connector.fetch("nonexistent") is None

    def test_fetch_interpolated_annual(self):
        series = self.connector.fetch_interpolated("population")
        assert isinstance(series, pd.Series)
        assert len(series) == 201  # 1900-2100 inclusive
        assert series.index[0] == 1900
        assert series.index[-1] == 2100
        # Interpolated values should be between neighbors
        assert series[1905] > series[1900]

    def test_fetch_interpolated_custom_range(self):
        series = self.connector.fetch_interpolated("population", 1950, 2000)
        assert len(series) == 51  # 1950-2000 inclusive

    def test_fetch_all(self):
        all_data = self.connector.fetch_all()
        assert len(all_data) == 8
        for name, series in all_data.items():
            assert isinstance(series, pd.Series)

    def test_fetch_all_interpolated(self):
        all_data = self.connector.fetch_all_interpolated()
        assert len(all_data) == 8
        for name, series in all_data.items():
            assert len(series) == 201

    def test_get_unit(self):
        assert self.connector.get_unit("population") == "persons"
        assert self.connector.get_unit("life_expectancy") == "years"
        assert self.connector.get_unit("pollution_index") == "dimensionless"
        assert self.connector.get_unit("nonexistent") is None

    def test_population_1970(self):
        """W3-03 population at 1970 should be ~3.7e9."""
        series = self.connector.fetch("population")
        pop_1970 = series[1970]
        assert 3.5e9 < pop_1970 < 4.0e9

    def test_nrfr_monotonic_decrease(self):
        """Nonrenewable resource fraction should monotonically decrease."""
        series = self.connector.fetch("nr_fraction_remaining")
        for i in range(len(series) - 1):
            assert series.iloc[i] >= series.iloc[i + 1]

    def test_population_peaks_and_declines(self):
        """Standard Run population peaks around 2030 then declines."""
        series = self.connector.fetch("population")
        peak_year = series.idxmax()
        assert 2020 <= peak_year <= 2040


class TestWorld3ReferenceCalibrationTargets:
    def test_to_calibration_targets(self):
        connector = World3ReferenceConnector()
        targets = connector.to_calibration_targets(weight=0.5)
        assert len(targets) == 8
        for t in targets:
            assert isinstance(t, dict)
            assert "variable_name" in t
            assert "years" in t
            assert "values" in t
            assert "unit" in t
            assert t["weight"] == 0.5
            assert t["source"].startswith("world3_reference:")

    def test_engine_variable_names(self):
        connector = World3ReferenceConnector()
        targets = connector.to_calibration_targets()
        var_names = {t["variable_name"] for t in targets}
        assert "POP" in var_names
        assert "industrial_output" in var_names
        assert "life_expectancy" in var_names

    def test_nrmsd_methods_assigned(self):
        connector = World3ReferenceConnector()
        targets = connector.to_calibration_targets()
        for t in targets:
            assert t["nrmsd_method"] in ("direct", "change_rate")


# ═══════════════════════════════════════════════════════════════════════
# EmpiricalCalibrationRunner tests
# ═══════════════════════════════════════════════════════════════════════

class TestEmpiricalCalibrationRunner:
    def test_init(self, tmp_path):
        runner = EmpiricalCalibrationRunner(aligned_dir=tmp_path)
        assert runner.aligned_dir == tmp_path
        assert runner.bridge is not None

    def test_load_reference_targets_no_connector(self, tmp_path):
        """Without a reference connector, returns empty list."""
        runner = EmpiricalCalibrationRunner(aligned_dir=tmp_path)
        targets = runner.load_reference_targets()
        assert targets == []

    def test_load_reference_targets_with_connector(self, tmp_path):
        connector = World3ReferenceConnector()
        runner = EmpiricalCalibrationRunner(
            aligned_dir=tmp_path,
            reference_connector=connector,
        )
        targets = runner.load_reference_targets(weight=0.5)
        assert len(targets) == 8
        for t in targets:
            assert isinstance(t, CalibrationTarget)
            assert t.weight == 0.5

    def test_validate_against_reference_no_connector(self, tmp_path):
        runner = EmpiricalCalibrationRunner(aligned_dir=tmp_path)
        result = runner.validate_against_reference(_trivial_engine, {})
        assert result is None

    def test_validate_against_reference_with_connector(self, tmp_path):
        connector = World3ReferenceConnector()
        runner = EmpiricalCalibrationRunner(
            aligned_dir=tmp_path,
            reference_connector=connector,
            normalize=False,
        )
        result = runner.validate_against_reference(_trivial_engine, {"scale": 1.0})
        # Only POP is in the trivial engine, so only 1 target matches
        assert result is not None
        assert isinstance(result, BridgeResult)
        assert result.n_targets >= 1

    @pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow required")
    def test_quick_evaluate(self, tmp_path):
        """Quick evaluate with parquet targets."""
        aligned = tmp_path / "aligned"
        aligned.mkdir()

        df = pd.DataFrame({
            "year": list(range(1900, 2101, 10)),
            "value": np.linspace(1.0, 3.0, 21),
            "country_code": ["WLD"] * 21,
            "unit": ["persons"] * 21,
        })
        df.to_parquet(aligned / "population_total.parquet")

        runner = EmpiricalCalibrationRunner(
            aligned_dir=aligned,
            normalize=False,
            entity_map={"population.total": {"engine_var": "POP", "unit": "persons", "nrmsd_method": "direct"}},
        )
        result = runner.quick_evaluate(_trivial_engine, {"scale": 1.0})
        assert isinstance(result, BridgeResult)
        assert result.n_targets >= 1

    @pytest.mark.skipif(not _HAS_DUCKDB, reason="duckdb required for pipeline store")
    def test_run_no_targets_returns_empty_report(self, tmp_path, monkeypatch):
        """With no aligned data, run() returns an empty report."""
        runner = EmpiricalCalibrationRunner(aligned_dir=tmp_path)
        monkeypatch.setattr(runner.bridge, "load_targets", lambda *args, **kwargs: [])
        from pyworldx.calibration.parameters import ParameterRegistry
        registry = ParameterRegistry()
        report = runner.run(registry, _trivial_engine)
        assert isinstance(report, EmpiricalCalibrationReport)
        assert report.empirical_targets_loaded == 0
        assert not report.converged

    def test_report_dataclass_defaults(self):
        report = EmpiricalCalibrationReport()
        assert report.reference_result is None
        assert report.empirical_targets_loaded == 0
        assert report.empirical_result is None
        assert report.pipeline_report is None
        assert report.calibrated_parameters == {}
        assert report.converged is False
        assert report.total_evaluations == 0


# ═══════════════════════════════════════════════════════════════════════
# Alignment map tests
# ═══════════════════════════════════════════════════════════════════════

class TestAlignmentMapWorld3Reference:
    def test_all_reference_variables_mapped(self):
        """Every variable in World3ReferenceConnector has an ONTOLOGY_MAP entry."""
        expected_source_ids = [
            "world3_reference_population",
            "world3_reference_industrial_output",
            "world3_reference_food_per_capita",
            "world3_reference_nr_fraction_remaining",
            "world3_reference_pollution_index",
            "world3_reference_life_expectancy",
            "world3_reference_human_welfare_index",
            "world3_reference_ecological_footprint",
        ]
        for source_id in expected_source_ids:
            assert source_id in ONTOLOGY_MAP, f"Missing ONTOLOGY_MAP entry: {source_id}"

    def test_reference_entries_have_reference_quality(self):
        """All world3_reference entries should have REFERENCE quality flag."""
        for key, mappings in ONTOLOGY_MAP.items():
            if key.startswith("world3_reference_"):
                for m in mappings:
                    assert m.quality_flag == "REFERENCE", (
                        f"{key} should have REFERENCE quality flag"
                    )

    def test_reference_entries_no_country_filter(self):
        """Reference trajectories are global — no country filtering."""
        for key, mappings in ONTOLOGY_MAP.items():
            if key.startswith("world3_reference_"):
                for m in mappings:
                    assert m.country_filter is None, (
                        f"{key} should have None country_filter"
                    )


# ═══════════════════════════════════════════════════════════════════════
# NRMSD computation tests
# ═══════════════════════════════════════════════════════════════════════

class TestNRMSDComputation:
    def test_direct_nrmsd_formula(self):
        """Verify direct NRMSD = RMSD / mean(|reference|)."""
        bridge = DataBridge(normalize=False)
        model = np.array([1.0, 2.0, 3.0])
        ref = np.array([1.1, 2.1, 3.1])
        nrmsd = bridge._compute_nrmsd(model, ref, "direct")

        rmsd = np.sqrt(np.mean((model - ref) ** 2))
        expected = rmsd / np.mean(np.abs(ref))
        assert nrmsd == pytest.approx(expected, abs=1e-10)

    def test_change_rate_nrmsd(self):
        """Change rate NRMSD compares percent changes, not levels."""
        bridge = DataBridge(normalize=False)
        # Both grow at same rate -> NRMSD should be 0
        model = np.array([100.0, 110.0, 121.0])  # 10% growth
        ref = np.array([200.0, 220.0, 242.0])    # same 10% growth
        nrmsd = bridge._compute_nrmsd(model, ref, "change_rate")
        assert nrmsd == pytest.approx(0.0, abs=1e-10)

    def test_empty_arrays_return_nan(self):
        bridge = DataBridge(normalize=False)
        assert np.isnan(bridge._compute_nrmsd(np.array([]), np.array([]), "direct"))
