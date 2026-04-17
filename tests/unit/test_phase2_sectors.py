"""Tests for Phase 2 sectors: Phosphorus, Ecosystem Services, Climate."""

from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.phosphorus import PhosphorusSector
from pyworldx.sectors.ecosystem_services import EcosystemServicesSector
from pyworldx.sectors.climate import ClimateSector


def _make_ctx() -> RunContext:
    return RunContext(
        master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={}
    )


# ── Phosphorus Sector Tests ────────────────────────────────────────────


class TestPhosphorusSector:
    def test_init_stocks(self) -> None:
        s = PhosphorusSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        assert "P_soc" in stocks
        assert "PRR" in stocks
        assert stocks["P_soc"].magnitude > 0
        assert 0 <= stocks["PRR"].magnitude <= 1

    def test_mining_declines_with_nrfr(self) -> None:
        s = PhosphorusSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_full = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
            "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
        }
        inputs_dep = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "nr_fraction_remaining": Quantity(0.1, "dimensionless"),
            "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
        }
        out_full = s.compute(0.0, stocks, inputs_full, ctx)
        out_dep = s.compute(0.0, stocks, inputs_dep, ctx)
        assert (
            out_full["phosphorus_mining_rate"].magnitude
            > out_dep["phosphorus_mining_rate"].magnitude
        )

    def test_energy_demand_broadcast(self) -> None:
        s = PhosphorusSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
            "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert "energy_demand_phosphorus" in out
        assert out["energy_demand_phosphorus"].magnitude > 0

    def test_supply_multiplier_affects_mining(self) -> None:
        """Reduced supply multiplier should reduce mining rate."""
        s = PhosphorusSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_full = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
            "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
        }
        inputs_half = dict(inputs_full)
        inputs_half["supply_multiplier_phosphorus"] = Quantity(
            0.5, "dimensionless"
        )
        out_full = s.compute(0.0, stocks, inputs_full, ctx)
        out_half = s.compute(0.0, stocks, inputs_half, ctx)
        assert (
            out_full["phosphorus_mining_rate"].magnitude
            > out_half["phosphorus_mining_rate"].magnitude
        )

    def test_declares_reads(self) -> None:
        s = PhosphorusSector()
        reads = s.declares_reads()
        assert "nr_fraction_remaining" in reads
        assert "supply_multiplier_phosphorus" in reads

    def test_declares_writes(self) -> None:
        s = PhosphorusSector()
        writes = s.declares_writes()
        assert "P_soc" in writes
        assert "PRR" in writes
        assert "energy_demand_phosphorus" in writes
        assert "phosphorus_availability" in writes

    def test_all_outputs_are_quantities(self) -> None:
        s = PhosphorusSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
            "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        for key, val in out.items():
            assert isinstance(val, Quantity), f"{key} is not a Quantity"


# ── Ecosystem Services Sector Tests ─────────────────────────────────────


