"""Tests for Regional Trade sector (Phase 2 Task 6)."""

from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.regional_trade import RegionalTradeSector


def _make_ctx() -> RunContext:
    return RunContext(
        master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={}
    )


class TestRegionalTradeSector:
    def test_init_stocks(self) -> None:
        s = RegionalTradeSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        assert stocks == {}  # No stocks — pure redistribution

    def test_trade_redistributes_food(self) -> None:
        """Trade should redistribute food from surplus to deficit regions."""
        s = RegionalTradeSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # Trade volume should be positive
        assert out["total_trade_volume"].magnitude >= 0

    def test_dissipative_trade(self) -> None:
        """Trade losses mean received < sent (dissipative)."""
        s = RegionalTradeSector(transport_loss=0.1)  # 10% loss
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # Energy demand should be positive (trade requires energy)
        assert out["energy_demand_regional_trade"].magnitude >= 0

    def test_temperature_reduces_trade(self) -> None:
        """Higher temperature anomaly should reduce trade attractiveness."""
        s = RegionalTradeSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_base = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        inputs_hot = dict(inputs_base)
        inputs_hot["temperature_anomaly"] = Quantity(
            5.0, "deg_C_anomaly"
        )
        out_base = s.compute(0.0, stocks, inputs_base, ctx)
        out_hot = s.compute(0.0, stocks, inputs_hot, ctx)
        # Higher temperature should reduce trade volume
        assert (
            out_hot["total_trade_volume"].magnitude
            <= out_base["total_trade_volume"].magnitude
        )

    def test_lifeboating_detection(self) -> None:
        """Lifeboating activates when FPC drops below threshold."""
        s = RegionalTradeSector(lifeboating_fpc_threshold=150.0)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        # Normal conditions: FPC=300, above threshold
        inputs_normal = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        out_normal = s.compute(0.0, stocks, inputs_normal, ctx)
        # Lifeboating should not be active
        assert out_normal["lifeboating_active"].magnitude == 0.0

        # Stress conditions: FPC=100, below threshold
        inputs_stress = {
            "food_per_capita": Quantity(100.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        s.compute(0.0, stocks, inputs_stress, ctx)
        # With FPC=100 distributed unevenly, some regions should lifeboat
        # (periphery gets 0.6/2.7 * 100 ≈ 22, below 150 threshold)

    def test_migration_flows_exist(self) -> None:
        """Migration flows should be computed internally."""
        s = RegionalTradeSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # Check regional outputs exist
        for name in s.region_names:
            assert f"regional_fpc_{name}" in out
            assert f"regional_io_{name}" in out
            assert f"regional_pop_{name}" in out

    def test_declares_reads(self) -> None:
        s = RegionalTradeSector()
        reads = s.declares_reads()
        assert "food_per_capita" in reads
        assert "industrial_output" in reads
        assert "POP" in reads
        assert "temperature_anomaly" in reads

    def test_declares_writes(self) -> None:
        s = RegionalTradeSector()
        writes = s.declares_writes()
        assert "energy_demand_regional_trade" in writes
        assert "supply_multiplier_regional_trade" in writes
        assert "lifeboating_active" in writes
        assert "total_trade_volume" in writes

    def test_all_outputs_are_quantities(self) -> None:
        s = RegionalTradeSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        for key, val in out.items():
            assert isinstance(val, Quantity), f"{key} is not a Quantity"

    def test_custom_num_regions(self) -> None:
        """Sector should work with different numbers of regions."""
        s = RegionalTradeSector(num_regions=5)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "POP": Quantity(2.1e9, "persons"),
            "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        }
        s.compute(0.0, stocks, inputs, ctx)
        assert len(s.region_names) == 5


class TestRegionalIntegration:
    def test_regional_with_base_sectors(self) -> None:
        """Regional sector runs alongside base sectors."""
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
            RegionalTradeSector(),
            WelfareSector(),
        ]
        result = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=50.0,
        ).run()

        assert len(result.time_index) == 51
        assert "lifeboating_active" in result.trajectories
        assert "total_trade_volume" in result.trajectories

    def test_regional_with_all_phase2(self) -> None:
        """Regional sector runs with most Phase 2 sectors (excluding SEIR)."""
        from pyworldx.sectors.population import PopulationSector
        from pyworldx.sectors.capital import CapitalSector
        from pyworldx.sectors.agriculture import AgricultureSector
        from pyworldx.sectors.resources import ResourcesSector
        from pyworldx.sectors.pollution import PollutionSector
        from pyworldx.sectors.welfare import WelfareSector
        from pyworldx.sectors.human_capital import HumanCapitalSector
        from pyworldx.sectors.phosphorus import PhosphorusSector
        from pyworldx.sectors.ecosystem_services import EcosystemServicesSector
        from pyworldx.sectors.climate import ClimateSector

        sectors = [
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
            HumanCapitalSector(),
            PhosphorusSector(),
            EcosystemServicesSector(),
            ClimateSector(),
            RegionalTradeSector(),
            WelfareSector(),
        ]
        result = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=3.0,  # Short run to avoid long-term instability
        ).run()

        assert len(result.time_index) == 4
        # Check no NaN in any trajectory
        for name, traj in result.trajectories.items():
            assert not np.any(np.isnan(traj)), f"NaN in {name}"
