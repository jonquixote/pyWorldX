"""Task D1: SEIRModule must emit disease_death_rate."""
from __future__ import annotations

from pyworldx.sectors.seir import SEIRModule
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx


def test_seir_exports_disease_death_rate() -> None:
    seir = SEIRModule(initial_infected_fraction=0.05)
    ctx = make_ctx()
    shared = {
        "POP": Quantity(7.8e9, "people"),
        "temperature_anomaly": Quantity(1.0, "deg_C_anomaly"),
    }
    out = seir.compute(2020.0, seir.init_stocks(ctx), shared, ctx)
    assert "disease_death_rate" in out, f"keys={list(out)}"
    ddr = out["disease_death_rate"].magnitude
    assert 0.0 < ddr < 0.02, f"ddr={ddr} out of sanity bounds [0, 0.02]"


def test_disease_death_rate_in_declares_writes() -> None:
    seir = SEIRModule()
    assert "disease_death_rate" in seir.declares_writes()


def test_zero_infected_gives_zero_disease_death_rate() -> None:
    """With no infected, excess disease deaths must be zero."""
    seir = SEIRModule(initial_infected_fraction=0.0)
    ctx = make_ctx()
    out = seir.compute(2020.0, seir.init_stocks(ctx), {}, ctx)
    assert out["disease_death_rate"].magnitude == 0.0, (
        f"Expected 0 disease deaths, got {out['disease_death_rate'].magnitude}"
    )


def test_higher_infected_fraction_raises_disease_death_rate() -> None:
    """More infected → more disease deaths."""
    ctx = make_ctx()
    seir_low = SEIRModule(initial_infected_fraction=0.001)
    seir_high = SEIRModule(initial_infected_fraction=0.10)
    out_low = seir_low.compute(2020.0, seir_low.init_stocks(ctx), {}, ctx)
    out_high = seir_high.compute(2020.0, seir_high.init_stocks(ctx), {}, ctx)
    assert out_high["disease_death_rate"].magnitude > out_low["disease_death_rate"].magnitude, (
        f"high infected should produce higher disease_death_rate: "
        f"low={out_low['disease_death_rate'].magnitude:.2e}, "
        f"high={out_high['disease_death_rate'].magnitude:.2e}"
    )
