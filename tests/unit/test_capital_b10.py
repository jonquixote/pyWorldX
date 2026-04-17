"""Task B10: capital.py must deduct energy sector investments to conserve IO.

Energy sectors (fossil, technology, sustainable) draw from industrial_output
for their investments. capital.py must subtract these from io_for_capital
before computing IC/SC investments, preventing double-counting.
"""
from __future__ import annotations

from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.energy_fossil import EnergyFossilSector
from pyworldx.sectors.energy_technology import EnergyTechnologySector
from pyworldx.sectors.energy_sustainable import EnergySustainableSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _stocks() -> dict:
    return {
        "IC": Quantity(2.1e11, "capital_units"),
        "SC": Quantity(1.44e11, "capital_units"),
        "LUFD": Quantity(1.0, "dimensionless"),
        "IOPCD": Quantity(40.3, "industrial_output_units"),
    }


def test_energy_sectors_emit_investment_variables() -> None:
    """Each energy sector must emit a *_sector_investment key."""
    ctx = make_ctx()
    shared = base_shared()

    fossil_stocks = {"fossil_capital": Quantity(5e10, "capital_units")}
    tech_stocks = {"technology_capital": Quantity(1e10, "capital_units")}
    sust_stocks = {"sustainable_capital": Quantity(5e9, "capital_units")}

    rf = EnergyFossilSector().compute(t=0.0, stocks=fossil_stocks, inputs=shared, ctx=ctx)
    rt = EnergyTechnologySector().compute(t=0.0, stocks=tech_stocks, inputs=shared, ctx=ctx)
    rs = EnergySustainableSector().compute(t=0.0, stocks=sust_stocks, inputs=shared, ctx=ctx)

    assert "fossil_sector_investment" in rf, f"fossil sector keys: {list(rf)}"
    assert "tech_sector_investment" in rt, f"tech sector keys: {list(rt)}"
    assert "sust_sector_investment" in rs, f"sust sector keys: {list(rs)}"


def test_capital_reads_energy_investments() -> None:
    """capital.py must declare reads for all three energy investment vars."""
    sector = CapitalSector()
    reads = sector.declares_reads()
    assert "fossil_sector_investment" in reads
    assert "tech_sector_investment" in reads
    assert "sust_sector_investment" in reads


def test_energy_investments_reduce_capital_investment() -> None:
    """Non-zero energy sector investments must reduce IC investment."""
    ctx = make_ctx()
    fs = CapitalSector()

    shared_no_energy = base_shared()
    shared_no_energy["fossil_sector_investment"] = Quantity(0.0, "capital_units")
    shared_no_energy["tech_sector_investment"] = Quantity(0.0, "capital_units")
    shared_no_energy["sust_sector_investment"] = Quantity(0.0, "capital_units")
    shared_no_energy["energy_supply_factor"] = Quantity(1.0, "dimensionless")
    shared_no_energy["financial_resilience"] = Quantity(1.0, "dimensionless")

    shared_with_energy = base_shared()
    shared_with_energy["fossil_sector_investment"] = Quantity(5e9, "capital_units")
    shared_with_energy["tech_sector_investment"] = Quantity(4e9, "capital_units")
    shared_with_energy["sust_sector_investment"] = Quantity(3e9, "capital_units")
    shared_with_energy["energy_supply_factor"] = Quantity(1.0, "dimensionless")
    shared_with_energy["financial_resilience"] = Quantity(1.0, "dimensionless")

    r_no = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_no_energy, ctx=ctx)
    r_with = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_with_energy, ctx=ctx)

    assert r_with["d_IC"].magnitude < r_no["d_IC"].magnitude, (
        f"d_IC with energy draw={r_with['d_IC'].magnitude:.4g} should be less than "
        f"without={r_no['d_IC'].magnitude:.4g}"
    )
