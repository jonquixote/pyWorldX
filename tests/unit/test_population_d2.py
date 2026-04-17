"""Task D2: population.py must read disease_death_rate (no double-count)."""
from __future__ import annotations

from pyworldx.sectors.population import PopulationSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _stocks(pop: float = 1.65e9) -> dict:
    return {
        "P1": Quantity(pop * 0.3, "persons"),
        "P2": Quantity(pop * 0.25, "persons"),
        "P3": Quantity(pop * 0.2, "persons"),
        "P4": Quantity(pop * 0.25, "persons"),
        "POP": Quantity(pop, "persons"),
        "PLE": Quantity(30.0, "years"),
        "EHSPC": Quantity(30.0, "dollars_per_person"),
        "AIOPC": Quantity(40.3, "industrial_output_units"),
        "DIOPC": Quantity(40.3, "industrial_output_units"),
        "FCFPC": Quantity(0.0, "dimensionless"),
    }


def test_disease_death_rate_in_declares_reads() -> None:
    pop = PopulationSector()
    assert "disease_death_rate" in pop.declares_reads(), (
        "population must read disease_death_rate from seir"
    )


def test_nonzero_disease_death_rate_increases_deaths() -> None:
    """Extra disease deaths must increase total mortality in population."""
    ctx = make_ctx()
    pop = PopulationSector()
    stocks = _stocks()

    s_no_disease = base_shared()
    s_no_disease["disease_death_rate"] = Quantity(0.0, "per_year")

    s_epidemic = base_shared()
    s_epidemic["disease_death_rate"] = Quantity(0.005, "per_year")

    r_no_disease = pop.compute(t=0.0, stocks=stocks, inputs=s_no_disease, ctx=ctx)
    r_epidemic = pop.compute(t=0.0, stocks=stocks, inputs=s_epidemic, ctx=ctx)

    assert r_epidemic["death_rate"].magnitude > r_no_disease["death_rate"].magnitude, (
        f"Epidemic deaths={r_epidemic['death_rate'].magnitude:.2e} must exceed "
        f"baseline deaths={r_no_disease['death_rate'].magnitude:.2e}"
    )


def test_zero_disease_death_rate_unchanged_from_baseline() -> None:
    """With disease_death_rate=0, output must match no-disease baseline."""
    ctx = make_ctx()
    pop = PopulationSector()
    stocks = _stocks()

    s_base = base_shared()
    s_zero = base_shared()
    s_zero["disease_death_rate"] = Quantity(0.0, "per_year")

    r_base = pop.compute(t=0.0, stocks=stocks, inputs=s_base, ctx=ctx)
    r_zero = pop.compute(t=0.0, stocks=stocks, inputs=s_zero, ctx=ctx)

    assert r_base["death_rate"].magnitude == r_zero["death_rate"].magnitude, (
        f"Zero disease rate must not change deaths: "
        f"base={r_base['death_rate'].magnitude}, zero={r_zero['death_rate'].magnitude}"
    )
