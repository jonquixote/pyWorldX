"""Task B3: welfare.py must emit damages_tnds for TNDS aggregation."""
from __future__ import annotations

from pyworldx.sectors.welfare import WelfareSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _compute(pi: float = 2.0, io: float = 1e11, pop: float = 7.8e9) -> dict:
    sector = WelfareSector()
    ctx = make_ctx()
    shared = base_shared()
    shared["pollution_index"] = Quantity(pi, "dimensionless")
    shared["industrial_output"] = Quantity(io, "industrial_output_units")
    shared["POP"] = Quantity(pop, "persons")
    return sector.compute(t=100.0, stocks={}, inputs=shared, ctx=ctx)


def test_damages_tnds_in_output() -> None:
    result = _compute()
    assert "damages_tnds" in result, f"damages_tnds missing; keys={list(result)}"
    assert isinstance(result["damages_tnds"], Quantity)


def test_damages_tnds_positive_when_polluted() -> None:
    result = _compute(pi=5.0)
    assert result["damages_tnds"].magnitude > 0.0


def test_damages_tnds_zero_when_no_pollution() -> None:
    """With zero pollution index there should be no pollution damages."""
    result = _compute(pi=0.0)
    assert result["damages_tnds"].magnitude == 0.0


def test_damages_tnds_scales_with_pollution() -> None:
    """Higher pollution → higher damages."""
    r_low = _compute(pi=1.0)
    r_high = _compute(pi=4.0)
    assert r_high["damages_tnds"].magnitude > r_low["damages_tnds"].magnitude


def test_damages_tnds_in_declares_writes() -> None:
    sector = WelfareSector()
    assert "damages_tnds" in sector.declares_writes()
