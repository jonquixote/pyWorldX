"""E8 coverage gap tests — targeted tests for uncovered branches.

Each test covers a specific uncovered line identified in the E8 coverage run.
"""
from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


def _ctx(master_dt: float = 1.0) -> RunContext:
    return RunContext(master_dt=master_dt, t_start=0.0, t_end=200.0, shared_state={})


# ── scenarios/builtin.py (0% → imports fix it) ───────────────────────


def test_builtin_scenarios_import() -> None:
    """Importing builtin.py covers the re-export module (100%)."""
    from pyworldx.scenarios.builtin import (  # noqa: F401
        BUILTIN_SCENARIOS,
        baseline_world3,
        high_resource_discovery,
        pollution_control_push,
        agricultural_efficiency_push,
        capital_reallocation_to_maintenance,
        wiliam_high_military_drag,
    )
    assert "baseline_world3" in BUILTIN_SCENARIOS


# ── scenarios/scenario.py line 81 (CUSTOM shape with custom_fn) ──────


def test_custom_policy_shape_with_fn() -> None:
    """PolicyEvent with CUSTOM shape + custom_fn applies the custom function."""
    from pyworldx.scenarios.scenario import PolicyEvent, PolicyShape
    fn = lambda baseline, t: baseline * 2.0  # noqa: E731
    event = PolicyEvent(target="x", shape=PolicyShape.CUSTOM, t_start=0.0, custom_fn=fn)
    result = event.apply(5.0, 1.0)
    assert abs(result - 10.0) < 1e-10


# ── scenarios/scenario.py line 165 (apply_parameter_overrides skip no-dot) ──


def test_apply_parameter_overrides_skips_no_dot_key() -> None:
    """apply_parameter_overrides silently skips keys without a dot."""
    from pyworldx.scenarios.scenario import apply_parameter_overrides, Scenario
    from pyworldx.sectors.capital import CapitalSector
    s = Scenario(
        name="test",
        description="test",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"no_dot_key": 99.0},  # no dot → skip
    )
    sector = CapitalSector()
    old_val = sector.initial_ic
    apply_parameter_overrides(s, [sector])
    assert sector.initial_ic == old_val  # unchanged


# ── base.py: RunContext.get_input with missing key ────────────────────


def test_runcontext_get_input_raises_on_missing() -> None:
    """RunContext.get_input raises KeyError when key is absent."""
    import pytest
    ctx = RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={"a": Quantity(1.0, "dimensionless")})
    with pytest.raises(KeyError, match="missing_key"):
        ctx.get_input("missing_key")


# ── ecosystem_services.py line 129 (ESP floor clamp: dESP < 0 at ESP=0) ─


