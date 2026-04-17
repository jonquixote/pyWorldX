"""Task B11: adaptive_technology multipliers must be consumed by resources/pollution/agriculture."""
from __future__ import annotations

from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


# ── Resources wiring ────────────────────────────────────────────────────

def test_resources_reads_resource_tech_mult() -> None:
    sector = ResourcesSector()
    assert "resource_tech_mult" in sector.declares_reads()


def test_higher_resource_tech_mult_reduces_nrur() -> None:
    """resource_tech_mult > 1 means more efficient extraction → lower nrur."""
    ctx = make_ctx()
    stocks = {"NR": Quantity(1e12, "resource_units")}

    s_baseline = base_shared()
    s_baseline["resource_tech_mult"] = Quantity(1.0, "dimensionless")

    s_tech = base_shared()
    s_tech["resource_tech_mult"] = Quantity(1.5, "dimensionless")

    r_base = ResourcesSector().compute(t=0.0, stocks=stocks, inputs=s_baseline, ctx=ctx)
    r_tech = ResourcesSector().compute(t=0.0, stocks=stocks, inputs=s_tech, ctx=ctx)

    assert r_tech["nrur"].magnitude < r_base["nrur"].magnitude, (
        f"nrur with tech={r_tech['nrur'].magnitude:.4g} should be less than "
        f"baseline={r_base['nrur'].magnitude:.4g}"
    )


# ── Pollution wiring ────────────────────────────────────────────────────

def test_pollution_reads_pollution_tech_mult() -> None:
    sector = PollutionSector()
    assert "pollution_tech_mult" in sector.declares_reads()


def test_higher_pollution_tech_mult_reduces_generation() -> None:
    """pollution_tech_mult > 1 means cleaner production → lower pollution_generation."""
    ctx = make_ctx()
    stocks = {
        "PPOL": Quantity(1.36e8, "pollution_units"),
        "PPDL1": Quantity(0.0, "pollution_units"),
        "PPDL2": Quantity(0.0, "pollution_units"),
        "PPDL3": Quantity(0.0, "pollution_units"),
    }

    s_baseline = base_shared()
    s_baseline["pollution_tech_mult"] = Quantity(1.0, "dimensionless")

    s_tech = base_shared()
    s_tech["pollution_tech_mult"] = Quantity(1.5, "dimensionless")

    r_base = PollutionSector().compute(t=0.0, stocks=stocks, inputs=s_baseline, ctx=ctx)
    r_tech = PollutionSector().compute(t=0.0, stocks=stocks, inputs=s_tech, ctx=ctx)

    assert r_tech["pollution_generation"].magnitude < r_base["pollution_generation"].magnitude, (
        f"pollution_gen with tech={r_tech['pollution_generation'].magnitude:.4g} should be less "
        f"than baseline={r_base['pollution_generation'].magnitude:.4g}"
    )


# ── Agriculture wiring ──────────────────────────────────────────────────

def test_agriculture_reads_agriculture_tech_mult() -> None:
    sector = AgricultureSector()
    assert "agriculture_tech_mult" in sector.declares_reads()


def test_higher_agriculture_tech_mult_increases_yield() -> None:
    """agriculture_tech_mult > 1 means better technology → higher food production."""
    ctx = make_ctx()
    stocks = {
        "AL": Quantity(1.4e9, "hectares"),
        "LFERT": Quantity(600.0, "veg_equiv_kg_per_ha_yr"),
        "CAI": Quantity(3.325e9, "agricultural_input_units"),
    }

    s_baseline = base_shared()
    s_baseline["agriculture_tech_mult"] = Quantity(1.0, "dimensionless")

    s_tech = base_shared()
    s_tech["agriculture_tech_mult"] = Quantity(1.3, "dimensionless")

    r_base = AgricultureSector().compute(t=0.0, stocks=stocks, inputs=s_baseline, ctx=ctx)
    r_tech = AgricultureSector().compute(t=0.0, stocks=stocks, inputs=s_tech, ctx=ctx)

    assert r_tech["food"].magnitude > r_base["food"].magnitude, (
        f"food with tech={r_tech['food'].magnitude:.4g} should be greater than "
        f"baseline={r_base['food'].magnitude:.4g}"
    )
