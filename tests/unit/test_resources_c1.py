"""Task C1: resources.py must compute and emit tech_metals_availability.

Reads tech_metals_demand from shared_state (published by energy_technology.py),
then computes availability = f(nr_fraction_remaining, demand_pressure).
"""
from __future__ import annotations

from pyworldx.sectors.resources import ResourcesSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _compute(nr: float = 1e12, tech_metals_demand: float = 0.0) -> dict:
    sector = ResourcesSector()
    ctx = make_ctx()
    stocks = {"NR": Quantity(nr, "resource_units")}
    shared = base_shared()
    shared["tech_metals_demand"] = Quantity(tech_metals_demand, "dimensionless")
    return sector.compute(t=0.0, stocks=stocks, inputs=shared, ctx=ctx)


def test_tech_metals_availability_in_output() -> None:
    result = _compute()
    assert "tech_metals_availability" in result, (
        f"tech_metals_availability missing; keys={list(result)}"
    )
    assert isinstance(result["tech_metals_availability"], Quantity)


def test_tech_metals_availability_full_when_no_demand() -> None:
    """With zero demand and full NR, availability should be 1.0."""
    result = _compute(nr=1e12, tech_metals_demand=0.0)
    assert result["tech_metals_availability"].magnitude == 1.0


def test_tech_metals_availability_in_declares_reads() -> None:
    """resources.py must declare that it reads tech_metals_demand."""
    sector = ResourcesSector()
    assert "tech_metals_demand" in sector.declares_reads()


def test_tech_metals_availability_in_declares_writes() -> None:
    sector = ResourcesSector()
    assert "tech_metals_availability" in sector.declares_writes()


def test_high_demand_reduces_availability() -> None:
    """High tech_metals_demand must reduce tech_metals_availability."""
    r_low = _compute(tech_metals_demand=0.0)
    r_high = _compute(tech_metals_demand=5e8)
    assert r_high["tech_metals_availability"].magnitude < r_low["tech_metals_availability"].magnitude, (
        f"High demand avail={r_high['tech_metals_availability'].magnitude:.4f} should be less than "
        f"low demand avail={r_low['tech_metals_availability'].magnitude:.4f}"
    )


def test_availability_bounded_0_to_1() -> None:
    """tech_metals_availability must always be in [0, 1]."""
    for demand in [0.0, 1e8, 1e9, 1e12]:
        result = _compute(tech_metals_demand=demand)
        avail = result["tech_metals_availability"].magnitude
        assert 0.0 <= avail <= 1.0, f"avail={avail} out of [0,1] at demand={demand}"
