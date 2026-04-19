"""Phase 1 end-to-end integration test.

Runs ALL Phase 1 sectors together through the engine to verify
cross-sector data flow, CentralRegistrar integration, and physics-based
bounds on key trajectories.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyworldx.core.central_registrar import CentralRegistrar
from pyworldx.core.engine import Engine
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.welfare import WelfareSector
from pyworldx.sectors.finance import FinanceSector
from pyworldx.sectors.energy_fossil import EnergyFossilSector
from pyworldx.sectors.energy_sustainable import EnergySustainableSector
from pyworldx.sectors.energy_technology import EnergyTechnologySector
from pyworldx.sectors.pollution_ghg import PollutionGHGModule
from pyworldx.sectors.pollution_toxins import PollutionToxinModule
from pyworldx.sectors.gini_distribution import GiniDistributionSector


def _all_phase1_sectors() -> list[object]:
    """Return all Phase 1 sectors."""
    return [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        FinanceSector(),
        EnergyFossilSector(),
        EnergySustainableSector(),
        EnergyTechnologySector(),
        PollutionGHGModule(),
        PollutionToxinModule(),
        GiniDistributionSector(),
        WelfareSector(),
    ]


@pytest.fixture(scope="module")
def result_200y() -> object:
    """Cache a single 200-year run for all physics tests."""
    return Engine(
        sectors=_all_phase1_sectors(),
        master_dt=1.0,
        t_start=0.0,
        t_end=200.0,
    ).run()


class TestPhase1EndToEnd:
    """Run all Phase 1 sectors together through the engine."""

    def test_engine_completes_200_years(self, result_200y: object) -> None:
        """Engine completes 200-year run without crash or NaN."""
        assert len(result_200y.time_index) == 201  # type: ignore[attr-defined]
        for name, traj in result_200y.trajectories.items():  # type: ignore[attr-defined]
            assert not np.any(np.isnan(traj)), f"NaN in {name}"
            assert not np.any(np.isinf(traj)), f"Inf in {name}"

    def test_population_in_physical_range(self, result_200y: object) -> None:
        """Population stays between 0.5 billion and 20 billion over 200 years."""
        pop = np.asarray(result_200y.trajectories["POP"])  # type: ignore[attr-defined]
        assert np.all(pop > 5e8), f"POP went below 0.5 billion: min={pop.min():.2e}"
        assert np.all(pop < 2e10), f"POP exceeded 20 billion: max={pop.max():.2e}"

    def test_industrial_output_positive(self, result_200y: object) -> None:
        """Industrial output must remain positive throughout the 200-year run."""
        io = np.asarray(result_200y.trajectories["industrial_output"])  # type: ignore[attr-defined]
        assert np.all(io > 0), f"industrial_output went non-positive: min={io.min():.2e}"

    def test_food_per_capita_non_negative(self, result_200y: object) -> None:
        """food_per_capita must remain >= 0 throughout."""
        fpc = np.asarray(result_200y.trajectories["food_per_capita"])  # type: ignore[attr-defined]
        assert np.all(fpc >= 0.0), f"food_per_capita went negative: min={fpc.min():.2f}"

    def test_nonrenewable_resources_decline(self, result_200y: object) -> None:
        """NR (nonrenewable resource stock) must strictly decline over 200 years."""
        nr = np.asarray(result_200y.trajectories["NR"])  # type: ignore[attr-defined]
        assert nr[-1] < nr[0], (
            f"NR must deplete over 200 years: start={nr[0]:.2e}, end={nr[-1]:.2e}"
        )

    def test_pollution_index_non_negative(self, result_200y: object) -> None:
        """Pollution index must remain non-negative (PPOL / baseline cannot go below 0)."""
        ppol = np.asarray(result_200y.trajectories["pollution_index"])  # type: ignore[attr-defined]
        assert np.all(ppol >= 0.0), f"pollution_index went negative: min={ppol.min():.4f}"

    def test_finance_liquid_funds_initialized(self, result_200y: object) -> None:
        """FinanceSector: L starts positive (1900 liquid funds > 0)."""
        assert "L" in result_200y.trajectories, "L not in trajectories"  # type: ignore[attr-defined]
        l_funds = np.asarray(result_200y.trajectories["L"])  # type: ignore[attr-defined]
        assert l_funds[0] > 0, f"Liquid funds at t=0 must be positive: {l_funds[0]:.2e}"

    def test_fossil_output_positive(self, result_200y: object) -> None:
        """Fossil output must be positive throughout (capital > 0, EROI > 0)."""
        assert "fossil_output" in result_200y.trajectories, "fossil_output not recorded"  # type: ignore[attr-defined]
        fo = np.asarray(result_200y.trajectories["fossil_output"])  # type: ignore[attr-defined]
        assert np.all(fo > 0), f"fossil_output went non-positive: min={fo.min():.2e}"

    def test_fossil_eroi_declines_with_depletion(self, result_200y: object) -> None:
        """Fossil EROI must decline as NR is depleted."""
        assert "fossil_eroi" in result_200y.trajectories, "fossil_eroi not recorded"  # type: ignore[attr-defined]
        eroi = np.asarray(result_200y.trajectories["fossil_eroi"])  # type: ignore[attr-defined]
        assert eroi[-1] < eroi[0], (
            f"fossil_eroi must decline: start={eroi[0]:.2f}, end={eroi[-1]:.2f}"
        )

    def test_central_registrar_integration(self) -> None:
        """CentralRegistrar runs alongside sectors without error."""
        sectors = _all_phase1_sectors()
        cr = CentralRegistrar(enabled=True)
        result = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=50.0,
            central_registrar=cr,
        ).run()

        assert "fossil_output" in result.trajectories
        assert len(result.time_index) == 51

    def test_gini_unequal_allocation(self, result_200y: object) -> None:
        """Gini sector produces unequal per-capita food allocation between cohorts."""
        assert "gini_food_top10" in result_200y.trajectories, "gini_food_top10 not recorded"  # type: ignore[attr-defined]
        assert "gini_food_bot90" in result_200y.trajectories, "gini_food_bot90 not recorded"  # type: ignore[attr-defined]
        top10 = np.asarray(result_200y.trajectories["gini_food_top10"])  # type: ignore[attr-defined]
        bot90 = np.asarray(result_200y.trajectories["gini_food_bot90"])  # type: ignore[attr-defined]
        assert not np.allclose(top10, bot90), "Gini must produce unequal allocation"

    def test_pollution_split_stocks_exist(self, result_200y: object) -> None:
        """GHG and Toxin modules create their stocks and remain non-negative."""
        for key in ("ghg_stock", "toxin_s1", "toxin_s2", "toxin_s3"):
            assert key in result_200y.trajectories, f"{key} not in trajectories"  # type: ignore[attr-defined]
            arr = np.asarray(result_200y.trajectories[key])  # type: ignore[attr-defined]
            assert np.all(arr >= 0.0), f"{key} went negative: min={arr.min():.2e}"

    def test_ghg_stock_non_negative(self, result_200y: object) -> None:
        """GHG stock must remain non-negative throughout (no unphysical negative GHGs)."""
        ghg = np.asarray(result_200y.trajectories["ghg_stock"])  # type: ignore[attr-defined]
        assert np.all(ghg >= 0.0), f"ghg_stock went negative: min={ghg.min():.2e}"

    def test_deterministic_repeatability(self) -> None:
        """Two consecutive runs produce identical output."""
        cr = CentralRegistrar(enabled=True)
        r1 = Engine(
            sectors=_all_phase1_sectors(),
            master_dt=1.0,
            t_start=0.0,
            t_end=50.0,
            central_registrar=cr,
        ).run()
        r2 = Engine(
            sectors=_all_phase1_sectors(),
            master_dt=1.0,
            t_start=0.0,
            t_end=50.0,
            central_registrar=cr,
        ).run()

        for name in r1.trajectories:
            if name in r2.trajectories:
                np.testing.assert_array_equal(
                    r1.trajectories[name],
                    r2.trajectories[name],
                    err_msg=f"Non-deterministic output for {name}",
                )
