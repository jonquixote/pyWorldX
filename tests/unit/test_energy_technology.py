"""Unit tests for EnergyTechnologySector (100% line+branch coverage)."""
from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.energy_technology import EnergyTechnologySector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _inputs(metals: float = 1.0, io: float = 7.9e11, supply_mult: float = 1.0) -> dict[str, Quantity]:
    return {
        "tech_metals_availability": Quantity(metals, "dimensionless"),
        "industrial_output": Quantity(io, "industrial_output_units"),
        "supply_multiplier_technology": Quantity(supply_mult, "dimensionless"),
    }


class TestEnergyTechnologySector:
    def test_init_stocks(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        assert "technology_capital" in stocks
        assert stocks["technology_capital"].magnitude == 1.0e10

    def test_compute_basic(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert "technology_output" in out
        assert "technology_eroi" in out
        assert "energy_demand_technology" in out
        assert "trapped_capital" in out
        assert "tech_metals_demand" in out

    def test_eroi_at_full_metals(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(metals=1.0), ctx)
        assert abs(out["technology_eroi"].magnitude - 15.0) < 1e-6

    def test_eroi_at_zero_metals(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(metals=0.0), ctx)
        assert abs(out["technology_eroi"].magnitude - 3.0) < 1e-6

    def test_eroi_interpolates_with_metals(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(metals=1.0), ctx)
        out_half = s.compute(0.0, stocks, _inputs(metals=0.5), ctx)
        out_none = s.compute(0.0, stocks, _inputs(metals=0.0), ctx)
        assert out_full["technology_eroi"].magnitude > out_half["technology_eroi"].magnitude > out_none["technology_eroi"].magnitude

    def test_output_zero_at_no_metals(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(metals=0.0), ctx)
        assert out["technology_output"].magnitude == 0.0

    def test_trapped_capital_zero_at_full_metals(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(metals=1.0), ctx)
        assert abs(out["trapped_capital"].magnitude) < 1e-6

    def test_trapped_capital_positive_at_low_metals(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(metals=0.3), ctx)
        assert out["trapped_capital"].magnitude > 0.0

    def test_supply_multiplier_reduces_output(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(metals=1.0, supply_mult=1.0), ctx)
        out_half = s.compute(0.0, stocks, _inputs(metals=1.0, supply_mult=0.5), ctx)
        assert out_full["technology_output"].magnitude > out_half["technology_output"].magnitude

    def test_tech_metals_demand_proportional_to_capital(self) -> None:
        s_lo = EnergyTechnologySector(initial_capital=1.0e9)
        s_hi = EnergyTechnologySector(initial_capital=1.0e11)
        ctx = _ctx()
        out_lo = s_lo.compute(0.0, s_lo.init_stocks(ctx), _inputs(), ctx)
        out_hi = s_hi.compute(0.0, s_hi.init_stocks(ctx), _inputs(), ctx)
        assert out_hi["tech_metals_demand"].magnitude > out_lo["tech_metals_demand"].magnitude

    def test_all_outputs_are_quantities(self) -> None:
        s = EnergyTechnologySector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        for k, v in out.items():
            assert isinstance(v, Quantity), f"{k} is not a Quantity"

    def test_declares_reads(self) -> None:
        s = EnergyTechnologySector()
        reads = s.declares_reads()
        assert "tech_metals_availability" in reads
        assert "supply_multiplier_technology" in reads

    def test_declares_writes(self) -> None:
        s = EnergyTechnologySector()
        writes = s.declares_writes()
        assert "technology_output" in writes
        assert "trapped_capital" in writes
        assert "technology_capital" in writes
