"""Test Scenario wiring: apply_parameter_overrides and policy_applier."""
from __future__ import annotations

from pyworldx.core.engine import Engine
from pyworldx.scenarios.scenario import apply_parameter_overrides
from pyworldx.scenarios.v2_scenarios import absolute_decoupling, minsky_moment
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.population import PopulationSector


def test_parameter_overrides_mutate_sector() -> None:
    """apply_parameter_overrides sets resource_elasticity=0.0 on CapitalSector."""
    scen = absolute_decoupling()
    cap = CapitalSector()
    original = cap.resource_elasticity
    apply_parameter_overrides(scen, [cap])
    assert cap.resource_elasticity == 0.0
    assert original != 0.0  # sanity: default is non-zero


def test_parameter_overrides_skips_unknown_sector() -> None:
    """Override for unknown sector name must not raise."""
    from pyworldx.scenarios.scenario import Scenario
    scen = Scenario(
        name="test",
        description="",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"nonexistent.attr": 1.0},
    )
    apply_parameter_overrides(scen, [CapitalSector()])  # must not raise


def test_scenario_apply_policies_wires_to_engine() -> None:
    """Engine accepts policy_applier=scenario.apply_policies without error."""
    scen = minsky_moment()
    engine = Engine(
        sectors=[PopulationSector()],
        policy_applier=scen.apply_policies,
        t_start=0.0,
        t_end=1.0,
        master_dt=1.0,
    )
    engine.run()  # must not raise
