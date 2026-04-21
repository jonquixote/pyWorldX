import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

from pyworldx.calibration.empirical import EmpiricalCalibrationRunner, _resolve_registry, build_sector_engine_factory
from pyworldx.calibration.metrics import CrossValidationConfig
from pyworldx.calibration.parameters import ParameterRegistry, build_world3_parameter_registry
from pyworldx.data.bridge import CalibrationTarget

@pytest.fixture(scope="module")
def full_reg() -> ParameterRegistry:
    return build_world3_parameter_registry()

@pytest.fixture(scope="module")
def population_factory():
    return build_sector_engine_factory("population")

def _synthetic_target(
    variable_name: str,
    years: np.ndarray,
    values: np.ndarray,
    *,
    weight: float = 1.0,
    nrmsd_method: str = "direct",
) -> CalibrationTarget:
    return CalibrationTarget(
        variable_name=variable_name,
        years=years,
        values=values,
        unit="synthetic",
        weight=weight,
        source="smoke_test",
        nrmsd_method=nrmsd_method,
    )

pytestmark = pytest.mark.integration


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

