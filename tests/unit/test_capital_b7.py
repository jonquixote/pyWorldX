"""Task B7: capital.py must emit energy_demand_capital so CentralRegistrar can allocate."""
from __future__ import annotations

from pyworldx.sectors.capital import CapitalSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _stocks() -> dict:
    return {
        "IC": Quantity(2.1e11, "capital_units"),
        "SC": Quantity(1.44e11, "capital_units"),
        "LUFD": Quantity(1.0, "dimensionless"),
        "IOPCD": Quantity(40.3, "industrial_output_units"),
    }


def _compute(ic_scale: float = 1.0) -> dict:
    sector = CapitalSector()
    ctx = make_ctx()
    shared = base_shared()
    stocks = {
        "IC": Quantity(2.1e11 * ic_scale, "capital_units"),
        "SC": Quantity(1.44e11, "capital_units"),
        "LUFD": Quantity(1.0, "dimensionless"),
        "IOPCD": Quantity(40.3, "industrial_output_units"),
    }
    return sector.compute(t=0.0, stocks=stocks, inputs=shared, ctx=ctx)


def test_energy_demand_capital_in_output() -> None:
    result = _compute()
    assert "energy_demand_capital" in result, (
        f"energy_demand_capital missing; keys={list(result)}"
    )
    assert isinstance(result["energy_demand_capital"], Quantity)


def test_energy_demand_capital_positive() -> None:
    result = _compute(ic_scale=1.0)
    assert result["energy_demand_capital"].magnitude > 0.0


def test_energy_demand_capital_scales_with_output() -> None:
    """Larger IC must produce larger energy demand (via Cobb-Douglas IO)."""
    r1 = _compute(ic_scale=1.0)
    r2 = _compute(ic_scale=4.0)
    # IC^0.25 → 4x IC gives ~4^0.25 = sqrt(2) ≈ 1.41x IO, so energy demand > 1x
    ratio = r2["energy_demand_capital"].magnitude / r1["energy_demand_capital"].magnitude
    assert ratio > 1.1, f"Expected energy demand to grow with IC, got ratio={ratio:.3f}"


def test_energy_demand_capital_in_declares_writes() -> None:
    sector = CapitalSector()
    assert "energy_demand_capital" in sector.declares_writes()
