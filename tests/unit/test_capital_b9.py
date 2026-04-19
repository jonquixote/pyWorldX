"""Task B9: capital.py must read financial_resilience and gate investment."""
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


def test_financial_resilience_in_declares_reads() -> None:
    sector = CapitalSector()
    assert "financial_resilience" in sector.declares_reads()


def test_low_financial_resilience_reduces_investment() -> None:
    """financial_resilience < 1.0 must reduce IC investment."""
    ctx = make_ctx()
    fs = CapitalSector()

    shared_healthy = base_shared()
    shared_healthy["financial_resilience"] = Quantity(1.0, "dimensionless")
    shared_healthy["energy_supply_factor"] = Quantity(1.0, "dimensionless")

    shared_stressed = base_shared()
    shared_stressed["financial_resilience"] = Quantity(0.3, "dimensionless")
    shared_stressed["energy_supply_factor"] = Quantity(1.0, "dimensionless")

    r_healthy = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_healthy, ctx=ctx)
    r_stressed = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_stressed, ctx=ctx)

    assert r_stressed["d_IC"].magnitude < r_healthy["d_IC"].magnitude, (
        f"Stressed dIC={r_stressed['d_IC'].magnitude:.4g} should be less than "
        f"healthy dIC={r_healthy['d_IC'].magnitude:.4g}"
    )


def test_full_financial_resilience_unaffected() -> None:
    """financial_resilience=1.0 gives same result as missing key (default=1.0)."""
    ctx = make_ctx()
    fs = CapitalSector()

    shared_default = base_shared()
    shared_explicit = base_shared()
    shared_explicit["financial_resilience"] = Quantity(1.0, "dimensionless")

    r_default = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_default, ctx=ctx)
    r_explicit = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_explicit, ctx=ctx)

    assert abs(r_default["d_IC"].magnitude - r_explicit["d_IC"].magnitude) < 1.0
