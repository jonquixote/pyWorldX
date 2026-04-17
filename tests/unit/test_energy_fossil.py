"""Unit tests for EnergyFossilSector (100% line+branch coverage)."""
from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.energy_fossil import EnergyFossilSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _inputs(nrfr: float = 1.0, io: float = 7.9e11, supply_mult: float = 1.0) -> dict[str, Quantity]:
    return {
        "nr_fraction_remaining": Quantity(nrfr, "dimensionless"),
        "industrial_output": Quantity(io, "industrial_output_units"),
        "supply_multiplier_fossil": Quantity(supply_mult, "dimensionless"),
    }


class TestEnergyFossilSector:
    def test_init_stocks(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        assert "fossil_capital" in stocks
        assert stocks["fossil_capital"].magnitude == 1.0e11

    def test_compute_basic(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert "fossil_output" in out
        assert "fossil_eroi" in out
        assert "energy_demand_fossil" in out
        assert "fossil_sector_investment" in out

    def test_eroi_at_full_reserves(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(nrfr=1.0), ctx)
        assert abs(out["fossil_eroi"].magnitude - 30.0) < 1e-6

    def test_eroi_at_depletion(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(nrfr=0.0), ctx)
        assert abs(out["fossil_eroi"].magnitude - 2.0) < 1e-6

    def test_eroi_declines_with_depletion(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(nrfr=1.0), ctx)
        out_half = s.compute(0.0, stocks, _inputs(nrfr=0.5), ctx)
        out_dep = s.compute(0.0, stocks, _inputs(nrfr=0.0), ctx)
        assert out_full["fossil_eroi"].magnitude > out_half["fossil_eroi"].magnitude > out_dep["fossil_eroi"].magnitude

    def test_output_declines_with_depletion(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(nrfr=1.0), ctx)
        out_dep = s.compute(0.0, stocks, _inputs(nrfr=0.0), ctx)
        assert out_full["fossil_output"].magnitude > out_dep["fossil_output"].magnitude

    def test_supply_multiplier_reduces_output(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(supply_mult=1.0), ctx)
        out_half = s.compute(0.0, stocks, _inputs(supply_mult=0.5), ctx)
        assert out_full["fossil_output"].magnitude > out_half["fossil_output"].magnitude

    def test_energy_demand_is_output_over_eroi(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(nrfr=1.0), ctx)
        expected = out["fossil_output"].magnitude / out["fossil_eroi"].magnitude
        assert abs(out["energy_demand_fossil"].magnitude - expected) < 1e-6

    def test_investment_decreases_with_depletion(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_full = s.compute(0.0, stocks, _inputs(nrfr=1.0), ctx)
        out_dep = s.compute(0.0, stocks, _inputs(nrfr=0.0), ctx)
        assert out_full["fossil_sector_investment"].magnitude > out_dep["fossil_sector_investment"].magnitude

    def test_all_outputs_are_quantities(self) -> None:
        s = EnergyFossilSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        for k, v in out.items():
            assert isinstance(v, Quantity), f"{k} is not a Quantity"

    def test_declares_reads(self) -> None:
        s = EnergyFossilSector()
        reads = s.declares_reads()
        assert "nr_fraction_remaining" in reads
        assert "supply_multiplier_fossil" in reads

    def test_declares_writes(self) -> None:
        s = EnergyFossilSector()
        writes = s.declares_writes()
        assert "fossil_output" in writes
        assert "fossil_eroi" in writes
        assert "fossil_capital" in writes
