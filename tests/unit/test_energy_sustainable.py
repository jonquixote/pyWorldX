"""Unit tests for EnergySustainableSector (100% line+branch coverage)."""
from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.energy_sustainable import EnergySustainableSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _inputs(io: float = 7.9e11, supply_mult: float = 1.0) -> dict[str, Quantity]:
    return {
        "industrial_output": Quantity(io, "industrial_output_units"),
        "supply_multiplier_sustainable": Quantity(supply_mult, "dimensionless"),
    }


class TestEnergySustainableSector:
    def test_init_stocks(self) -> None:
        s = EnergySustainableSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        assert "sustainable_capital" in stocks
        assert stocks["sustainable_capital"].magnitude == 2.0e10

    def test_compute_basic(self) -> None:
        s = EnergySustainableSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert "sustainable_output" in out
        assert "sustainable_eroi" in out
        assert "energy_demand_sustainable" in out
        assert "sust_sector_investment" in out

    def test_eroi_is_stable(self) -> None:
        """Sustainable EROI is fixed (not resource-depleted)."""
        s = EnergySustainableSector(eroi=12.0)
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert abs(out["sustainable_eroi"].magnitude - 12.0) < 1e-6

    def test_output_proportional_to_capital(self) -> None:
        s_lo = EnergySustainableSector(initial_capital=1.0e10)
        s_hi = EnergySustainableSector(initial_capital=4.0e10)
        ctx = _ctx()
        out_lo = s_lo.compute(0.0, s_lo.init_stocks(ctx), _inputs(), ctx)
        out_hi = s_hi.compute(0.0, s_hi.init_stocks(ctx), _inputs(), ctx)
        ratio = out_hi["sustainable_output"].magnitude / max(out_lo["sustainable_output"].magnitude, 1e-30)
        assert abs(ratio - 4.0) < 0.01

    def test_supply_multiplier_reduces_output(self) -> None:
        s = EnergySustainableSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(supply_mult=1.0), ctx)
        out_half = s.compute(0.0, stocks, _inputs(supply_mult=0.5), ctx)
        assert out_full["sustainable_output"].magnitude > out_half["sustainable_output"].magnitude

    def test_energy_demand_is_output_over_eroi(self) -> None:
        s = EnergySustainableSector(eroi=12.0)
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        expected = out["sustainable_output"].magnitude / 12.0
        assert abs(out["energy_demand_sustainable"].magnitude - expected) < 1e-6

    def test_investment_positive(self) -> None:
        s = EnergySustainableSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["sust_sector_investment"].magnitude > 0.0

    def test_all_outputs_are_quantities(self) -> None:
        s = EnergySustainableSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        for k, v in out.items():
            assert isinstance(v, Quantity), f"{k} is not a Quantity"

    def test_declares_reads(self) -> None:
        s = EnergySustainableSector()
        reads = s.declares_reads()
        assert "industrial_output" in reads
        assert "supply_multiplier_sustainable" in reads

    def test_declares_writes(self) -> None:
        s = EnergySustainableSector()
        writes = s.declares_writes()
        assert "sustainable_output" in writes
        assert "sustainable_capital" in writes
        assert "sust_sector_investment" in writes
