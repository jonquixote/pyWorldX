"""Task D5: population.py reads total_migration_flow as mortality stressor."""
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


def test_total_migration_flow_in_declares_reads() -> None:
    pop = PopulationSector()
    assert "total_migration_flow" in pop.declares_reads()


def test_high_migration_flow_raises_deaths() -> None:
    """Large migration stress (mass displacement) increases mortality."""
    ctx = make_ctx()
    pop = PopulationSector()
    stocks = _stocks()

    s_no_migration = base_shared()
    s_no_migration["total_migration_flow"] = Quantity(0.0, "persons_per_year")

    s_mass_displacement = base_shared()
    s_mass_displacement["total_migration_flow"] = Quantity(5e8, "persons_per_year")

    r_no = pop.compute(t=0.0, stocks=stocks, inputs=s_no_migration, ctx=ctx)
    r_mass = pop.compute(t=0.0, stocks=stocks, inputs=s_mass_displacement, ctx=ctx)

    assert r_mass["death_rate"].magnitude > r_no["death_rate"].magnitude, (
        f"Mass displacement death_rate={r_mass['death_rate'].magnitude:.2e} must exceed "
        f"no-migration death_rate={r_no['death_rate'].magnitude:.2e}"
    )


def test_zero_migration_unchanged_from_baseline() -> None:
    """total_migration_flow=0 must not change results vs absent."""
    ctx = make_ctx()
    pop = PopulationSector()
    stocks = _stocks()

    s_base = base_shared()
    s_zero = base_shared()
    s_zero["total_migration_flow"] = Quantity(0.0, "persons_per_year")

    r_base = pop.compute(t=0.0, stocks=stocks, inputs=s_base, ctx=ctx)
    r_zero = pop.compute(t=0.0, stocks=stocks, inputs=s_zero, ctx=ctx)

    assert r_base["death_rate"].magnitude == r_zero["death_rate"].magnitude
