# tests/unit/test_capital_tech_cost.py
from __future__ import annotations
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.capital import CapitalSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _base_inputs() -> dict[str, Quantity]:
    return {
        "fcaor": Quantity(0.05, "dimensionless"),
        "POP": Quantity(1.65e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "AL": Quantity(1.4e9, "hectares"),
        "aiph": Quantity(5.0, "capital_units"),
        "food_per_capita": Quantity(400.0, "food_units_per_person"),
        "frac_io_to_agriculture": Quantity(0.15, "dimensionless"),
        "industrial_output_per_capita": Quantity(40.0, "industrial_output_units"),
        "service_output_per_capita": Quantity(87.0, "service_units_per_capita"),
        "maintenance_ratio": Quantity(1.0, "dimensionless"),
        "human_capital_multiplier": Quantity(1.0, "dimensionless"),
        "labor_force_multiplier": Quantity(1.0, "dimensionless"),
        "energy_supply_factor": Quantity(1.0, "dimensionless"),
        "financial_resilience": Quantity(1.0, "dimensionless"),
        "resource_share_bot90": Quantity(0.5, "dimensionless"),
    }


def test_tech_cost_fraction_declared_as_read() -> None:
    """Capital sector must declare tech_cost_fraction as a read."""
    assert "tech_cost_fraction" in CapitalSector().declares_reads()


def test_zero_tech_cost_fraction_unchanged() -> None:
    """tech_cost_fraction=0 must produce same d_IC as when key is absent."""
    s = CapitalSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    inputs_no_key = _base_inputs()
    inputs_zero = {**_base_inputs(), "tech_cost_fraction": Quantity(0.0, "dimensionless")}
    out_no = s.compute(0.0, stocks, inputs_no_key, ctx)
    out_zero = s.compute(0.0, stocks, inputs_zero, ctx)
    assert abs(out_no["d_IC"].magnitude - out_zero["d_IC"].magnitude) < 1.0


def test_nonzero_tech_cost_reduces_io_for_capital() -> None:
    """A 10% tech_cost_fraction reduces capital available for allocation."""
    # In a low-income economy (low IOPC_desired), fioai can be positive,
    # allowing investment. We use low IOPCD to force that.
    s = CapitalSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    # IOPCD (expected income) is very low, so iopc_ratio is high,
    # which maps to high consumption but leaves room for investment
    low_income_stocks = {**stocks, "IOPCD": Quantity(5.0, "industrial_output_units")}
    inputs = _base_inputs()

    out_zero = s.compute(0.0, low_income_stocks, {**inputs, "tech_cost_fraction": Quantity(0.0, "dimensionless")}, ctx)
    out_ten = s.compute(0.0, low_income_stocks, {**inputs, "tech_cost_fraction": Quantity(0.10, "dimensionless")}, ctx)

    # With tech_cost_fraction=0.10, more IO is devoted to R&D,
    # leaving less for capital. So d_IC should be lower (less positive or more negative).
    assert out_ten["d_IC"].magnitude <= out_zero["d_IC"].magnitude


def test_tech_cost_fraction_monotone() -> None:
    """d_IC must decrease monotonically as tech_cost_fraction increases."""
    s = CapitalSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    # Use low IOPCD to allow industry investment
    low_income_stocks = {**stocks, "IOPCD": Quantity(5.0, "industrial_output_units")}
    inputs = _base_inputs()

    fracs = [0.0, 0.05, 0.10, 0.20]
    dic_values = []
    for f in fracs:
        out = s.compute(0.0, low_income_stocks, {**inputs, "tech_cost_fraction": Quantity(f, "dimensionless")}, ctx)
        dic_values.append(out["d_IC"].magnitude)
    assert dic_values == sorted(dic_values, reverse=True), "d_IC must decrease as tech_cost_fraction increases"
