"""Shared test fixtures for pyWorldX."""

from __future__ import annotations

from typing import Callable

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
