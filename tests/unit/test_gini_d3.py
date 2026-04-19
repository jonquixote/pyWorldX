"""Task D3: Gini stratified mortality (population) and allocation (capital)."""
from __future__ import annotations

from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _pop_stocks(pop: float = 1.65e9) -> dict:
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


# ── Population Gini tests ─────────────────────────────────────────────────

def test_population_reads_gini_mortality_multipliers() -> None:
    """population must declare reads for gini stratified mortality inputs."""
    pop = PopulationSector()
    reads = pop.declares_reads()
    assert "gini_mortality_mult" in reads, (
        f"gini_mortality_mult missing from declares_reads: {reads}"
    )


def test_gini_mortality_mult_below_1_increases_deaths() -> None:
    """gini_mortality_mult < 1 (inequality worsens health) must raise death_rate."""
    ctx = make_ctx()
    pop = PopulationSector()
    stocks = _pop_stocks()

    s_equal = base_shared()
    s_equal["gini_mortality_mult"] = Quantity(1.0, "dimensionless")

    s_unequal = base_shared()
    s_unequal["gini_mortality_mult"] = Quantity(0.8, "dimensionless")

    r_eq = pop.compute(t=0.0, stocks=stocks, inputs=s_equal, ctx=ctx)
    r_uneq = pop.compute(t=0.0, stocks=stocks, inputs=s_unequal, ctx=ctx)

    assert r_uneq["death_rate"].magnitude > r_eq["death_rate"].magnitude, (
        f"Unequal death_rate={r_uneq['death_rate'].magnitude:.2e} must exceed "
        f"equal death_rate={r_eq['death_rate'].magnitude:.2e}"
    )


def test_gini_mortality_mult_1_matches_baseline() -> None:
    """gini_mortality_mult=1.0 must not change results vs absent."""
    ctx = make_ctx()
    pop = PopulationSector()
    stocks = _pop_stocks()

    s_base = base_shared()
    s_one = base_shared()
    s_one["gini_mortality_mult"] = Quantity(1.0, "dimensionless")

    r_base = pop.compute(t=0.0, stocks=stocks, inputs=s_base, ctx=ctx)
    r_one = pop.compute(t=0.0, stocks=stocks, inputs=s_one, ctx=ctx)

    assert r_base["death_rate"].magnitude == r_one["death_rate"].magnitude


# ── Capital Gini tests ────────────────────────────────────────────────────

def test_capital_reads_resource_share_bot90() -> None:
    """capital must declare read for resource_share_bot90."""
    cap = CapitalSector()
    assert "resource_share_bot90" in cap.declares_reads(), (
        "capital must read resource_share_bot90"
    )


def test_high_inequality_reduces_industrial_output() -> None:
    """oligarchic resource_share_bot90=0.30 must give lower IO than egalitarian 0.70."""
    ctx = make_ctx()
    cap = CapitalSector()
    stocks = cap.init_stocks(ctx)

    s_egalitarian = base_shared()
    s_egalitarian["resource_share_bot90"] = Quantity(0.70, "dimensionless")

    s_oligarchic = base_shared()
    s_oligarchic["resource_share_bot90"] = Quantity(0.30, "dimensionless")

    r_eq = cap.compute(t=0.0, stocks=stocks, inputs=s_egalitarian, ctx=ctx)
    r_uneq = cap.compute(t=0.0, stocks=stocks, inputs=s_oligarchic, ctx=ctx)

    assert r_uneq["industrial_output"].magnitude < r_eq["industrial_output"].magnitude, (
        f"Oligarchic IO={r_uneq['industrial_output'].magnitude:.3e} must be < "
        f"egalitarian IO={r_eq['industrial_output'].magnitude:.3e}"
    )


def test_neutral_resource_share_unchanged_from_baseline() -> None:
    """resource_share_bot90=0.50 (neutral) must match absent (default) output."""
    ctx = make_ctx()
    cap = CapitalSector()
    stocks = cap.init_stocks(ctx)

    s_base = base_shared()
    s_neutral = base_shared()
    s_neutral["resource_share_bot90"] = Quantity(0.50, "dimensionless")

    r_base = cap.compute(t=0.0, stocks=stocks, inputs=s_base, ctx=ctx)
    r_neutral = cap.compute(t=0.0, stocks=stocks, inputs=s_neutral, ctx=ctx)

    assert abs(r_base["industrial_output"].magnitude - r_neutral["industrial_output"].magnitude) < 1.0, (
        f"Neutral share should not change IO: "
        f"base={r_base['industrial_output'].magnitude:.3e}, "
        f"neutral={r_neutral['industrial_output'].magnitude:.3e}"
    )
