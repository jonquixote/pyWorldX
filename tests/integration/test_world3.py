"""Tests for World3-03 sector library.

Tests all 5 sectors individually (unit consistency, sign/monotonicity,
nonneg guards) and as an integrated 5-sector model running through
the engine.

Sectors calibrated to wrld3-03.mdl (Vensim, September 29 2005).
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
        assert stocks["POP"].magnitude == 1.6e9

    def test_compute_produces_births_and_deaths(self) -> None:
        s = PopulationSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(460.0, "food_units_per_person"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "pollution_index": Quantity(1.0, "dimensionless"),
            "service_output_per_capita": Quantity(20.0, "service_output_units"),
        }
        out = s.compute(1950.0, stocks, inputs, ctx)
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
        stocks = s.init_stocks(ctx)
        base_inputs = {
            "food_per_capita": Quantity(460.0, "food_units_per_person"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "pollution_index": Quantity(0.0, "dimensionless"),
            "service_output_per_capita": Quantity(20.0, "service_output_units"),
        }
        out_clean = s.compute(1950.0, stocks, base_inputs, ctx)

        pol_inputs = dict(base_inputs)
        pol_inputs["pollution_index"] = Quantity(50.0, "dimensionless")
        out_dirty = s.compute(1950.0, stocks, pol_inputs, ctx)

        assert (
            out_dirty["life_expectancy"].magnitude
            < out_clean["life_expectancy"].magnitude
        )

    def test_lmhs_switching_at_1940(self) -> None:
        """LMHS1 (pre-1940) should give lower LE than LMHS2 (post-1940).

        t is simulation time (offset from 1900), so t=30 → 1930, t=50 → 1950.
        """
        s = PopulationSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        inputs = {
            "food_per_capita": Quantity(460.0, "food_units_per_person"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "pollution_index": Quantity(0.0, "dimensionless"),
            "service_output_per_capita": Quantity(50.0, "service_output_units"),
        }
        out_pre = s.compute(30.0, stocks, inputs, ctx)   # sim time = 1930
        out_post = s.compute(50.0, stocks, inputs, ctx)  # sim time = 1950
        assert (
            out_post["life_expectancy"].magnitude
            > out_pre["life_expectancy"].magnitude
        )


class TestCapitalSector:
    def test_init_stocks(self) -> None:
        s = CapitalSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "IC" in stocks
        assert "SC" in stocks
        assert stocks["IC"].magnitude == 2.1e11

    def test_compute_produces_industrial_output(self) -> None:
        s = CapitalSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        inputs = {
            "fcaor": Quantity(0.05, "dimensionless"),
            "POP": Quantity(1.65e9, "persons"),
            "food_per_capita": Quantity(230.0, "food_units_per_person"),
            "service_output_per_capita": Quantity(0.0, "service_output_units"),
        }
        out = s.compute(1900.0, stocks, inputs, ctx)
        assert "industrial_output" in out
        assert out["industrial_output"].magnitude > 0

    def test_fcaor_reduces_output(self) -> None:
        """Higher FCAOR (resource scarcity) should reduce IO."""
        s = CapitalSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        inputs_low = {
            "fcaor": Quantity(0.05, "dimensionless"),
            "POP": Quantity(1.65e9, "persons"),
            "food_per_capita": Quantity(230.0, "food_units_per_person"),
            "service_output_per_capita": Quantity(0.0, "service_output_units"),
        }
        inputs_high = dict(inputs_low)
        inputs_high["fcaor"] = Quantity(0.5, "dimensionless")

        out_low = s.compute(1900.0, stocks, inputs_low, ctx)
        out_high = s.compute(1900.0, stocks, inputs_high, ctx)
        assert (
            out_high["industrial_output"].magnitude
            < out_low["industrial_output"].magnitude
        )

    def test_ic_depreciation_rate(self) -> None:
        """IC depreciation should use ALIC=14 years (not 20)."""
        s = CapitalSector()
        assert s.alic == 14.0

    def test_fioai_is_residual(self) -> None:
        """FIOAI should be 1 - FIOAA - FIOAS - FIOAC."""
        s = CapitalSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        fioaa_in = 0.07
        inputs = {
            "fcaor": Quantity(0.05, "dimensionless"),
            "POP": Quantity(3e9, "persons"),
            "food_per_capita": Quantity(300.0, "food_units_per_person"),
            "service_output_per_capita": Quantity(100.0, "service_output_units"),
            "frac_io_to_agriculture": Quantity(fioaa_in, "dimensionless"),
        }
        out = s.compute(1970.0, stocks, inputs, ctx)
        fioai = out["frac_io_to_industry"].magnitude
        fioas = out["frac_io_to_services"].magnitude
        fioac = out["frac_io_to_consumption"].magnitude
        assert abs(fioai + fioas + fioaa_in + fioac - 1.0) < 0.01


class TestAgricultureSector:
    def test_init_stocks(self) -> None:
        s = AgricultureSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "AL" in stocks
        assert "LFERT" in stocks
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
        out = s.compute(1900.0, stocks, inputs, ctx)
        assert "food" in out
        assert "food_per_capita" in out
        assert out["food"].magnitude > 0
        assert out["food_per_capita"].magnitude > 0

    def test_lymc_full_range(self) -> None:
        """LYMC table should go up to AIPH=1000 with yield multiplier=10."""
        from pyworldx.sectors.agriculture import _LYMC_X, _LYMC_Y
        assert len(_LYMC_X) == 26
        assert _LYMC_X[-1] == 1000.0
        assert _LYMC_Y[-1] == 10.0

    def test_fioaa_reaches_zero(self) -> None:
        """FIOAA should reach 0 when food is abundant (FPC/SFPC >= 2)."""
        from pyworldx.sectors.agriculture import _FIOAA_X, _FIOAA_Y
        # At x=2.0, y should be 0.0
        idx = list(_FIOAA_X).index(2.0)
        assert _FIOAA_Y[idx] == 0.0


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
            "industrial_output_per_capita": Quantity(
                1e12 / 3e9, "industrial_output_units"
            ),
        }
        out = s.compute(1970.0, stocks, inputs, ctx)
        assert out["d_NR"].magnitude < 0  # depleting

    def test_pcrum_w303_values(self) -> None:
        """PCRUM table should use W3-03 X-axis (0..1600) not old (0..150)."""
        from pyworldx.sectors.resources import _PCRUM_X
        assert _PCRUM_X[-1] == 1600.0

    def test_fcaor_output(self) -> None:
        """Resources sector should output FCAOR for capital sector."""
        s = ResourcesSector()
        ctx = RunContext()
        stocks = {"NR": Quantity(5e11, "resource_units")}
        inputs = {
            "POP": Quantity(3e9, "persons"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "industrial_output_per_capita": Quantity(
                1e12 / 3e9, "industrial_output_units"
            ),
        }
        out = s.compute(1970.0, stocks, inputs, ctx)
        assert "fcaor" in out
        fcaor = out["fcaor"].magnitude
        assert 0.0 <= fcaor <= 1.0

    def test_substep_hint(self) -> None:
        s = ResourcesSector()
        assert s.timestep_hint == 0.25


class TestPollutionSector:
    def test_init_stocks(self) -> None:
        s = PollutionSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        assert "PPOL" in stocks
        # DELAY3 pipeline stocks
        assert "PPDL1" in stocks
        assert "PPDL2" in stocks
        assert "PPDL3" in stocks

    def test_ahl70_correct(self) -> None:
        """Base absorption half-life should be 1.5 years (not 20)."""
        s = PollutionSector()
        assert s.ahl70 == 1.5

    def test_ahlm_table_correct(self) -> None:
        """AHLM table should have massive nonlinearity (41x at PPOLX=1001)."""
        from pyworldx.sectors.pollution import _AHLM_X, _AHLM_Y
        assert _AHLM_X[-1] == 1001.0
        assert _AHLM_Y[-1] == 41.0

    def test_pollution_efficiency_bounded(self) -> None:
        s = PollutionSector()
        ctx = RunContext()
        stocks = s.init_stocks(ctx)
        stocks["PPOL"] = Quantity(1.36e8, "pollution_units")
        inputs = {
            "POP": Quantity(3e9, "persons"),
            "industrial_output": Quantity(1e12, "industrial_output_units"),
            "food": Quantity(1e12, "food_units"),
            "AL": Quantity(0.9e9, "hectares"),
            "nrur": Quantity(1e10, "resource_units"),
        }
        out = s.compute(1970.0, stocks, inputs, ctx)
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
        assert np.max(pop) > pop[0] * 1.5  # at least 50% growth at peak

    def test_resources_deplete(self) -> None:
        """Non-renewable resources should deplete over the simulation."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        nr = result.trajectories["NR"]
        assert nr[-1] < nr[0] * 0.95  # at least 5% depletion

    def test_pollution_rises(self) -> None:
        """Pollution should rise over the simulation."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        ppol = result.trajectories["PPOL"]
        assert np.max(ppol) > ppol[0] * 1.5  # pollution rises

    def test_industrial_output_exists(self) -> None:
        """Industrial output should be recorded and positive."""
        sectors = self._make_sectors()
        result = Engine(sectors=sectors, t_end=200.0).run()
        assert "industrial_output" in result.trajectories
        io = result.trajectories["industrial_output"]
        assert io[0] > 0

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
