"""Unit tests for FinanceSector leverage_fraction parameter."""
from __future__ import annotations

import pytest

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.finance import FinanceSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _base_inputs() -> dict[str, Quantity]:
    return {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "IC": Quantity(2.1e11, "capital_units"),
        "SC": Quantity(1.44e11, "capital_units"),
        "AL": Quantity(0.9e9, "hectares"),
        "POP": Quantity(1.65e9, "persons"),
        "tnds_aes": Quantity(0.0, "capital_units"),
        "education_tnds": Quantity(0.0, "capital_units"),
        "damages_tnds": Quantity(0.0, "capital_units"),
    }


def test_leverage_fraction_default_zero() -> None:
    """FinanceSector must default leverage_fraction to 0.0."""
    s = FinanceSector()
    assert s.leverage_fraction == 0.0


def test_leverage_zero_same_dDg_as_no_leverage() -> None:
    """leverage_fraction=0 must produce same dD_g as before the feature existed."""
    ctx = _ctx()
    s = FinanceSector(leverage_fraction=0.0)
    out = s.compute(0.0, s.init_stocks(ctx), _base_inputs(), ctx)
    s2 = FinanceSector(leverage_fraction=0.2)
    out2 = s2.compute(0.0, s2.init_stocks(ctx), _base_inputs(), ctx)
    # With leverage, D_g grows faster than without
    assert out2["d_D_g"].magnitude >= out["d_D_g"].magnitude


def test_nonzero_leverage_increases_debt_growth() -> None:
    """leverage_fraction=0.2 must produce higher dD_g than leverage_fraction=0.0."""
    ctx = _ctx()
    s_no_lev = FinanceSector(leverage_fraction=0.0)
    s_lev = FinanceSector(leverage_fraction=0.2)
    out_no = s_no_lev.compute(0.0, s_no_lev.init_stocks(ctx), _base_inputs(), ctx)
    out_lev = s_lev.compute(0.0, s_lev.init_stocks(ctx), _base_inputs(), ctx)
    assert out_lev["d_D_g"].magnitude > out_no["d_D_g"].magnitude


def test_leverage_fraction_is_scenario_settable() -> None:
    """finance.leverage_fraction must be overridable via apply_parameter_overrides."""
    from pyworldx.scenarios.scenario import apply_parameter_overrides, Scenario

    scenario = Scenario(
        name="test",
        description="test",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"finance.leverage_fraction": 0.3},
    )
    s = FinanceSector()
    apply_parameter_overrides(scenario, [s])
    assert s.leverage_fraction == pytest.approx(0.3)


def test_leverage_fraction_clamped() -> None:
    """leverage_fraction must be clamped to [0, 1] regardless of input."""
    s_neg = FinanceSector(leverage_fraction=-0.5)
    assert s_neg.leverage_fraction == 0.0
    s_high = FinanceSector(leverage_fraction=2.0)
    assert s_high.leverage_fraction == 1.0


def test_minsky_moment_scenario_has_leverage_override() -> None:
    """minsky_moment() must include finance.leverage_fraction in parameter_overrides."""
    from pyworldx.scenarios.v2_scenarios import minsky_moment

    s = minsky_moment()
    assert "finance.leverage_fraction" in s.parameter_overrides
    assert s.parameter_overrides["finance.leverage_fraction"] > 0.0
