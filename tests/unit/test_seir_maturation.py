from __future__ import annotations
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.seir import SEIRModule


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _pop_inputs() -> dict[str, Quantity]:
    return {
        "food_per_capita": Quantity(400.0, "food_units_per_person"),
        "industrial_output": Quantity(7.9e10, "industrial_output_units"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "service_output_per_capita": Quantity(87.0, "service_units_per_capita"),
        "supply_multiplier_population": Quantity(1.0, "dimensionless"),
        "labor_force_multiplier": Quantity(1.0, "dimensionless"),
        "toxin_health_multiplier": Quantity(1.0, "dimensionless"),
        "toxin_fertility_multiplier": Quantity(1.0, "dimensionless"),
        "disease_death_rate": Quantity(0.0, "per_year"),
        "gini_mortality_mult": Quantity(1.0, "dimensionless"),
        "total_migration_flow": Quantity(0.0, "persons"),
        "energy_supply_factor": Quantity(1.0, "dimensionless"),
    }


def test_population_exports_mat1_mat2_mat3() -> None:
    """PopulationSector.compute() must include mat1, mat2, mat3 in its output."""
    s = PopulationSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    out = s.compute(0.0, stocks, _pop_inputs(), ctx)
    for key in ("mat1", "mat2", "mat3"):
        assert key in out, f"PopulationSector must export {key}"
        assert out[key].magnitude > 0.0, f"{key} must be positive at t=0 (population is aging)"


def test_population_declares_writes_mat_flows() -> None:
    """PopulationSector.declares_writes() must include mat1, mat2, mat3."""
    s = PopulationSector()
    for key in ("mat1", "mat2", "mat3"):
        assert key in s.declares_writes(), f"declares_writes() must include {key}"


def test_seir_declares_reads_mat_flows() -> None:
    """SEIRModule.declares_reads() must include mat1, mat2, mat3."""
    s = SEIRModule()
    for key in ("mat1", "mat2", "mat3"):
        assert key in s.declares_reads(), f"declares_reads() must include {key}"


def _make_consistent_stocks(
    p1: float, p2: float, p3: float, p4: float, infected_frac: float = 0.001
) -> dict[str, Quantity]:
    """Create SEIR stocks consistent with given population cohort sizes."""
    stocks: dict[str, Quantity] = {}
    for label, pop in zip(
        ["C1_0_14", "C2_15_44", "C3_45_64", "C4_65_plus"], [p1, p2, p3, p4]
    ):
        stocks[f"S_{label}"] = Quantity(pop * (1.0 - infected_frac), "persons")
        stocks[f"E_{label}"] = Quantity(0.0, "persons")
        stocks[f"I_{label}"] = Quantity(pop * infected_frac, "persons")
        stocks[f"R_{label}"] = Quantity(0.0, "persons")
    return stocks


def test_seir_aging_reduces_young_cohort_susceptibles() -> None:
    """With positive mat flows, dS for C1 (0-14) must be lower than without maturation."""
    s = SEIRModule()
    ctx = _ctx()
    # Use consistent stocks: C1=400M, C2=700M, C3=300M, C4=250M
    stocks = _make_consistent_stocks(0.4e9, 0.7e9, 0.3e9, 0.25e9)
    base = {
        "POP": Quantity(1.65e9, "persons"),
        "P1": Quantity(0.4e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "P4": Quantity(0.25e9, "persons"),
        "birth_rate": Quantity(0.03, "per_year"),
        "death_rate": Quantity(0.01, "per_year"),
    }
    inputs_no_aging = {**base}
    inputs_with_aging = {
        **base,
        "mat1": Quantity(2.0e7, "persons_per_year"),
        "mat2": Quantity(1.5e7, "persons_per_year"),
        "mat3": Quantity(1.0e7, "persons_per_year"),
    }
    out_no = s.compute(0.0, stocks, inputs_no_aging, ctx)
    out_with = s.compute(0.0, stocks, inputs_with_aging, ctx)
    assert out_with["d_S_C1_0_14"].magnitude < out_no["d_S_C1_0_14"].magnitude, (
        "Aging must remove susceptibles from C1: dS_C1_0_14 with aging must be < without"
    )


def test_seir_aging_increases_adult_cohort_susceptibles() -> None:
    """Aging must add susceptibles to C2 (15-44) from C1 outflow."""
    s = SEIRModule()
    ctx = _ctx()
    # Use consistent stocks: C1=400M, C2=700M, C3=300M, C4=250M
    stocks = _make_consistent_stocks(0.4e9, 0.7e9, 0.3e9, 0.25e9)
    base = {
        "POP": Quantity(1.65e9, "persons"),
        "P1": Quantity(0.4e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "P4": Quantity(0.25e9, "persons"),
        "birth_rate": Quantity(0.03, "per_year"),
        "death_rate": Quantity(0.01, "per_year"),
    }
    inputs_no_aging = {**base}
    inputs_with_aging = {
        **base,
        "mat1": Quantity(2.0e7, "persons_per_year"),
        "mat2": Quantity(1.5e7, "persons_per_year"),
        "mat3": Quantity(1.0e7, "persons_per_year"),
    }
    out_no = s.compute(0.0, stocks, inputs_no_aging, ctx)
    out_with = s.compute(0.0, stocks, inputs_with_aging, ctx)
    assert out_with["d_S_C2_15_44"].magnitude > out_no["d_S_C2_15_44"].magnitude, (
        "Aging must add susceptibles to C2: dS_C2_15_44 with aging must be > without"
    )


def test_seir_no_crash_with_zero_mat_flows() -> None:
    """SEIR must not crash when mat1/mat2/mat3 are absent (defaults to 0)."""
    s = SEIRModule()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    inputs = {
        "POP": Quantity(1.65e9, "persons"),
        "P1": Quantity(0.4e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "P4": Quantity(0.25e9, "persons"),
        "birth_rate": Quantity(5.0e7, "persons_per_year"),
        "death_rate": Quantity(0.01, "per_year"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    for k, v in out.items():
        assert v.magnitude == v.magnitude, f"NaN in {k}"
