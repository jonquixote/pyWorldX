"""Task B2: human_capital.py must emit education_tnds for TNDS aggregation."""
from __future__ import annotations

from pyworldx.sectors.human_capital import HumanCapitalSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _compute(pop: float = 7.8e9, sopc: float = 87.0) -> dict:
    sector = HumanCapitalSector()
    ctx = make_ctx()
    stocks = {"H": Quantity(0.7, "dimensionless")}
    shared = base_shared()
    shared["POP"] = Quantity(pop, "persons")
    shared["service_output_per_capita"] = Quantity(sopc, "service_output_units")
    return sector.compute(t=100.0, stocks=stocks, inputs=shared, ctx=ctx)


def test_education_tnds_in_output() -> None:
    """compute() must return education_tnds key."""
    result = _compute()
    assert "education_tnds" in result, f"education_tnds missing; keys={list(result)}"
    assert isinstance(result["education_tnds"], Quantity)


def test_education_tnds_positive() -> None:
    """education_tnds must be strictly positive for non-zero pop and sopc."""
    result = _compute()
    assert result["education_tnds"].magnitude > 0.0


def test_education_tnds_scales_with_pop() -> None:
    """Doubling population must approximately double education_tnds."""
    r1 = _compute(pop=1e9)
    r2 = _compute(pop=2e9)
    ratio = r2["education_tnds"].magnitude / r1["education_tnds"].magnitude
    assert 1.8 < ratio < 2.2, f"Expected ~2x pop scaling, got {ratio:.3f}"


def test_education_tnds_in_declares_writes() -> None:
    """education_tnds must appear in declares_writes()."""
    sector = HumanCapitalSector()
    assert "education_tnds" in sector.declares_writes()
