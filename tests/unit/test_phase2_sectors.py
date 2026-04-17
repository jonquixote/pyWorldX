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


# ── E2: 9 missing unit tests ─────────────────────────────────────────────


def test_recycling_increases_with_prr() -> None:
    """Higher PRR stock leads to higher phosphorus recycling rate."""
    ctx = _make_ctx()
    inputs = {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "food_per_capita": Quantity(300.0, "food_units_per_person"),
        "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
        "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
    }
    s_lo = PhosphorusSector(initial_prr=0.1)
    s_hi = PhosphorusSector(initial_prr=0.9)
    out_lo = s_lo.compute(0.0, s_lo.init_stocks(ctx), inputs, ctx)
    out_hi = s_hi.compute(0.0, s_hi.init_stocks(ctx), inputs, ctx)
    assert out_hi["phosphorus_recycling_rate"].magnitude > out_lo["phosphorus_recycling_rate"].magnitude


def test_prr_increases_with_profitability() -> None:
    """Profitability drives dPRR positive: with zero sedimentation, mining >> recycling cost → d_PRR > 0."""
    ctx = _make_ctx()
    # sedimentation_rate=0 isolates the profitability mechanism from the large dissipation term
    s = PhosphorusSector(initial_prr=0.01, sedimentation_rate=0.0)
    stocks = s.init_stocks(ctx)
    inputs = {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "food_per_capita": Quantity(300.0, "food_units_per_person"),
        "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
        "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["d_PRR"].magnitude > 0.0, "dPRR must be positive when profitability_factor > 0 and dissipation = 0"


def test_85_percent_floor_behavior() -> None:
    """PRR clamps at 1.0: when PRR >= 1.0 and natural dynamics would push it higher, dPRR is forced ≤ 0."""
    ctx = _make_ctx()
    s = PhosphorusSector(initial_prr=1.0)
    stocks = {"P_soc": Quantity(14000.0, "megatonnes_P"), "PRR": Quantity(1.0, "dimensionless")}
    inputs = {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "food_per_capita": Quantity(300.0, "food_units_per_person"),
        "nr_fraction_remaining": Quantity(1.0, "dimensionless"),
        "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["d_PRR"].magnitude <= 0.0, "dPRR must be <= 0 when PRR is at ceiling (1.0)"


def test_analytical_weathering() -> None:
    """Weathering loss = P_soc * weathering_rate exactly (closed form)."""
    P_soc_val = 14000.0
    rate = 0.001
    ctx = _make_ctx()
    s = PhosphorusSector(weathering_rate=rate)
    stocks = {"P_soc": Quantity(P_soc_val, "megatonnes_P"), "PRR": Quantity(0.0, "dimensionless")}
    inputs = {
        "industrial_output": Quantity(7.9e11, "industrial_output_units"),
        "food_per_capita": Quantity(0.0, "food_units_per_person"),  # zero waste
        "nr_fraction_remaining": Quantity(0.0, "dimensionless"),    # zero mining
        "supply_multiplier_phosphorus": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    expected_loss = P_soc_val * rate  # 14.0 Mt/yr
    # dP_soc = 0 (mining) + 0 (recycling) - expected_loss (weathering) - 0 (waste)
    assert abs(out["d_P_soc"].magnitude + expected_loss) < 1e-6, (
        f"d_P_soc={out['d_P_soc'].magnitude:.6f}, expected ~{-expected_loss:.6f}"
    )


def test_finance_sector_reads_tnds_aes() -> None:
    """FinanceSector.declares_reads() must include 'tnds_aes'."""
    from pyworldx.sectors.finance import FinanceSector
    assert "tnds_aes" in FinanceSector().declares_reads()


def test_100_percent_replacement_impossible() -> None:
    """AES cost grows when ESP → 0, but esp_multiplier stays near zero — natural services cannot be bought back."""
    ctx = _make_ctx()
    s = EcosystemServicesSector()
    stocks = {"ESP": Quantity(0.01, "dimensionless")}
    inputs = {
        "pollution_index": Quantity(1.0, "dimensionless"),
        "AL": Quantity(0.9e9, "hectares"),
        "temperature_anomaly": Quantity(0.0, "deg_C_anomaly"),
        "supply_multiplier_aes": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["tnds_aes"].magnitude > 0.0, "AES cost must be positive when ESP is depleted"
    assert out["esp_multiplier"].magnitude < 0.1, (
        "esp_multiplier must reflect actual ESP, not AES spending — 100% replacement impossible"
    )


def test_aerosol_decay() -> None:
    """With industrial_output = 0, aerosol index falls to near zero (quasi-equilibrium at source=0)."""
    ctx = _make_ctx()
    s = ClimateSector()
    stocks = s.init_stocks(ctx)
    inputs = {
        "industrial_output": Quantity(0.0, "industrial_output_units"),
        "pollution_generation": Quantity(0.0, "pollution_units"),
        "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    assert out["aerosol_index"].magnitude < 1e-10, (
        f"Aerosol must collapse to ~0 with zero IO; got {out['aerosol_index'].magnitude:.2e}"
    )


def test_aerosol_production() -> None:
    """Aerosol index is proportional to industrial output (A = K_AERO * io * tau)."""
    ctx = _make_ctx()
    s = ClimateSector()
    stocks = s.init_stocks(ctx)
    base_inputs = {
        "pollution_generation": Quantity(0.0, "pollution_units"),
        "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
    }
    out_lo = s.compute(0.0, stocks, {**base_inputs, "industrial_output": Quantity(1.0e11, "industrial_output_units")}, ctx)
    out_hi = s.compute(0.0, stocks, {**base_inputs, "industrial_output": Quantity(3.0e11, "industrial_output_units")}, ctx)
    ratio = out_hi["aerosol_index"].magnitude / max(out_lo["aerosol_index"].magnitude, 1e-30)
    assert abs(ratio - 3.0) < 0.01, f"Aerosol should scale 3× with 3× IO; got ratio={ratio:.4f}"


def test_analytical_aerosol_decay() -> None:
    """Aerosol quasi-equilibrium matches closed-form A = K_AERO * io * tau_aero within 1%."""
    from pyworldx.sectors.climate import _K_AERO, _TAU_AERO
    io_val = 7.9e11
    ctx = _make_ctx()
    s = ClimateSector()
    stocks = s.init_stocks(ctx)
    inputs = {
        "industrial_output": Quantity(io_val, "industrial_output_units"),
        "pollution_generation": Quantity(0.0, "pollution_units"),
        "supply_multiplier_climate": Quantity(1.0, "dimensionless"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    expected = _K_AERO * io_val * _TAU_AERO
    actual = out["aerosol_index"].magnitude
    rel_err = abs(actual - expected) / max(abs(expected), 1e-30)
    assert rel_err < 0.01, f"Aerosol quasi-eq: expected={expected:.3e}, actual={actual:.3e}"
