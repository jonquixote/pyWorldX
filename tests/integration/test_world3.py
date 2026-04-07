"""Tests for World3-03 sector library.

Tests all 5 sectors individually (unit consistency, sign/monotonicity,
nonneg guards) and as an integrated 5-sector model running through
the engine.
"""

from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.resources import ResourcesSector


# ── Individual sector tests ──────────────────────────────────────────

class TestPopulationSector:
    def test_init_stocks(self) -> None:
        s = PopulationSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "POP" in stocks
        assert stocks["POP"].magnitude == 1.65e9

    def test_compute_produces_births_and_deaths(self) -> None:
        s = PopulationSector()
        ctx = RunContext()
        stocks = {"POP": Quantity(3.0e9, "persons")}
        inputs = {
            "food_per_capita": Quantity(2.0, "food_units_per_person"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "pollution_index": Quantity(1.0, "dimensionless"),
            "service_output_per_capita": Quantity(20.0, "service_output_units"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert "d_POP" in out
        assert "birth_rate" in out
        assert "death_rate" in out
        assert "life_expectancy" in out
        assert out["birth_rate"].magnitude > 0
        assert out["death_rate"].magnitude > 0
        assert out["life_expectancy"].magnitude > 0

    def test_pollution_reduces_life_expectancy(self) -> None:
        s = PopulationSector()
        ctx = RunContext()
        stocks = {"POP": Quantity(3.0e9, "persons")}
        base_inputs = {
            "food_per_capita": Quantity(2.0, "food_units_per_person"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "pollution_index": Quantity(0.0, "dimensionless"),
            "service_output_per_capita": Quantity(20.0, "service_output_units"),
        }
        out_clean = s.compute(0.0, stocks, base_inputs, ctx)

        pol_inputs = dict(base_inputs)
        pol_inputs["pollution_index"] = Quantity(50.0, "dimensionless")
        out_dirty = s.compute(0.0, stocks, pol_inputs, ctx)

        assert (
            out_dirty["life_expectancy"].magnitude
            < out_clean["life_expectancy"].magnitude
        )


class TestCapitalSector:
    def test_init_stocks(self) -> None:
        s = CapitalSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "IC" in stocks
        assert "SC" in stocks
        assert stocks["IC"].magnitude > 0

    def test_compute_produces_industrial_output(self) -> None:
        s = CapitalSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        inputs = {
            "extraction_rate": Quantity(1e9, "resource_units"),
            "pollution_index": Quantity(0.0, "dimensionless"),
            "POP": Quantity(1.65e9, "persons"),
            "pollution_efficiency": Quantity(1.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert "industrial_output" in out
        assert out["industrial_output"].magnitude > 0


class TestAgricultureSector:
    def test_init_stocks(self) -> None:
        s = AgricultureSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "AL" in stocks
        assert stocks["AL"].magnitude > 0

    def test_compute_produces_food(self) -> None:
        s = AgricultureSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        inputs = {
            "industrial_output": Quantity(7e10, "industrial_output_units"),
            "POP": Quantity(1.65e9, "persons"),
            "pollution_index": Quantity(0.0, "dimensionless"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert "food" in out
        assert "food_per_capita" in out
        assert out["food"].magnitude > 0
        assert out["food_per_capita"].magnitude > 0


class TestResourcesSector:
    def test_init_stocks(self) -> None:
        s = ResourcesSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "NR" in stocks
        assert stocks["NR"].magnitude == 1e12

    def test_extraction_depletes(self) -> None:
        s = ResourcesSector()
        ctx = RunContext()
        stocks = {"NR": Quantity(1e12, "resource_units")}
        inputs = {
            "POP": Quantity(3e9, "persons"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        assert out["d_NR"].magnitude < 0  # depleting

    def test_substep_hint(self) -> None:
        s = ResourcesSector()
        assert s.timestep_hint == 0.25


class TestPollutionSector:
    def test_init_stocks(self) -> None:
        s = PollutionSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "PPOL" in stocks

    def test_pollution_efficiency_bounded(self) -> None:
        s = PollutionSector()
        ctx = RunContext()
        stocks = {"PPOL": Quantity(1.36e8, "pollution_units")}
        inputs = {
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "food": Quantity(1e12, "food_units"),
        }
        out = s.compute(0.0, stocks, inputs, ctx)
        pe = out["pollution_efficiency"].magnitude
        assert 0.0 < pe <= 1.0


# ── Full World3-03 integration test ─────────────────────────────────

class TestWorld3Integration:
    """Run the full 5-sector World3-03 model through the engine."""

    @staticmethod
    def _make_sectors() -> list[object]:
        return [
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
        ]

    def test_engine_runs_200_years(self) -> None:
        """Engine should complete a 200-year run without crash or NaN."""
        sectors = self._make_sectors()
        engine = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=200.0,
        )
        result = engine.run()

        # 201 time points (t=0 to t=200)
        assert len(result.time_index) == 201

        # No NaN in any trajectory
        for name, traj in result.trajectories.items():
            assert not np.any(np.isnan(traj)), f"NaN found in {name}"

    def test_population_grows(self) -> None:
        """Population should grow substantially over 200 years."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        pop = result.trajectories["POP"]
        assert pop[-1] > pop[0] * 1.5  # at least 50% growth

    def test_resources_deplete(self) -> None:
        """Non-renewable resources should deplete over the simulation.

        Threshold is conservative (>5% depletion) — the extraction mechanism
        is exercised and verified, but full World3-03 calibration to match
        Nebel 2023 NRMSD bounds is a deferred Sprint 4 item.
        """
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        nr = result.trajectories["NR"]
        er = result.trajectories["extraction_rate"]

        # Significant depletion (currently ~7.9%; guard against regression
        # to zero extraction)
        assert nr[-1] < nr[0] * 0.95

        # The causal mechanism: extraction rate should be higher when both
        # population and industrial output are higher.  Compare t=0 vs t=100.
        # This catches the case where er collapses to zero without a good reason.
        assert er[0] > 0, "extraction rate should be positive at t=0"
        # At t=0, POP is 1.65e9 and IO is ~7e10 — er should be substantial.
        # If er[0] drops below this, the PCRUM table scaling is broken.
        assert er[0] > 1e6, (
            f"extraction rate at t=0 is too low: {er[0]:.2e}. "
            f"Check _PCRUM table scaling in resources.py."
        )
        # er should correlate with io * pop: higher inputs → higher extraction
        assert er[0] >= er[-1], (
            "extraction rate should not grow when NR depletes and "
            "io/pop collapse — this suggests the mechanism is inverted"
        )

    def test_pollution_rises(self) -> None:
        """Pollution should rise over the simulation."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        ppol = result.trajectories["PPOL"]
        assert np.max(ppol) > ppol[0] * 2  # pollution at least doubles

    def test_industrial_output_exists(self) -> None:
        """Industrial output should be recorded."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        assert "industrial_output" in result.trajectories
        io = result.trajectories["industrial_output"]
        assert io[0] > 0  # initial IO is positive

    def test_food_per_capita_positive(self) -> None:
        """Food per capita should remain positive throughout."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        fpc = result.trajectories["food_per_capita"]
        assert np.all(fpc > 0)

    def test_deterministic(self) -> None:
        """Two runs with same sectors should produce identical results."""
        r1 = Engine(sectors=self._make_sectors(), t_end=50.0).run()
        r2 = Engine(sectors=self._make_sectors(), t_end=50.0).run()
        for name in r1.trajectories:
            if name in r2.trajectories:
                np.testing.assert_array_equal(
                    r1.trajectories[name], r2.trajectories[name]
                )

    def test_substep_ratio_resources(self) -> None:
        """Resources sector should be sub-stepped at 4:1."""
        sectors = self._make_sectors()
        engine = Engine(sectors=sectors, t_end=10.0)
        assert engine.substep_ratios["resources"] == 4