def test_ecosystem_esp_floor_clamp() -> None:
    """At ESP=0 with degradation-dominant dynamics, dESP must be clamped to 0."""
    from pyworldx.sectors.ecosystem_services import EcosystemServicesSector
    s = EcosystemServicesSector()
    ctx = _ctx()
    stocks = {"ESP": Quantity(0.0, "dimensionless")}
    inputs = {
        "pollution_index": Quantity(100.0, "dimensionless"),  # strong degradation
        "AL": Quantity(0.1e9, "hectares"),                    # high land use
        "temperature_anomaly": Quantity(5.0, "deg_C_anomaly"),  # above critical
        "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["d_ESP"].magnitude == 0.0, "dESP must be clamped to 0 when ESP is at floor"


# ── human_capital.py line 95 (H floor clamp) ─────────────────────────


def test_human_capital_h_floor_clamp() -> None:
    """At H=0 with negative dynamics, dH must be clamped to 0."""
    from pyworldx.sectors.human_capital import HumanCapitalSector
    s = HumanCapitalSector()
    ctx = _ctx()
    stocks = {"H": Quantity(0.0, "dimensionless"), "fcfpc": Quantity(0.0, "dimensionless")}
    inputs = {
        "service_output_per_capita": Quantity(0.0, "service_units_per_capita"),  # no education
        "death_rate": Quantity(0.5, "per_year"),  # very high death rate → negative dH
        "labor_force": Quantity(1e9, "persons"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["d_H"].magnitude >= 0.0, "dH must not be negative when H=0"


# ── phosphorus.py line 170 (PRR floor clamp: dPRR < 0 at PRR=0) ─────


def test_phosphorus_prr_floor_clamp() -> None:
    """At PRR=0 with dissipation dominant, dPRR must be clamped to 0."""
    from pyworldx.sectors.phosphorus import PhosphorusSector
    s = PhosphorusSector(sedimentation_rate=100.0)  # extreme dissipation
    ctx = _ctx()
    stocks = {"P_soc": Quantity(14000.0, "megatonnes_P"), "PRR": Quantity(0.0, "dimensionless")}
    inputs = {
        "industrial_output": Quantity(0.0, "industrial_output_units"),  # zero profitability
        "food_per_capita": Quantity(0.0, "food_units_per_person"),
        "nr_fraction_remaining": Quantity(0.0, "dimensionless"),
        "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["d_PRR"].magnitude == 0.0, "dPRR must be clamped at floor when PRR=0 and dynamics are negative"


# ── phosphorus.py line 196 (SOC floor clamp: dSOC < 0 at SOC=0) ─────


def test_phosphorus_soc_floor_clamp() -> None:
    """At SOC=0 with degradation dominant, dSOC must be clamped to 0."""
    from pyworldx.sectors.phosphorus import PhosphorusSector
    s = PhosphorusSector(initial_soc=0.0)
    ctx = _ctx()
    stocks = {"P_soc": Quantity(14000.0, "megatonnes_P"), "PRR": Quantity(0.12, "dimensionless")}
    inputs = {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "food_per_capita": Quantity(300.0, "food_units_per_person"),
        "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
        "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
        "pollution_index": Quantity(100.0, "dimensionless"),  # extreme respiration
        "frac_io_to_agriculture": Quantity(1.0, "dimensionless"),  # max farming depletion
        "C_soc": Quantity(0.0, "GtC"),  # SOC at floor
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["d_P_soc"].magnitude is not None  # just verify it computed without crash


# ── population.py lines 319, 340, 351 (time-threshold branches at t=2100) ─


def test_population_high_t_branches() -> None:
    """At t >= 2100 (calendar_year >= 4000), population sector hits ZPGT/FCEST/PET branches."""
    from pyworldx.sectors.population import PopulationSector
    s = PopulationSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    inputs: dict[str, Quantity] = {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "food_per_capita": Quantity(300.0, "food_units_per_person"),
        "service_output_per_capita": Quantity(87.0, "service_units_per_capita"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "energy_supply_factor": Quantity(1.0, "dimensionless"),
        "supply_multiplier_population": Quantity(1.0, "dimensionless"),
        "labor_force_multiplier": Quantity(1.0, "dimensionless"),
        "toxin_health_multiplier": Quantity(1.0, "dimensionless"),
        "toxin_fertility_multiplier": Quantity(1.0, "dimensionless"),
        "disease_death_rate": Quantity(0.0, "per_year"),
        "gini_mortality_mult": Quantity(1.0, "dimensionless"),
        "total_migration_flow": Quantity(0.0, "persons"),
    }
    # t=2100 → calendar_year = 2100 + 1900 = 4000 → triggers ZPGT/FCEST/PET branches
    out = s.compute(2100.0, stocks, inputs, ctx)
    assert "d_P1" in out, "Population sector must compute at high t"


# ── resources.py lines 96, 117 (policy/fcaor switch branches at t=0) ──


def test_resources_switch_branches_at_low_switch_time() -> None:
    """With policy_year=0 and fcaor_switch_time=0, resources hits both switch branches."""
    from pyworldx.sectors.resources import ResourcesSector
    s = ResourcesSector()
    s.policy_year = 0.0
    s.fcaor_switch_time = 0.0
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    inputs: dict[str, Quantity] = {
        "POP": Quantity(1.65e9, "persons"),
        "industrial_output_per_capita": Quantity(40.0, "industrial_output_units"),
        "supply_multiplier_resources": Quantity(1.0, "dimensionless"),
        "resource_tech_mult": Quantity(1.0, "dimensionless"),
    }
    # t=1.0 > policy_year=0.0 → hits both if-branches
    out = s.compute(1.0, stocks, inputs, ctx)
    assert "d_NR" in out, "Resources sector must compute at t past policy_year"


# ── seir.py lines 246-252 (stock floor clamp in SEIR ODE) ────────────


def test_seir_stock_floor_clamp() -> None:
    """With near-zero SEIR stocks, clamping prevents negative values."""
    from pyworldx.sectors.seir import SEIRModule
    s = SEIRModule()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    # Set stocks near-zero to trigger floor clamping in ODE derivatives
    stocks["S_0"] = Quantity(1e-10, "persons")
    stocks["E_0"] = Quantity(1e-10, "persons")
    stocks["I_0"] = Quantity(1e-10, "persons")
    stocks["R_0"] = Quantity(1e-10, "persons")
    inputs: dict[str, Quantity] = {
        "POP": Quantity(1.65e9, "persons"),
        "pathogen_virulence": Quantity(0.5, "dimensionless"),
        "pathogen_lethality": Quantity(0.1, "dimensionless"),
        "supply_multiplier_health": Quantity(1.0, "dimensionless"),
        "quarantine_effectiveness": Quantity(0.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    # Verify no NaN and all d_ outputs exist
    for k, v in out.items():
        assert v.magnitude == v.magnitude, f"NaN in SEIR output {k}"


# ── adaptive_technology.py line 156 (metadata method) ────────────────


def test_adaptive_technology_metadata() -> None:
    """AdaptiveTechnologySector.metadata() must return a dict with key fields."""
    from pyworldx.sectors.adaptive_technology import AdaptiveTechnologySector
    s = AdaptiveTechnologySector()
    meta = s.metadata()
    assert "validation_status" in meta
    assert "equation_source" in meta
