"""Task B13: population.py must read toxin multipliers from pollution_toxins.py."""
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


def test_toxin_multipliers_in_declares_reads() -> None:
    sector = PopulationSector()
    reads = sector.declares_reads()
    assert "toxin_health_multiplier" in reads
    assert "toxin_fertility_multiplier" in reads


def test_low_toxin_health_mult_reduces_life_expectancy() -> None:
    """toxin_health_multiplier < 1 must reduce life_expectancy."""
    ctx = make_ctx()
    pop = PopulationSector()

    s_clean = base_shared()
    s_clean["toxin_health_multiplier"] = Quantity(1.0, "dimensionless")
    s_clean["toxin_fertility_multiplier"] = Quantity(1.0, "dimensionless")

    s_toxic = base_shared()
    s_toxic["toxin_health_multiplier"] = Quantity(0.7, "dimensionless")
    s_toxic["toxin_fertility_multiplier"] = Quantity(1.0, "dimensionless")

    r_clean = pop.compute(t=0.0, stocks=_stocks(), inputs=s_clean, ctx=ctx)
    r_toxic = pop.compute(t=0.0, stocks=_stocks(), inputs=s_toxic, ctx=ctx)

    assert r_toxic["life_expectancy"].magnitude < r_clean["life_expectancy"].magnitude, (
        f"LE with toxins={r_toxic['life_expectancy'].magnitude:.2f} should be less than "
        f"clean={r_clean['life_expectancy'].magnitude:.2f}"
    )


def test_low_toxin_fertility_mult_reduces_birth_rate() -> None:
    """toxin_fertility_multiplier < 1 must reduce birth_rate."""
    ctx = make_ctx()
    pop = PopulationSector()

    s_clean = base_shared()
    s_clean["toxin_health_multiplier"] = Quantity(1.0, "dimensionless")
    s_clean["toxin_fertility_multiplier"] = Quantity(1.0, "dimensionless")

    s_toxic = base_shared()
    s_toxic["toxin_health_multiplier"] = Quantity(1.0, "dimensionless")
    s_toxic["toxin_fertility_multiplier"] = Quantity(0.6, "dimensionless")

    r_clean = pop.compute(t=0.0, stocks=_stocks(), inputs=s_clean, ctx=ctx)
    r_toxic = pop.compute(t=0.0, stocks=_stocks(), inputs=s_toxic, ctx=ctx)

    assert r_toxic["birth_rate"].magnitude < r_clean["birth_rate"].magnitude, (
        f"Birth rate with toxins={r_toxic['birth_rate'].magnitude:.4g} should be less than "
        f"clean={r_clean['birth_rate'].magnitude:.4g}"
    )
