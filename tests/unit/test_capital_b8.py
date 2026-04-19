"""Task B8: capital.py must read energy_supply_factor and gate investment."""
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


def test_energy_supply_factor_in_declares_reads() -> None:
    sector = CapitalSector()
    assert "energy_supply_factor" in sector.declares_reads()


def test_energy_constrained_reduces_investment() -> None:
    """energy_supply_factor < 1.0 must reduce IC investment vs unconstrained."""
    ctx = make_ctx()
    fs = CapitalSector()

    shared_full = base_shared()
    shared_full["energy_supply_factor"] = Quantity(1.0, "dimensionless")

    shared_constrained = base_shared()
    shared_constrained["energy_supply_factor"] = Quantity(0.5, "dimensionless")

    r_full = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_full, ctx=ctx)
    r_constrained = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_constrained, ctx=ctx)

    dIC_full = r_full["d_IC"].magnitude
    dIC_constrained = r_constrained["d_IC"].magnitude

    assert dIC_constrained < dIC_full, (
        f"Energy-constrained dIC={dIC_constrained:.4g} should be less than "
        f"unconstrained dIC={dIC_full:.4g}"
    )


def test_full_energy_supply_unaffected() -> None:
    """energy_supply_factor=1.0 must give the same result as missing key (default=1.0)."""
    ctx = make_ctx()
    fs = CapitalSector()

    shared_default = base_shared()
    # No energy_supply_factor key → default 1.0
    shared_explicit = base_shared()
    shared_explicit["energy_supply_factor"] = Quantity(1.0, "dimensionless")

    r_default = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_default, ctx=ctx)
    r_explicit = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_explicit, ctx=ctx)

    assert abs(r_default["d_IC"].magnitude - r_explicit["d_IC"].magnitude) < 1.0, (
        "ESF=1.0 should give same result as no ESF key"
    )
