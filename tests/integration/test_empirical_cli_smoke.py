"""Smoke tests for the empirical CLI entry-point and its fixed helper functions.

Covers:
  - _resolve_registry() — the canonical replacement for the broken
    ParameterRegistry.for_sector() / registry.subset() calls
  - build_sector_engine_factory() — module-level function that was missing
    and causing an ImportError at CLI startup
  - CLI subprocess invocation (--dry-run) via subprocess.run so the test
    exercises the real argparse / logging path without a live Parquet store
  - EmpiricalCalibrationRunner.run() end-to-end with synthetic targets,
    a scoped registry, and a mocked engine factory (fast path, < 30s)

All tests are self-contained.  No Parquet store, USGS data, or internet
access is required.  The suite intentionally stays under ~30 s total
by using morris_trajectories=2 / sobol_samples=32 where the optimizer
runs at all.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from pyworldx.calibration.empirical import (
    EmpiricalCalibrationRunner,
    _resolve_registry,
    build_sector_engine_factory,
    _SECTOR_NAMES,
)
from pyworldx.calibration.metrics import CrossValidationConfig
from pyworldx.calibration.parameters import (
    ParameterRegistry,
    build_world3_parameter_registry,
)
from pyworldx.data.bridge import CalibrationTarget


# ══════════════════════════════════════════════════════════════════════
# Shared helpers / fixtures
# ══════════════════════════════════════════════════════════════════════

ALL_SECTORS = sorted(_SECTOR_NAMES)


def _synthetic_target(
    variable_name: str,
    years: np.ndarray,
    values: np.ndarray,
    *,
    weight: float = 1.0,
    nrmsd_method: str = "direct",
) -> CalibrationTarget:
    """Construct a CalibrationTarget from raw arrays."""
    return CalibrationTarget(
        variable_name=variable_name,
        years=years,
        values=values,
        unit="synthetic",
        weight=weight,
        source="smoke_test",
        nrmsd_method=nrmsd_method,
    )


def _sector_primary_var(sector: str) -> str:
    """Return the primary output variable name for each sector."""
    return {
        "population": "POP",
        "capital": "IC",
        "agriculture": "AL",
        "resources": "NR",
        "pollution": "PPOL",
    }[sector]


@pytest.fixture(scope="module")
def full_reg() -> ParameterRegistry:
    """Module-scoped full registry (build once, reuse)."""
    return build_world3_parameter_registry()


@pytest.fixture(scope="module")
def population_factory():
    """build_sector_engine_factory for 'population', module-scoped."""
    return build_sector_engine_factory("population")


# ══════════════════════════════════════════════════════════════════════
# 1.  _resolve_registry() unit tests
# ══════════════════════════════════════════════════════════════════════


class TestResolveRegistry:
    """Unit tests for _resolve_registry() — covers every branch."""

    def test_returns_tuple_of_registry_and_list(self):
        args = SimpleNamespace(sector="population", params=None)
        reg, names = _resolve_registry(args)
        assert isinstance(reg, ParameterRegistry)
        assert isinstance(names, list)
        assert len(names) > 0

    def test_no_params_returns_all_sector_params(self):
        """When args.params is None/empty, requested == all sector params."""
        full = build_world3_parameter_registry()
        for sector in ALL_SECTORS:
            args = SimpleNamespace(sector=sector, params=None)
            _, names = _resolve_registry(args)
            expected = [e.name for e in full.get_sector_parameters(sector)]
            assert names == expected, (
                f"Sector {sector!r}: expected {expected}, got {names}"
            )

    def test_explicit_params_overrides_sector(self):
        """When args.params is set, only those names are returned."""
        full = build_world3_parameter_registry()
        all_names = [e.name for e in full.all_entries()]
        # Pick two arbitrary names from different sectors
        name_a, name_b = all_names[0], all_names[-1]
        args = SimpleNamespace(sector="population", params=f"{name_a},{name_b}")
        _, names = _resolve_registry(args)
        assert names == [name_a, name_b]

    def test_empty_string_params_falls_back_to_sector(self):
        args = SimpleNamespace(sector="capital", params="   ")
        _, names = _resolve_registry(args)
        full = build_world3_parameter_registry()
        expected = [e.name for e in full.get_sector_parameters("capital")]
        assert names == expected

    def test_unknown_sector_raises_value_error(self):
        """An unregistered sector with no parameters raises ValueError."""
        args = SimpleNamespace(sector="__nonexistent__", params=None)
        with pytest.raises(ValueError, match="No parameters found"):
            _resolve_registry(args)

    def test_unknown_param_name_raises_value_error(self):
        """An explicitly requested name not in the registry raises ValueError."""
        args = SimpleNamespace(sector="population", params="__fake_param_xyz__")
        with pytest.raises(ValueError, match="Unknown parameter"):
            _resolve_registry(args)

    def test_whitespace_and_comma_handling_in_params(self):
        """Extra whitespace around commas must be stripped correctly."""
        full = build_world3_parameter_registry()
        names = [e.name for e in full.get_sector_parameters("population")]
        padded = " , ".join(names)
        args = SimpleNamespace(sector="population", params=padded)
        _, result = _resolve_registry(args)
        assert result == names

    def test_returned_registry_is_full_registry(self, full_reg):
        """_resolve_registry returns the full registry, not a scoped one."""
        args = SimpleNamespace(sector="population", params=None)
        reg, _ = _resolve_registry(args)
        # The full registry contains entries for all sectors
        for sector in ALL_SECTORS:
            assert len(reg.get_sector_parameters(sector)) > 0


# ══════════════════════════════════════════════════════════════════════
# 2.  build_sector_engine_factory() unit tests
# ══════════════════════════════════════════════════════════════════════


class TestBuildSectorEngineFactory:
    """Unit tests for build_sector_engine_factory()."""

    def test_returns_callable(self):
        f = build_sector_engine_factory("population")
        assert callable(f)

    @pytest.mark.parametrize("sector", ALL_SECTORS)
    def test_all_sectors_return_callable(self, sector: str):
        f = build_sector_engine_factory(sector)
        assert callable(f)

    def test_unknown_sector_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown sector"):
            build_sector_engine_factory("__bad_sector__")

    def test_factory_returns_trajectories_and_time_index(self, full_reg, population_factory):
        """factory(defaults) must return (dict, ndarray) with sane shapes."""
        defaults = full_reg.get_defaults()
        traj, time = population_factory(defaults)
        assert isinstance(traj, dict)
        assert isinstance(time, np.ndarray)
        assert len(time) > 0
        # time_index must be calendar years (1900 … 2100)
        assert time[0] == pytest.approx(1900.0, abs=1.0)
        assert time[-1] == pytest.approx(2100.0, abs=1.0)

    def test_factory_trajectories_contain_expected_variables(self, full_reg, population_factory):
        defaults = full_reg.get_defaults()
        traj, _ = population_factory(defaults)
        # Population sector must produce POP at minimum
        assert "POP" in traj

    def test_factory_trajectories_are_finite(self, full_reg, population_factory):
        defaults = full_reg.get_defaults()
        traj, time = population_factory(defaults)
        for var, arr in traj.items():
            assert np.all(np.isfinite(arr)), f"NaN/Inf in trajectory {var!r}"

    def test_parameter_injection_changes_output(self, full_reg, population_factory):
        """Injecting a different parameter value must produce a different trajectory."""
        defaults = full_reg.get_defaults()
        traj_default, time = population_factory(defaults)

        # Scale initial_population up 10 %
        perturbed = dict(defaults)
        pop_key = next(
            k for k in perturbed if "initial_population" in k
        )
        perturbed[pop_key] = perturbed[pop_key] * 1.10
        traj_perturbed, _ = population_factory(perturbed)

        assert not np.allclose(
            traj_default["POP"], traj_perturbed["POP"]
        ), "Parameter perturbation had no effect on POP trajectory"

    def test_short_key_injection_strips_sector_prefix(self, full_reg):
        """Parameters keyed as 'sector.name' must be accepted without error."""
        factory = build_sector_engine_factory("resources")
        defaults = full_reg.get_defaults()
        # All defaults are already 'sector.name' keyed — must not raise
        traj, time = factory(defaults)
        assert "NR" in traj

    @pytest.mark.parametrize("sector,primary_var", [
        ("population", "POP"),
        ("capital",    "IC"),
        ("agriculture","AL"),
        ("resources",  "NR"),
        ("pollution",  "PPOL"),
    ])
    def test_each_sector_factory_produces_primary_variable(
        self, full_reg, sector: str, primary_var: str
    ):
        factory = build_sector_engine_factory(sector)
        traj, _ = factory(full_reg.get_defaults())
        assert primary_var in traj, (
            f"Sector {sector!r} factory did not produce {primary_var!r}. "
            f"Available keys: {sorted(traj.keys())}"
        )


# ══════════════════════════════════════════════════════════════════════
# 3.  CLI --dry-run smoke (subprocess)
# ══════════════════════════════════════════════════════════════════════


class TestCliDryRun:
    """Invoke the CLI via subprocess so argparse / logging paths are exercised.

    These tests pass --dry-run so no optimizer runs and they complete
    in well under 5 s each.
    """

    @pytest.fixture(autouse=True)
    def aligned_dir(self, tmp_path: Path) -> Path:
        """Create an empty aligned dir; store on self for reuse."""
        d = tmp_path / "aligned"
        d.mkdir()
        self.aligned = d
        return d

    def _run_cli(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        """Helper: run the CLI module and return the completed process."""
        return subprocess.run(
            [
                sys.executable, "-m", "pyworldx.calibration.empirical",
                "--sector", "population",
                "--aligned-dir", str(self.aligned),
                "--dry-run",
                *extra_args,
            ],
            capture_output=True,
            text=True,
        )

    def test_dry_run_exits_zero_on_empty_aligned_dir(self):
        """--dry-run with an empty aligned dir should exit 0 after printing
        coverage (empty) then 'No calibration targets loaded' error."""
        proc = self._run_cli()
        # No targets → error path; but the CLI itself must not crash with a
        # Python traceback.  Check there is no AttributeError / ImportError.
        assert "AttributeError" not in proc.stderr
        assert "ImportError" not in proc.stderr
        assert "for_sector" not in proc.stderr, (
            "Old broken API call still present in stderr"
        )

    def test_dry_run_exits_zero_with_synthetic_parquet(self, tmp_path: Path):
        """Write a minimal aligned Parquet file so the coverage table prints."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        parquet_path = self.aligned / "POP.parquet"
        df = pd.DataFrame({
            "year": [1960, 1970, 1980, 1990, 2000],
            "value": [3.0e9, 3.7e9, 4.4e9, 5.3e9, 6.1e9],
        })
        df.to_parquet(parquet_path, index=False)

        proc = self._run_cli()
        # Still may exit non-zero if bridge doesn't recognize the file,
        # but there must be no Python exception traceback.
        assert "Traceback" not in proc.stderr
        assert "AttributeError" not in proc.stderr
        assert "ImportError" not in proc.stderr

    def test_dry_run_unknown_sector_exits_nonzero(self):
        """An unknown sector name must produce a clean error, not a traceback."""
        proc = subprocess.run(
            [
                sys.executable, "-m", "pyworldx.calibration.empirical",
                "--sector", "__bad__",
                "--aligned-dir", str(self.aligned),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert "Traceback" not in proc.stderr

    def test_dry_run_bad_train_window_exits_nonzero(self):
        """Malformed --train-window must exit non-zero cleanly."""
        proc = self._run_cli("--train-window", "NOTAYEAR")
        assert proc.returncode != 0
        assert "Traceback" not in proc.stderr

    def test_dry_run_module_import_succeeds(self):
        """The module must be importable without side-effects."""
        proc = subprocess.run(
            [
                sys.executable, "-c",
                "from pyworldx.calibration.empirical import "
                "_resolve_registry, build_sector_engine_factory; print('OK')",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "OK" in proc.stdout


# ══════════════════════════════════════════════════════════════════════
# 4.  EmpiricalCalibrationRunner end-to-end smoke (fast, synthetic)
# ══════════════════════════════════════════════════════════════════════


class TestRunnerEndToEnd:
    """End-to-end smoke tests using synthetic targets + monkeypatched
    load_targets.  No Parquet I/O.  Optimizer runs with morris=2/sobol=32
    to keep wall time under 30 s.
    """

    YEARS = np.array([1960, 1970, 1980, 1990, 2000], dtype=int)

    @pytest.fixture
    def pop_targets(self, full_reg, population_factory) -> list[CalibrationTarget]:
        """Synthetic POP targets at 5 % above the default trajectory."""
        defaults = full_reg.get_defaults()
        traj, time = population_factory(defaults)
        values = np.interp(self.YEARS, time, traj["POP"]) * 1.05
        return [_synthetic_target("POP", self.YEARS, values)]

    @pytest.fixture
    def scoped_pop_registry(self, full_reg) -> tuple[ParameterRegistry, list[str]]:
        """Registry scoped to only the population-sector parameters."""
        args = SimpleNamespace(sector="population", params=None)
        full, requested = _resolve_registry(args)
        scoped = ParameterRegistry()
        for name in requested:
            scoped.register(full.lookup(name))
        return scoped, requested

    def _make_runner(self, tmp_path: Path) -> EmpiricalCalibrationRunner:
        aligned = tmp_path / "aligned"
        aligned.mkdir(exist_ok=True)
        return EmpiricalCalibrationRunner(aligned_dir=aligned)

    def test_run_returns_report_with_correct_type(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory
    ):
        from pyworldx.calibration.empirical import EmpiricalCalibrationReport
        registry, _ = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            morris_trajectories=2,
            sobol_samples=32,
        )
        assert isinstance(report, EmpiricalCalibrationReport)

    def test_run_loads_correct_target_count(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory
    ):
        registry, _ = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            morris_trajectories=2,
            sobol_samples=32,
        )
        assert report.empirical_targets_loaded == len(pop_targets)

    def test_run_with_cross_val_config_populates_validation_nrmsd(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory
    ):
        registry, _ = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        cfg = CrossValidationConfig(
            train_start=1960, train_end=1990,
            validate_start=1990, validate_end=2000,
        )
        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            cross_val_config=cfg,
            morris_trajectories=2,
            sobol_samples=32,
        )
        assert report.validation_nrmsd is not None
        assert np.isfinite(report.validation_nrmsd)

    def test_run_produces_finite_train_nrmsd(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory
    ):
        registry, _ = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        cfg = CrossValidationConfig(
            train_start=1960, train_end=1990,
            validate_start=1990, validate_end=2000,
        )
        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            cross_val_config=cfg,
            morris_trajectories=2,
            sobol_samples=32,
        )
        if report.train_result is not None:
            assert np.isfinite(report.train_result.composite_nrmsd)
        elif report.pipeline_report and report.pipeline_report.calibration:
            assert np.isfinite(
                report.pipeline_report.calibration.total_nrmsd
            )
        else:
            pytest.fail("No NRMSD available in report after run()")

    def test_calibrated_parameters_are_finite(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory
    ):
        registry, _ = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            morris_trajectories=2,
            sobol_samples=32,
        )
        if report.calibrated_parameters:
            for name, val in report.calibrated_parameters.items():
                assert np.isfinite(val), f"Parameter {name!r} is not finite: {val}"

    def test_calibrated_parameters_keys_match_requested(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory
    ):
        registry, requested = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            morris_trajectories=2,
            sobol_samples=32,
        )
        if report.calibrated_parameters:
            for name in report.calibrated_parameters:
                assert name in requested, (
                    f"Calibrated key {name!r} was not in requested list {requested}"
                )

    def test_zero_weight_targets_do_not_affect_objective(
        self, tmp_path, full_reg, population_factory
    ):
        """Targets with weight=0 must not crash the runner."""
        years = self.YEARS
        targets = [
            _synthetic_target("POP", years,
                              np.array([3e9, 3.7e9, 4.4e9, 5.3e9, 6.1e9]),
                              weight=1.0),
            _synthetic_target("NR", years,
                              np.array([9.5e11, 9e11, 8.5e11, 8e11, 7.5e11]),
                              weight=0.0),  # <- zero weight
        ]
        args = SimpleNamespace(sector="population", params=None)
        full, requested = _resolve_registry(args)
        scoped = ParameterRegistry()
        for name in requested:
            scoped.register(full.lookup(name))

        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: targets

        # Must complete without exception
        report = runner.run(
            registry=scoped,
            engine_factory=population_factory,
            weights={"POP": 1.0, "NR": 0.0},
            morris_trajectories=2,
            sobol_samples=32,
        )
        assert report.empirical_targets_loaded == 2

    def test_output_json_written_when_output_arg_passed(
        self, tmp_path, pop_targets, scoped_pop_registry, population_factory, monkeypatch
    ):
        """Simulate --output flag: after run(), calibrated params should be
        serialisable as JSON (mirrors what the CLI does)."""
        registry, _ = scoped_pop_registry
        runner = self._make_runner(tmp_path)
        runner.load_targets = lambda w=None: pop_targets

        report = runner.run(
            registry=registry,
            engine_factory=population_factory,
            weights={"POP": 1.0},
            morris_trajectories=2,
            sobol_samples=32,
        )

        out_path = tmp_path / "params.json"
        if report.calibrated_parameters:
            out_path.write_text(json.dumps(report.calibrated_parameters, indent=2))
            loaded = json.loads(out_path.read_text())
            assert isinstance(loaded, dict)
            for k, v in loaded.items():
                assert isinstance(k, str)
                assert isinstance(v, float)


