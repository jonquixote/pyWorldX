"""Tests for Human Capital sector (Phase 2 Task 1)."""

from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.human_capital import HumanCapitalSector


def _make_ctx() -> RunContext:
    return RunContext(
        master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={}
    )


class TestHumanCapitalSector:
    def test_init_stocks(self) -> None:
        s = HumanCapitalSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        assert "H" in stocks
        assert stocks["H"].magnitude == 0.3

    def test_custom_init(self) -> None:
        s = HumanCapitalSector(initial_h=0.5, skill_half_life=5.0)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        assert stocks["H"].magnitude == 0.5
        assert s.skill_half_life == 5.0

    def test_education_rate_increases_with_sopc(self) -> None:
        s = HumanCapitalSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_low = {
            "service_output_per_capita": Quantity(
                50.0, "service_output_units"
            ),
            "death_rate": Quantity(0.02, "per_year"),
        }
        inputs_high = {
            "service_output_per_capita": Quantity(
                400.0, "service_output_units"
            ),
            "death_rate": Quantity(0.02, "per_year"),
        }
        out_low = s.compute(0.0, stocks, inputs_low, ctx)
        out_high = s.compute(0.0, stocks, inputs_high, ctx)
        assert (
            out_high["education_rate"].magnitude
            > out_low["education_rate"].magnitude
        )

    def test_skill_degradation(self) -> None:
        s = HumanCapitalSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "service_output_per_capita": Quantity(
                0.0, "service_output_units"
            ),
            "death_rate": Quantity(0.0, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # Without education and mortality, H should degrade
        assert out["skill_degradation_rate"].magnitude > 0
        # dH should be negative (H is degrading)
        assert out["d_H"].magnitude < 0

    def test_mortality_loss(self) -> None:
        s = HumanCapitalSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs_low = {
            "service_output_per_capita": Quantity(
                100.0, "service_output_units"
            ),
            "death_rate": Quantity(0.01, "per_year"),
        }
        inputs_high = {
            "service_output_per_capita": Quantity(
                100.0, "service_output_units"
            ),
            "death_rate": Quantity(0.05, "per_year"),
        }
        out_low = s.compute(0.0, stocks, inputs_low, ctx)
        out_high = s.compute(0.0, stocks, inputs_high, ctx)
        assert (
            out_high["mortality_loss"].magnitude
            > out_low["mortality_loss"].magnitude
        )

    def test_h_bounded_at_zero(self) -> None:
        """H derivative should be clamped to 0 at lower bound."""
        s = HumanCapitalSector(initial_h=0.0)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "service_output_per_capita": Quantity(
                0.0, "service_output_units"
            ),
            "death_rate": Quantity(1.0, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert out["d_H"].magnitude == 0.0  # Clamped at 0

    def test_h_bounded_at_one(self) -> None:
        """H derivative should be clamped to 0 at upper bound."""
        s = HumanCapitalSector(initial_h=1.0)
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "service_output_per_capita": Quantity(
                800.0, "service_output_units"
            ),
            "death_rate": Quantity(0.0, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        # Education rate at SOPC=800 is 0.15 * 1e9 which is huge
        # dH should be clamped to 0
        assert out["d_H"].magnitude == 0.0  # Clamped at 1

    def test_declares_reads(self) -> None:
        s = HumanCapitalSector()
        reads = s.declares_reads()
        assert "service_output_per_capita" in reads
        assert "death_rate" in reads

    def test_declares_writes(self) -> None:
        s = HumanCapitalSector()
        writes = s.declares_writes()
        assert "H" in writes
        assert "education_rate" in writes
        assert "human_capital_multiplier" in writes
        assert "skill_degradation_rate" in writes
        assert "mortality_loss" in writes

    def test_metadata_complete(self) -> None:
        s = HumanCapitalSector()
        meta = s.metadata()
        assert "validation_status" in meta
        assert "equation_source" in meta
        assert "free_parameters" in meta
        free_params = meta["free_parameters"]
        assert isinstance(free_params, list)
        assert "initial_h" in free_params
        assert "skill_half_life" in free_params

    def test_all_outputs_are_quantities(self) -> None:
        s = HumanCapitalSector()
        ctx = _make_ctx()
        stocks = s.init_stocks(ctx)
        inputs = {
            "service_output_per_capita": Quantity(
                100.0, "service_output_units"
            ),
            "death_rate": Quantity(0.02, "per_year"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        for key, val in out.items():
            assert isinstance(val, Quantity), f"{key} is not a Quantity"


class TestHumanCapitalIntegration:
    def test_capital_uses_human_capital(self) -> None:
        """Capital sector production increases with H."""
        from pyworldx.sectors.capital import CapitalSector

        cap = CapitalSector()
        ctx = _make_ctx()
        stocks = cap.init_stocks(ctx)
        inputs_base = {
            "fcaor": Quantity(0.05, "dimensionless"),
            "POP": Quantity(1.65e9, "persons"),
            "P2": Quantity(7.0e8, "persons"),
            "P3": Quantity(3.0e8, "persons"),
            "AL": Quantity(0.9e9, "hectares"),
            "aiph": Quantity(100.0, "agricultural_input_units"),
            "food_per_capita": Quantity(
                300.0, "food_units_per_person"
            ),
            "frac_io_to_agriculture": Quantity(0.1, "dimensionless"),
            "industrial_output_per_capita": Quantity(
                400.0, "industrial_output_units"
            ),
            "service_output_per_capita": Quantity(
                87.0, "service_output_units"
            ),
            "maintenance_ratio": Quantity(1.0, "dimensionless"),
            "human_capital_multiplier": Quantity(0.5, "dimensionless"),
        }
        inputs_high_h = dict(inputs_base)
        inputs_high_h["human_capital_multiplier"] = Quantity(
            1.0, "dimensionless"
        )

        out_low = cap.compute(0.0, stocks, inputs_base, ctx)
        out_high = cap.compute(0.0, stocks, inputs_high_h, ctx)

        assert (
            out_high["industrial_output"].magnitude
            > out_low["industrial_output"].magnitude
        )

    def test_h_defaults_to_1_when_not_provided(self) -> None:
        """Capital sector works when human_capital_multiplier is absent."""
        from pyworldx.sectors.capital import CapitalSector

        cap = CapitalSector()
        ctx = _make_ctx()
        stocks = cap.init_stocks(ctx)
        inputs = {
            "fcaor": Quantity(0.05, "dimensionless"),
            "POP": Quantity(1.65e9, "persons"),
            "P2": Quantity(7.0e8, "persons"),
            "P3": Quantity(3.0e8, "persons"),
            "AL": Quantity(0.9e9, "hectares"),
            "aiph": Quantity(100.0, "agricultural_input_units"),
            "food_per_capita": Quantity(
                300.0, "food_units_per_person"
            ),
            "frac_io_to_agriculture": Quantity(0.1, "dimensionless"),
            "industrial_output_per_capita": Quantity(
                400.0, "industrial_output_units"
            ),
            "service_output_per_capita": Quantity(
                87.0, "service_output_units"
            ),
            "maintenance_ratio": Quantity(1.0, "dimensionless"),
            # No human_capital_multiplier — should default to 1.0
        }
        out = cap.compute(0.0, stocks, inputs, ctx)
        # Should produce positive IO without error
        assert out["industrial_output"].magnitude > 0

    def test_analytical_h_decay(self) -> None:
        """Isolated H decay approximately matches exponential decay."""
        # With no education and no mortality, dH/dt = -H * ln(2)/half_life
        # Solution: H(t) = H0 * exp(-ln(2)/half_life * t)
        half_life = 10.0
        s = HumanCapitalSector(initial_h=1.0, skill_half_life=half_life)
        
        class DummySector:
            name = "dummy"
            version = "1.0.0"
            timestep_hint = None
            def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
                return {}
            def compute(self, t: float, stocks: dict[str, Quantity], inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
                return {
                    "service_output_per_capita": Quantity(0.0, "service_output_units"),
                    "death_rate": Quantity(0.0, "per_year"),
                }
            def declares_reads(self) -> list[str]: return []
            def declares_writes(self) -> list[str]: return ["service_output_per_capita", "death_rate"]
            def metadata(self) -> dict[str, object]: return {}
            def algebraic_loop_hints(self) -> list: return []
            
        result = Engine(
            sectors=[s, DummySector()],
            master_dt=1.0,
            t_start=0.0,
            t_end=50.0,
        ).run()

        H_traj = result.trajectories["H"]
        t_grid = result.time_index

        # Verify H decreases monotonically
        for i in range(1, len(H_traj)):
            assert H_traj[i] <= H_traj[i - 1] + 1e-10, (
                f"H should decrease monotonically at t={t_grid[i]}"
            )

        # Verify H stays positive
        assert np.all(H_traj >= 0.0)

        # Verify approximate exponential decay (tight tolerance)
        decay_rate = np.log(2) / half_life
        analytical_h = 1.0 * np.exp(-decay_rate * t_grid)
        np.testing.assert_allclose(H_traj, analytical_h, rtol=1e-4, atol=1e-4)