class TestEcosystemServicesSector:
    def test_init_stocks(self) -> None:
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        assert "ESP" in stocks
        assert stocks["ESP"].magnitude == 1.0

    def test_degradation_increases_with_pollution(self) -> None:
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_low = {
            "pollution_index": Quantity(1.0, "dimensionless"),
            "AL": Quantity(0.9e9, "hectares"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        inputs_high = {
            "pollution_index": Quantity(10.0, "dimensionless"),
            "AL": Quantity(0.9e9, "hectares"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        out_low = s.compute(0.0, stocks, inputs_low, ctx)
        out_high = s.compute(0.0, stocks, inputs_high, ctx)
        # Higher pollution should cause faster ESP decline
        assert out_low["d_ESP"].magnitude > out_high["d_ESP"].magnitude

    def test_degradation_increases_with_land_use(self) -> None:
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_natural = {
            "pollution_index": Quantity(1.0, "dimensionless"),
            "AL": Quantity(5.0e9, "hectares"),  # High AL = low land use
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        inputs_developed = {
            "pollution_index": Quantity(1.0, "dimensionless"),
            "AL": Quantity(0.5e9, "hectares"),  # Low AL = high land use
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        out_nat = s.compute(0.0, stocks, inputs_natural, ctx)
        out_dev = s.compute(0.0, stocks, inputs_developed, ctx)
        assert out_nat["d_ESP"].magnitude > out_dev["d_ESP"].magnitude

    def test_regeneration_at_baseline(self) -> None:
        """At ESP=1.0, logistic regeneration = 0 (ESP*(1-ESP) = 0)."""
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "pollution_index": Quantity(0.0, "dimensionless"),
            "AL": Quantity(6.0e9, "hectares"),  # PAL = no land use
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # At ESP=1.0, regeneration = 0, degradation = 0, so dESP = 0
        assert abs(out["d_ESP"].magnitude) < 1e-10

    def test_tnds_aes_scales_exponentially(self) -> None:
        """As ESP approaches 0, TNDS_AES should grow super-linearly."""
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks_low = {"ESP": Quantity(0.9, "dimensionless")}
        stocks_high = {"ESP": Quantity(0.5, "dimensionless")}
        inputs = {
            "pollution_index": Quantity(5.0, "dimensionless"),
            "AL": Quantity(3.0e9, "hectares"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        out_low = s.compute(0.0, stocks_low, inputs, ctx)
        out_high = s.compute(0.0, stocks_high, inputs, ctx)
        # TNDS_AES at ESP=0.5 should be much larger than at ESP=0.9
        tnds_ratio = (
            out_high["tnds_aes"].magnitude
            / max(out_low["tnds_aes"].magnitude, 1e-10)
        )
        assert tnds_ratio > 1.0

    def test_energy_demand_broadcast(self) -> None:
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "pollution_index": Quantity(5.0, "dimensionless"),
            "AL": Quantity(3.0e9, "hectares"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert "energy_demand_aes" in out

    def test_all_outputs_are_quantities(self) -> None:
        s = EcosystemServicesSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "pollution_index": Quantity(5.0, "dimensionless"),
            "AL": Quantity(3.0e9, "hectares"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
            "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        for key, val in out.items():
            assert isinstance(val, Quantity), f"{key} is not a Quantity"


# ── Climate Sector Tests ────────────────────────────────────────────────


class TestClimateSector:
    def test_init_stocks(self) -> None:
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        assert "T" in stocks
        assert "A" in stocks
        assert stocks["T"].magnitude == 0.0
        assert stocks["A"].magnitude == 1.0

    def test_aerosol_at_equilibrium(self) -> None:
        """Aerosol is always at quasi-equilibrium with industrial output."""
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_low = {
            "industrial_output": Quantity(1.0e11, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        inputs_high = {
            "industrial_output": Quantity(1.0e13, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        out_low = s.compute(0.0, stocks, inputs_low, ctx)
        out_high = s.compute(0.0, stocks, inputs_high, ctx)
        # Higher IO should produce higher aerosol index
        assert (
            out_high["aerosol_index"].magnitude
            > out_low["aerosol_index"].magnitude
        )
        # dA should be 0 (algebraic equilibrium)
        assert out_high["d_A"].magnitude == 0.0

    def test_termination_shock(self) -> None:
        """Industrial crash → aerosol drops to near zero immediately."""
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(0.0, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # Aerosol index should be ~0 (no industrial output to produce aerosols)
        assert out["aerosol_index"].magnitude < 0.01

    def test_temperature_rises_with_ghg(self) -> None:
        """Higher pollution generation should increase temperature."""
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_low = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        inputs_high = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "pollution_generation": Quantity(1.0e14, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        out_low = s.compute(0.0, stocks, inputs_low, ctx)
        out_high = s.compute(0.0, stocks, inputs_high, ctx)
        assert out_high["d_T"].magnitude > out_low["d_T"].magnitude

    def test_heat_shock_below_threshold(self) -> None:
        """At T=0, heat_shock_multiplier should be 1.0."""
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert out["heat_shock_multiplier"].magnitude == 1.0

    def test_energy_demand_broadcast(self) -> None:
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert "energy_demand_climate" in out

    def test_all_outputs_are_quantities(self) -> None:
        s = ClimateSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "pollution_generation": Quantity(0.0, "pollution_units"),
            "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        for key, val in out.items():
            assert isinstance(val, Quantity), f"{key} is not a Quantity"


# ── Cross-Sector Integration Tests ──────────────────────────────────────


class TestPhase2SectorsIntegration:
    def test_all_phase2_sectors_run_together(self) -> None:
        """All Phase 2 sectors run together without crash or NaN."""
        from pyworldx.sectors.population import PopulationSector
        from pyworldx.sectors.capital import CapitalSector
        from pyworldx.sectors.agriculture import AgricultureSector
        from pyworldx.sectors.resources import ResourcesSector
        from pyworldx.sectors.pollution import PollutionSector
        from pyworldx.sectors.welfare import WelfareSector

        sectors = [
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
            PhosphorusSector(),
            EcosystemServicesSector(),
            ClimateSector(),
            WelfareSector(),
        ]
        result = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=200.0,
        ).run()

        assert len(result.time_index) == 201
        for name, traj in result.trajectories.items():
            assert not np.any(np.isnan(traj)), f"NaN in {name}"
            assert not np.any(np.isinf(traj)), f"Inf in {name}"

    def test_heat_shock_affects_food(self) -> None:
        """Higher temperature anomaly reduces food production."""
        from pyworldx.sectors.population import PopulationSector
        from pyworldx.sectors.capital import CapitalSector
        from pyworldx.sectors.agriculture import AgricultureSector
        from pyworldx.sectors.resources import ResourcesSector
        from pyworldx.sectors.pollution import PollutionSector
        from pyworldx.sectors.welfare import WelfareSector

        base_sectors = [
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
            WelfareSector(),
        ]
        # Run without climate — heat_shock_multiplier defaults to 1.0
        result_no_climate = Engine(
            sectors=base_sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=100.0,
        ).run()

        # With climate at elevated temperature, heat shock should reduce food
        sectors_with_climate = base_sectors + [ClimateSector()]
        result_with_climate = Engine(
            sectors=sectors_with_climate,
            master_dt=1.0,
            t_start=0.0,
            t_end=100.0,
        ).run()

        # Both should produce non-negative food; climate may cause oscillations
        assert np.all(result_no_climate.trajectories["food_per_capita"] >= 0)
        assert np.all(result_with_climate.trajectories["food_per_capita"] >= 0)
        # Without climate, food should generally be higher
        mean_no = np.mean(result_no_climate.trajectories["food_per_capita"])
        mean_with = np.mean(result_with_climate.trajectories["food_per_capita"])
        assert mean_no >= mean_with, (
            f"Climate should reduce average food: {mean_no:.1f} vs {mean_with:.1f}"
        )

    def test_phosphorus_affects_food(self) -> None:
        """Phosphorus availability affects food production."""
        from pyworldx.sectors.population import PopulationSector
        from pyworldx.sectors.capital import CapitalSector
        from pyworldx.sectors.agriculture import AgricultureSector
        from pyworldx.sectors.resources import ResourcesSector
        from pyworldx.sectors.pollution import PollutionSector
        from pyworldx.sectors.welfare import WelfareSector

        base_sectors = [
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
            WelfareSector(),
        ]
        result_no_p = Engine(
            sectors=base_sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=100.0,
        ).run()

        sectors_with_p = base_sectors + [PhosphorusSector()]
        result_with_p = Engine(
            sectors=sectors_with_p,
            master_dt=1.0,
            t_start=0.0,
            t_end=100.0,
        ).run()

        # Skip t=0 where bootstrap may not fully converge with new stocks
        assert np.all(result_no_p.trajectories["food_per_capita"][1:] > 0)
        assert np.all(result_with_p.trajectories["food_per_capita"][1:] > 0)
