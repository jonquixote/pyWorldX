"""Integration tests: EmpiricalCalibrationRunner with synthetic targets."""
import pytest
import numpy as np
from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
from pyworldx.data.bridge import CalibrationTarget


@pytest.fixture
def runner_no_parquet(tmp_path):
    """Runner pointing at an empty (but existing) aligned dir."""
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    return EmpiricalCalibrationRunner(aligned_dir=aligned)


def test_runner_load_targets_empty_dir_returns_empty_list(runner_no_parquet):
    targets = runner_no_parquet.load_targets()
    # data_pipeline not installed/empty dir → graceful empty list
    assert isinstance(targets, list)
    assert len(targets) == 0


def test_runner_quick_evaluate_with_synthetic_targets(
    runner_no_parquet, full_registry, fake_engine_factory
):
    """quick_evaluate should work even without Parquet data if targets injected."""
    targets = [
        CalibrationTarget(
            variable_name="POP",
            years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
            values=np.array([3.0e9, 3.7e9, 4.4e9, 5.3e9, 6.1e9]),
            unit="persons", weight=1.0, source="synthetic", nrmsd_method="direct",
        )
    ]
    # Inject targets directly via bridge.compare
    traj, t_idx = fake_engine_factory(full_registry.get_defaults())
    result = runner_no_parquet.bridge.compare(targets, traj, t_idx)
    assert np.isfinite(result.composite_nrmsd)
    assert result.n_targets == 1


def test_runner_run_with_no_targets_returns_empty_report(
    runner_no_parquet, full_registry, fake_engine_factory
):
    """If load_targets returns [], run() returns an EmpiricalCalibrationReport
    with empirical_targets_loaded == 0 and calibrated_parameters == {}."""
    report = runner_no_parquet.run(
        registry=full_registry,
        engine_factory=fake_engine_factory,
    )
    assert report.empirical_targets_loaded == 0
    assert report.calibrated_parameters == {}
    assert report.converged is False


def test_full_population_calibration_smoke(full_registry):
    """Smoke test: single-sector calibration with synthetic targets.

    Uses a 2-trajectory Morris + 32-sample Sobol to keep wall time < 60s.
    This is the key end-to-end test for the whole fixed CLI path.
    """
    from pyworldx.calibration.empirical import (
        _resolve_registry,
        build_sector_engine_factory,
    )
    from pyworldx.calibration.metrics import CrossValidationConfig
    from types import SimpleNamespace
    import tempfile
    from pathlib import Path

    # Step 1: resolve registry via the fixed function
    args = SimpleNamespace(sector="population", params=None)
    registry, requested = _resolve_registry(args)
    assert len(requested) == 3

    # Step 2: build engine factory
    engine_factory = build_sector_engine_factory("population")

    # Step 3: build synthetic targets
    defaults = registry.get_defaults()
    traj, time = engine_factory(defaults)
    synthetic_targets = [
        CalibrationTarget(
            variable_name="POP",
            years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
            values=np.interp([1960, 1970, 1980, 1990, 2000], time, traj["POP"]) * 1.05,
            unit="persons", weight=1.0, source="synthetic", nrmsd_method="direct",
        )
    ]

    # Step 4: Run calibration with mocked load_targets
    with tempfile.TemporaryDirectory() as td:
        runner = EmpiricalCalibrationRunner(aligned_dir=Path(td))
        # monkeypatch instance method to return synthetic targets
        runner.load_targets = lambda w=None: synthetic_targets  # type: ignore

        cfg = CrossValidationConfig(
            train_start=1960, train_end=1990,
            validate_start=1990, validate_end=2000,
        )

        weights = {"POP": 1.0}

        report = runner.run(
            registry=registry,
            engine_factory=engine_factory,
            weights=weights,
            cross_val_config=cfg,
            morris_trajectories=2,  # fast smoke test
            sobol_samples=32,       # fast smoke test
        )

        assert report.converged is True
        assert report.total_evaluations > 0
        assert "population.len_scale" in report.calibrated_parameters
        assert report.train_result is not None
        assert report.validation_nrmsd is not None
