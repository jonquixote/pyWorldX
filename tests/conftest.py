"""Shared test fixtures for pyWorldX."""

from __future__ import annotations

from typing import Callable

import numpy as np
import pytest

from pyworldx.core.central_registrar import CentralRegistrar
from pyworldx.core.engine import Engine
from pyworldx.core.result import RunResult
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.welfare import WelfareSector
from pyworldx.sectors.finance import FinanceSector
from pyworldx.sectors.energy_fossil import EnergyFossilSector
from pyworldx.sectors.energy_sustainable import EnergySustainableSector
from pyworldx.sectors.energy_technology import EnergyTechnologySector
from pyworldx.sectors.pollution_ghg import PollutionGHGModule
from pyworldx.sectors.pollution_toxins import PollutionToxinModule
from pyworldx.sectors.gini_distribution import GiniDistributionSector


# ── T0-0: --fast flag ─────────────────────────────────────────────────

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --fast CLI flag to skip slow optimizer + data-bridge I/O in tests."""
    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help=(
            "Stub optimizer and DataBridge for fast wiring checks. "
            "No Parquet I/O, no Bayesian optimization loop. "
            "Use for CI pre-flight; run full suite for acceptance."
        ),
    )


@pytest.fixture
def fast_mode(request: pytest.FixtureRequest) -> bool:
    """True when --fast is passed on the CLI."""
    return bool(request.config.getoption("--fast"))


@pytest.fixture(autouse=False)
def stub_optimizer(fast_mode: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """When --fast: patch CalibrationRunner._run_optimizer to return a
    pre-seeded parameter dict that is known to satisfy all NRMSD thresholds.

    The stub also patches DataBridge.load_targets so integration tests that
    inherit this fixture do not hit the Parquet cache on a clean checkout.
    """
    if not fast_mode:
        return

    # Pre-seeded parameters that pass all Nebel 2023 NRMSD thresholds
    _FAST_PARAMS: dict[str, float] = {
        "resources.initial_nr": 1.0e12,
        "pollution.pcrum": 0.001,
        "agriculture.io_pc_ref": 600.0,
    }

    # Stub the optimizer loop
    try:
        from pyworldx.calibration.runner import CalibrationRunner
        monkeypatch.setattr(
            CalibrationRunner,
            "_run_optimizer",
            lambda self, objective, bounds: _FAST_PARAMS,
        )
    except (ImportError, AttributeError):
        pass  # CalibrationRunner not yet implemented — skip gracefully

    # Stub DataBridge.load_targets to return an empty list (no file I/O)
    try:
        from pyworldx.data.bridge import DataBridge
        monkeypatch.setattr(
            DataBridge,
            "load_targets",
            lambda self, *args, **kwargs: [],
        )
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def fake_ctx() -> RunContext:
    """Return a minimal RunContext with empty shared_state."""
    return RunContext(
        master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={}
    )


@pytest.fixture
def default_5_sectors() -> list[object]:
    """Return the canonical 5 World3-03 sectors."""
    return [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
    ]


@pytest.fixture
def phase1_all_sectors() -> list[object]:
    """Return all Phase 1 sectors (5 World3 + 8 Phase 1 + Welfare)."""
    return [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        FinanceSector(),
        EnergyFossilSector(),
        EnergySustainableSector(),
        EnergyTechnologySector(),
        PollutionGHGModule(),
        PollutionToxinModule(),
        GiniDistributionSector(),
        WelfareSector(),
    ]


@pytest.fixture
def run_200yr() -> Callable[
    [list[object], CentralRegistrar | None],
    RunResult,
]:
    """Factory that runs a sector list for 200 years."""
    def _run(
        sector_list: list[object],
        central_registrar: CentralRegistrar | None = None,
    ) -> RunResult:
        return Engine(
            sectors=sector_list,
            master_dt=1.0,
            t_start=0.0,
            t_end=200.0,
            central_registrar=central_registrar,
        ).run()
    return _run


# ── Phase 0: Calibration fixtures ─────────────────────────────────────

from pyworldx.calibration.parameters import build_world3_parameter_registry  # noqa: E402
from pyworldx.data.bridge import CalibrationTarget  # noqa: E402


@pytest.fixture
def full_registry():
    """The canonical 17-parameter World3 registry."""
    return build_world3_parameter_registry()


@pytest.fixture
def fake_engine_factory():
    """Minimal engine_factory stub: linear growth for all variables."""
    def factory(params: dict) -> tuple[dict, np.ndarray]:
        time = np.arange(1900, 2101, dtype=float)
        pop0 = params.get("population.initial_population", 1.65e9)
        trajectories = {
            "POP": pop0 * (1 + 0.015 * (time - 1900)),
            "IC":  2.1e11 * (1 + 0.02 * (time - 1900)),
            "AL":  9e8 * np.ones_like(time),
            "NR":  1e12 * np.exp(-0.005 * (time - 1900)),
            "PPOL": 2.5e7 * (1 + 0.03 * (time - 1900)),
        }
        return trajectories, time
    return factory


@pytest.fixture
def minimal_targets():
    """Two CalibrationTargets with known analytic NRMSD."""
    years = np.array([1960, 1970, 1980, 1990, 2000], dtype=int)
    return [
        CalibrationTarget(
            variable_name="POP",
            years=years,
            values=np.array([3.0e9, 3.7e9, 4.4e9, 5.3e9, 6.1e9]),
            unit="persons",
            weight=1.0,
            source="test",
            nrmsd_method="direct",
        ),
        CalibrationTarget(
            variable_name="NR",
            years=years,
            values=np.array([9.5e11, 9.0e11, 8.5e11, 8.0e11, 7.5e11]),
            unit="resource_units",
            weight=1.0,
            source="test",
            nrmsd_method="change_rate",
        ),
    ]
