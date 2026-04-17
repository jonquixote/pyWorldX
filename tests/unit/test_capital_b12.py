"""Task B12: capital.py must read trapped_capital and refund it to IC investment.

energy_technology.py emits trapped_capital: investment that was allocated but
couldn't be deployed due to metals scarcity. This stranded capital should
return to the productive capital pool (d_IC += trapped_capital).
"""
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


def test_trapped_capital_in_declares_reads() -> None:
    sector = CapitalSector()
    assert "trapped_capital" in sector.declares_reads()


def test_trapped_capital_refund_increases_d_IC() -> None:
    """Positive trapped_capital must increase d_IC compared to zero."""
    ctx = make_ctx()
    fs = CapitalSector()

    shared_no_trap = base_shared()
    shared_no_trap["trapped_capital"] = Quantity(0.0, "capital_units")
    shared_no_trap["energy_supply_factor"] = Quantity(1.0, "dimensionless")
    shared_no_trap["financial_resilience"] = Quantity(1.0, "dimensionless")

    shared_with_trap = base_shared()
    shared_with_trap["trapped_capital"] = Quantity(2e9, "capital_units")
    shared_with_trap["energy_supply_factor"] = Quantity(1.0, "dimensionless")
    shared_with_trap["financial_resilience"] = Quantity(1.0, "dimensionless")

    r_no = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_no_trap, ctx=ctx)
    r_with = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_with_trap, ctx=ctx)

    assert r_with["d_IC"].magnitude > r_no["d_IC"].magnitude, (
        f"d_IC with refund={r_with['d_IC'].magnitude:.4g} should exceed "
        f"without={r_no['d_IC'].magnitude:.4g}"
    )


def test_trapped_capital_refund_is_exact() -> None:
    """Refund should add trapped_capital exactly to d_IC."""
    ctx = make_ctx()
    fs = CapitalSector()

    trap_amount = 3e9

    shared_no = base_shared()
    shared_no["trapped_capital"] = Quantity(0.0, "capital_units")
    shared_no["energy_supply_factor"] = Quantity(1.0, "dimensionless")
    shared_no["financial_resilience"] = Quantity(1.0, "dimensionless")

    shared_yes = base_shared()
    shared_yes["trapped_capital"] = Quantity(trap_amount, "capital_units")
    shared_yes["energy_supply_factor"] = Quantity(1.0, "dimensionless")
    shared_yes["financial_resilience"] = Quantity(1.0, "dimensionless")

    r_no = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_no, ctx=ctx)
    r_yes = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_yes, ctx=ctx)

    diff = r_yes["d_IC"].magnitude - r_no["d_IC"].magnitude
    assert abs(diff - trap_amount) < trap_amount * 0.01, (
        f"Expected refund of {trap_amount:.4g}, got diff={diff:.4g}"
    )
