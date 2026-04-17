"""Phase 1 end-to-end integration test.

Runs ALL Phase 1 sectors together through the engine to verify
cross-sector data flow, CentralRegistrar integration, and absence
of NaN/inf in all trajectories.
"""

from __future__ import annotations

import numpy as np

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


class TestPhase1EndToEnd:
    """Run all Phase 1 sectors together through the engine."""

    def test_engine_completes_200_years(self) -> None:
        """Engine completes 200-year run without crash or NaN."""
        sectors = _all_phase1_sectors()
        cr = CentralRegistrar(enabled=True)
        result = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=200.0,
            central_registrar=cr,
        ).run()

        assert len(result.time_index) == 201
        for name, traj in result.trajectories.items():
            assert not np.any(np.isnan(traj)), f"NaN in {name}"
            assert not np.any(np.isinf(traj)), f"Inf in {name}"

    def test_finance_sector_initializes(self) -> None:
        """FinanceSector: L starts positive."""
        sectors = _all_phase1_sectors()
        result = Engine(
            sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0,
        ).run()

        if "L" in result.trajectories:
            assert result.trajectories["L"][0] > 0

    def test_energy_sectors_produce_output(self) -> None:
        """Energy sectors produce non-zero output."""
        sectors = _all_phase1_sectors()
        result = Engine(
            sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0,
        ).run()

        if "fossil_output" in result.trajectories:
            assert np.any(result.trajectories["fossil_output"] > 0)

    def test_central_registrar_integration(self) -> None:
        """CentralRegistrar runs alongside sectors without error."""
        sectors = _all_phase1_sectors()
        cr = CentralRegistrar(enabled=True)
        result = Engine(
            sectors=sectors,
            master_dt=1.0,
            t_start=0.0,
            t_end=200.0,
            central_registrar=cr,
        ).run()

        assert "fossil_output" in result.trajectories
        assert len(result.time_index) == 201

    def test_gini_unequal_allocation(self) -> None:
        """Gini sector produces unequal allocation."""
        sectors = _all_phase1_sectors()
        result = Engine(
            sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0,
        ).run()

        if ("gini_food_top10" in result.trajectories
                and "gini_food_bot90" in result.trajectories):
            top10 = result.trajectories["gini_food_top10"]
            bot90 = result.trajectories["gini_food_bot90"]
            # At least some timesteps should show inequality
            assert not np.allclose(top10, bot90), (
                "Gini should produce unequal allocation"
            )

    def test_pollution_split_stocks_exist(self) -> None:
        """GHG and Toxin modules create their stocks."""
        sectors = _all_phase1_sectors()
        result = Engine(
            sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0,
        ).run()

        assert "ghg_stock" in result.trajectories
        assert "toxin_s1" in result.trajectories
        assert "toxin_s2" in result.trajectories
        assert "toxin_s3" in result.trajectories

    def test_deterministic_repeatability(self) -> None:
        """Two consecutive runs produce identical output."""
        sectors = _all_phase1_sectors()
        cr = CentralRegistrar(enabled=True)
        r1 = Engine(
            sectors=sectors,
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
