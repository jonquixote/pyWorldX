"""Tests for SEIR module (Phase 2 Task 5)."""

from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.seir import SEIRModule


def _make_ctx() -> RunContext:
    return RunContext(
        master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={}
    )


class TestSEIRModule:
    def test_init_stocks(self) -> None:
        s = SEIRModule()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        # 4 cohorts x 4 compartments = 16 stocks
        assert len(stocks) == 16
        for label in ["C1_0_14", "C2_15_44", "C3_45_64", "C4_65_plus"]:
            assert f"S_{label}" in stocks
            assert f"E_{label}" in stocks
            assert f"I_{label}" in stocks
            assert f"R_{label}" in stocks
        # Initial infected fraction should be small but non-zero
        total_i = sum(
            stocks[f"I_{label}"].magnitude
            for label in ["C1_0_14", "C2_15_44", "C3_45_64", "C4_65_plus"]
        )
        assert total_i > 0

    def test_epidemic_spreads(self) -> None:
        """With R0 > 1, infections should increase over time."""
        s = SEIRModule(r0_base=2.5, initial_infected_fraction=0.01)
        ctx = _make_ctx()
        s.init_stocks(ctx)
        {
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "P1": Quantity(0.4e9, "persons"),
            "P2": Quantity(1.0e9, "persons"),
            "P3": Quantity(0.5e9, "persons"),
            "P4": Quantity(0.2e9, "persons"),
            "birth_rate": Quantity(0.03, "per_year"),
            "death_rate": Quantity(0.02, "per_year"),
        }
        # Run the engine for 30 years to see epidemic dynamics
        result = Engine(
            sectors=[s],
            master_dt=1.0,
            t_start=0.0,
            t_end=30.0,
        ).run()
        i_initial = result.trajectories["infected_count"][0]
        i_peak = max(result.trajectories["infected_count"])
        assert i_peak > i_initial * 1.5, (
            f"Infections should grow: initial={i_initial:.0f}, peak={i_peak:.0f}"
        )

    def test_labor_force_multiplier(self) -> None:
        """Labor force multiplier should be < 1.0 when disease is present."""
        s = SEIRModule(
            r0_base=2.5,
            initial_infected_fraction=0.1,  # 10% initially infected
        )
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "P1": Quantity(0.4e9, "persons"),
            "P2": Quantity(1.0e9, "persons"),
            "P3": Quantity(0.5e9, "persons"),
            "P4": Quantity(0.2e9, "persons"),
            "birth_rate": Quantity(0.03, "per_year"),
            "death_rate": Quantity(0.02, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        lfm = out["labor_force_multiplier"].magnitude
        # With 10% infected + productivity penalty for recovered,
        # labor force should be reduced
        assert 0.0 <= lfm < 1.0, (
            f"LFM should be < 1.0 with disease present, got {lfm}"
        )

    def test_temperature_increases_transmission(self) -> None:
        """Higher temperature anomaly should increase reproduction number."""
        s = SEIRModule(r0_base=2.5, initial_infected_fraction=0.01)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_base = {
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "P1": Quantity(0.4e9, "persons"),
            "P2": Quantity(1.0e9, "persons"),
            "P3": Quantity(0.5e9, "persons"),
            "P4": Quantity(0.2e9, "persons"),
            "birth_rate": Quantity(0.03, "per_year"),
            "death_rate": Quantity(0.02, "per_year"),
        }
        inputs_warm = dict(inputs_base)
        inputs_warm["temperature_anomaly"] = Quantity(
            3.0, "deg_C_anomaly"
        )
        out_base = s.compute(0.0, stocks, inputs_base, ctx)
        out_warm = s.compute(0.0, stocks, inputs_warm, ctx)
        assert (
            out_warm["reproduction_number"].magnitude
            > out_base["reproduction_number"].magnitude
        )

    def test_reproduction_number(self) -> None:
        """Effective reproduction number should be computable."""
        s = SEIRModule(r0_base=2.5, initial_infected_fraction=0.01)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "P1": Quantity(0.4e9, "persons"),
            "P2": Quantity(1.0e9, "persons"),
            "P3": Quantity(0.5e9, "persons"),
            "P4": Quantity(0.2e9, "persons"),
            "birth_rate": Quantity(0.03, "per_year"),
            "death_rate": Quantity(0.02, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        r_eff = out["reproduction_number"].magnitude
        assert r_eff >= 0.0, "R_eff should be non-negative"

    def test_declares_reads(self) -> None:
        s = SEIRModule()
        reads = s.declares_reads()
        assert "temperature_anomaly" in reads
        assert "P1" in reads
        assert "P2" in reads
        assert "P3" in reads
        assert "P4" in reads
        assert "birth_rate" in reads
        assert "death_rate" in reads

    def test_declares_writes(self) -> None:
        s = SEIRModule()
        writes = s.declares_writes()
        assert "labor_force_multiplier" in writes
        assert "infected_count" in writes
        assert "reproduction_number" in writes
        for label in ["C1_0_14", "C2_15_44", "C3_45_64", "C4_65_plus"]:
            assert f"S_{label}" in writes
            assert f"I_{label}" in writes

    def test_all_outputs_are_quantities(self) -> None:
        s = SEIRModule()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "P1": Quantity(0.4e9, "persons"),
            "P2": Quantity(1.0e9, "persons"),
            "P3": Quantity(0.5e9, "persons"),
            "P4": Quantity(0.2e9, "persons"),
            "birth_rate": Quantity(0.03, "per_year"),
            "death_rate": Quantity(0.02, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        for key, val in out.items():
            assert isinstance(val, Quantity), f"{key} is not a Quantity"

    def test_non_negative_stocks(self) -> None:
        """SEIR dynamics should never produce negative S/E/I/R values."""
        s = SEIRModule(r0_base=2.5)
        ctx = _make_ctx()
        s.init_stocks(ctx)
        {
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "P1": Quantity(0.4e9, "persons"),
            "P2": Quantity(1.0e9, "persons"),
            "P3": Quantity(0.5e9, "persons"),
            "P4": Quantity(0.2e9, "persons"),
            "birth_rate": Quantity(0.03, "per_year"),
            "death_rate": Quantity(0.02, "per_year"),
        }
        # Run engine for 50 years
        result = Engine(
            sectors=[s],
            master_dt=1.0,
            t_start=0.0,
            t_end=50.0,
        ).run()
        for name, traj in result.trajectories.items():
            if name.startswith(("S_", "E_", "I_", "R_")):
                assert np.all(traj >= -1e-6), (
                    f"{name} went negative: min={traj.min():.2f}"
                )


class TestSEIRCapitalCoupling:
    def test_seir_labor_mult_propagates(self) -> None:
        """SEIR labor_force_multiplier is readable by Capital sector."""
        from pyworldx.sectors.population import PopulationSector
        from pyworldx.sectors.capital import CapitalSector
        from pyworldx.sectors.agriculture import AgricultureSector
        from pyworldx.sectors.resources import ResourcesSector
        from pyworldx.sectors.pollution import PollutionSector
        from pyworldx.sectors.welfare import WelfareSector
        from pyworldx.sectors.human_capital import HumanCapitalSector
        from pyworldx.sectors.ecosystem_services import EcosystemServicesSector
        from pyworldx.sectors.climate import ClimateSector
        from pyworldx.sectors.phosphorus import PhosphorusSector

        base_sectors = [
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
            HumanCapitalSector(),
            PhosphorusSector(),
            EcosystemServicesSector(),
            ClimateSector(),
            WelfareSector(),
        ]

        # Add SEIR with very small initial infection
        seir = SEIRModule(
            r0_base=2.5,
            initial_infected_fraction=0.00001,  # 0.001% initially infected
        )
        sectors_with_seir = base_sectors + [seir]

        # Run for 1 year — epidemic grows over ~1 year with these parameters
        result = Engine(
            sectors=sectors_with_seir,
            master_dt=1.0,
            t_start=0.0,
            t_end=1.0,
        ).run()

        # Check SEIR outputs exist
        assert "labor_force_multiplier" in result.trajectories
        assert "infected_count" in result.trajectories
        # With tiny infection and only 1 year, LFM should be near 1.0
        lfm = result.trajectories["labor_force_multiplier"]
        assert lfm[0] >= 0.99, (
            f"LFM should be near 1.0 initially, got {lfm[0]:.4f}"
        )