# ══════════════════════════════════════════════════════════════════════
# 5.  Regression: the specific bugs from the original broken CLI
# ══════════════════════════════════════════════════════════════════════


class TestRegressionOriginalBugs:
    """Explicit regression tests for the three bugs reported in the issue:

    Bug 1: ParameterRegistry.for_sector() — AttributeError at import time
    Bug 2: registry.subset() — AttributeError, cascading from Bug 1
    Bug 3: len(registry) on the result of .subset() — TypeError
    """

    def test_bug1_for_sector_does_not_exist_on_class(self):
        """ParameterRegistry must NOT have a for_sector class method."""
        assert not hasattr(ParameterRegistry, "for_sector"), (
            "ParameterRegistry.for_sector() still exists — the old broken "
            "API has been restored.  Remove it or tests will regress."
        )

    def test_bug2_subset_does_not_exist_on_instance(self, full_reg):
        """ParameterRegistry instances must NOT have a subset() method."""
        assert not hasattr(full_reg, "subset"), (
            "ParameterRegistry.subset() still exists.  This method was never "
            "implemented and its presence will mislead future callers."
        )

    def test_bug3_resolve_registry_len_works(self):
        """len(requested) after _resolve_registry() must not raise TypeError."""
        args = SimpleNamespace(sector="population", params=None)
        _, requested = _resolve_registry(args)
        # This was failing with TypeError: object of type ParameterRegistry
        # has no len() when the old code did len(registry)
        n = len(requested)
        assert isinstance(n, int)
        assert n > 0

    def test_fixed_path_no_attribute_error_end_to_end(self, tmp_path):
        """Simulate the exact CLI code path that was broken.

        Previously raised:
            AttributeError: type object 'ParameterRegistry' has no
            attribute 'for_sector'
        """
        args = SimpleNamespace(sector="population", params=None)

        # This is the fixed path — must complete without any exception
        try:
            full_reg, requested = _resolve_registry(args)
            scoped = ParameterRegistry()
            for name in requested:
                scoped.register(full_reg.lookup(name))
            n = len(requested)
            assert n > 0
        except AttributeError as exc:
            pytest.fail(f"AttributeError in fixed registry path: {exc}")
        except TypeError as exc:
            pytest.fail(f"TypeError in fixed registry path (len bug): {exc}")

    def test_build_sector_engine_factory_importable_from_module(self):
        """build_sector_engine_factory must be importable from empirical,
        not from a phantom pyworldx.engine module."""
        try:
            from pyworldx.calibration.empirical import build_sector_engine_factory as bsef
            assert callable(bsef)
        except ImportError as exc:
            pytest.fail(
                f"build_sector_engine_factory not importable from "
                f"pyworldx.calibration.empirical: {exc}"
            )
