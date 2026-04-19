"""Verify Phase 2 shared helpers load and return expected defaults."""
from __future__ import annotations

from pyworldx.sectors.base import RunContext
from tests._phase2_helpers import base_shared, make_ctx


def test_make_ctx_returns_runcontext() -> None:
    ctx = make_ctx()
    assert isinstance(ctx, RunContext)
    assert ctx.master_dt == 1.0
    assert ctx.t_start == 0.0  # relative time, NOT 1900
    assert ctx.t_end == 200.0


def test_make_ctx_custom_dt() -> None:
    ctx = make_ctx(master_dt=0.5)
    assert ctx.master_dt == 0.5


def test_base_shared_has_all_defaults() -> None:
    s = base_shared()
    assert s["POP"].magnitude == 7.8e9
    assert s["industrial_output"].magnitude == 1.0e11
    assert s["energy_supply_factor"].magnitude == 1.0
    assert s["labor_force_multiplier"].magnitude == 1.0


def test_base_shared_override_known_key() -> None:
    s = base_shared(POP=1.0e10)
    assert s["POP"].magnitude == 1.0e10
    assert s["POP"].unit == "people"  # preserves unit of known key


def test_base_shared_override_unknown_key_uses_dimensionless() -> None:
    s = base_shared(some_new_key=5.0)
    assert s["some_new_key"].magnitude == 5.0
    assert s["some_new_key"].unit == "dimensionless"


def test_base_shared_year_param_is_accepted() -> None:
    # year param exists for human readability, should not raise
    s = base_shared(year=1900)
    assert "POP" in s
