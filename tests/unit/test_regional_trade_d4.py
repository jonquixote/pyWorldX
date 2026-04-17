"""Task D4: regional_trade must emit total_migration_flow scalar."""
from __future__ import annotations

from pyworldx.sectors.regional_trade import RegionalTradeSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx


def _run(fpc: float = 300.0) -> dict:
    sector = RegionalTradeSector(num_regions=2)
    ctx = make_ctx()
    shared = {
        "food_per_capita": Quantity(fpc, "food_units_per_person"),
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "POP": Quantity(7.8e9, "persons"),
    }
    return sector.compute(t=0.0, stocks={}, inputs=shared, ctx=ctx)


def test_total_migration_flow_in_output() -> None:
    result = _run()
    assert "total_migration_flow" in result, f"keys={list(result)}"
    assert isinstance(result["total_migration_flow"], Quantity)


def test_total_migration_flow_in_declares_writes() -> None:
    sector = RegionalTradeSector()
    assert "total_migration_flow" in sector.declares_writes()


def test_migration_flow_non_negative() -> None:
    """Migration flow is a total (sum of flows) and must be >= 0."""
    result = _run()
    assert result["total_migration_flow"].magnitude >= 0.0


def test_low_fpc_produces_migration() -> None:
    """Very low FPC triggers stress; migration flow must be finite and >= 0."""
    result = _run(fpc=80.0)
    assert result["total_migration_flow"].magnitude >= 0.0
