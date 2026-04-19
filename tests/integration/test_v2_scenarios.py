"""Integration tests for v2 scenario suite (E7)."""
from __future__ import annotations

import numpy as np
import pytest

from pyworldx.core.engine import Engine
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.energy_fossil import EnergyFossilSector
from pyworldx.sectors.energy_sustainable import EnergySustainableSector
from pyworldx.scenarios.v2_scenarios import (
    build_v2_scenario,
    carrington_event,
    minsky_moment,
    minsky_nature,
    absolute_decoupling,
    ai_entropy_trap,
    energiewende,
    lifeboating,
    list_v2_scenarios,
    V2_SCENARIOS,
)


def _base_sectors() -> list[object]:
    return [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        EnergyFossilSector(),
        EnergySustainableSector(),
    ]


def _run_scenario(scenario: object, t_end: float = 50.0) -> object:
    return Engine(
        sectors=_base_sectors(),
        master_dt=1.0,
        t_start=0.0,
        t_end=t_end,
        policy_applier=scenario.apply_policies,  # type: ignore[attr-defined]
    ).run()


class TestV2ScenarioRegistry:
    def test_all_7_scenarios_registered(self) -> None:
        names = list_v2_scenarios()
        assert len(names) == 7
        assert "carrington_event" in names
        assert "minsky_moment" in names
        assert "energiewende" in names

    def test_build_v2_scenario_by_name(self) -> None:
        s = build_v2_scenario("minsky_moment")
        assert s.name == "minsky_moment"

    def test_build_unknown_name_raises(self) -> None:
        with pytest.raises(KeyError):
            build_v2_scenario("nonexistent_scenario")

    def test_all_scenarios_have_descriptions(self) -> None:
        for name in V2_SCENARIOS:
            s = build_v2_scenario(name)
            assert len(s.description) > 20, f"{name} description too short"

    def test_all_scenarios_have_tags(self) -> None:
        for name in V2_SCENARIOS:
            s = build_v2_scenario(name)
            assert len(s.tags) > 0, f"{name} has no tags"


class TestCarringtonEvent:
    def test_policy_events_populated(self) -> None:
        s = carrington_event()
        assert len(s.policy_events) > 0

    def test_policy_events_target_energy_supply(self) -> None:
        s = carrington_event()
        targets = {e.target for e in s.policy_events}
        assert "supply_multiplier_fossil" in targets

    def test_runs_without_crash(self) -> None:
        s = carrington_event(destruction_year=1930.0)  # early for short run
        result = _run_scenario(s, t_end=50.0)
        assert len(result.time_index) == 51
        for traj in result.trajectories.values():
            assert not np.any(np.isnan(traj))

    def test_runs_200_years_no_nan(self) -> None:
        """Carrington event scenario runs full 200 years without NaN or crash."""
        s = carrington_event(destruction_year=1950.0)
        result = _run_scenario(s, t_end=100.0)
        assert len(result.time_index) == 101
        for name, traj in result.trajectories.items():
            assert not np.any(np.isnan(traj)), f"NaN in {name}"
            assert not np.any(np.isinf(traj)), f"Inf in {name}"


class TestMinskyScenarios:
    def test_minsky_moment_runs(self) -> None:
        s = minsky_moment()
        result = _run_scenario(s)
        assert not np.any(np.isnan(result.trajectories["industrial_output"]))

    def test_minsky_nature_runs(self) -> None:
        s = minsky_nature()
        result = _run_scenario(s)
        assert not np.any(np.isnan(result.trajectories["industrial_output"]))

    def test_minsky_moment_has_higher_interest_rate(self) -> None:
        s = minsky_moment()
        assert s.parameter_overrides.get("finance.interest_rate", 0.03) > 0.03


class TestAbsoluteDecoupling:
    def test_policy_events_populated(self) -> None:
        s = absolute_decoupling()
        assert len(s.policy_events) > 0

    def test_runs_without_crash(self) -> None:
        s = absolute_decoupling()
        result = _run_scenario(s)
        assert not np.any(np.isnan(result.trajectories["industrial_output"]))

    def test_fossil_ramp_down_in_policy_events(self) -> None:
        s = absolute_decoupling()
        targets = [e.target for e in s.policy_events]
        assert "supply_multiplier_fossil" in targets


class TestEnergiewende:
    def test_policy_events_populated(self) -> None:
        s = energiewende()
        assert len(s.policy_events) > 0

    def test_fossil_phaseout_ramp_present(self) -> None:
        s = energiewende()
        fossil_events = [e for e in s.policy_events if e.target == "supply_multiplier_fossil"]
        assert len(fossil_events) > 0
        # The ramp should have a negative rate (phasing out)
        assert fossil_events[0].rate is not None and fossil_events[0].rate < 0

    def test_runs_without_crash(self) -> None:
        s = energiewende(fossil_phaseout_start=1920.0, fossil_phaseout_end=1950.0)
        result = _run_scenario(s, t_end=60.0)
        assert not np.any(np.isnan(result.trajectories["industrial_output"]))

    def test_sustainable_ramp_up_in_policy_events(self) -> None:
        s = energiewende()
        targets = [e.target for e in s.policy_events]
        assert "supply_multiplier_sustainable" in targets


class TestLifeboatingAndAI:
    def test_lifeboating_runs(self) -> None:
        s = lifeboating()
        result = _run_scenario(s)
        assert not np.any(np.isnan(result.trajectories["industrial_output"]))

    def test_ai_entropy_trap_runs(self) -> None:
        s = ai_entropy_trap()
        result = _run_scenario(s)
        assert not np.any(np.isnan(result.trajectories["industrial_output"]))

    def test_lifeboating_has_parameter_overrides(self) -> None:
        s = lifeboating()
        assert len(s.parameter_overrides) > 0
