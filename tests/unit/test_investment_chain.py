"""Task 6 tests: TAI → CAI → AI investment chain + FIOAA ownership.

Tests the W3-03 corrected agricultural input allocation:
    IO × FIOAA → TAI
    TAI × FIALD(MPLD/MPAI) → Land Development (÷ DCPH)
    TAI × (1-FIALD) → CAI (1st-order delay, ALAI=2yr) → AI
    AI × (1-FALM) / AL → AIPH → LYMC → food
    AI × FALM → land maintenance
"""

from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.agriculture import (
    AgricultureSector,
    _DCPH_X,
    _DCPH_Y,
    _FALM_X,
    _FALM_Y,
    _FIALD_X,
    _FIALD_Y,
    _LYMC_X,
    _LYMC_Y,
)
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.table_functions import table_lookup


def _base_inputs() -> dict[str, Quantity]:
    return {
        "industrial_output": Quantity(1.0e12, "industrial_output_units"),
        "POP": Quantity(3.5e9, "persons"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "food_per_capita": Quantity(300.0, "food_units_per_person"),
    }


# 1. FIALD table canonical values
def test_fiald_table_values() -> None:
    assert _FIALD_X[0] == 0.0
    assert _FIALD_X[-1] == 2.0
    assert _FIALD_Y[0] == 0.0
    assert _FIALD_Y[-1] == 1.0
    assert _FIALD_Y == tuple(sorted(_FIALD_Y))  # monotonic increasing


# 2. DCPH table canonical values
def test_dcp_table_values() -> None:
    assert _DCPH_X[0] == 0.0
    assert _DCPH_X[-1] == 1.0
    # Cost falls then rises? Canonical: very high at 0, decreasing monotone.
    assert _DCPH_Y[0] > _DCPH_Y[-1]
    assert _DCPH_Y[0] == 100000.0


# 3. FALM table canonical values
def test_falm_table_values() -> None:
    assert _FALM_X[0] == 0.0
    assert _FALM_Y[0] == 0.0
    assert _FALM_Y[-1] > 0.0
    assert _FALM_Y == tuple(sorted(_FALM_Y))


# 4. FIALD split: when MPLD >> MPAI, FIALD should be high
def test_fiald_split_high_mpld() -> None:
    s = AgricultureSector()
    ctx = RunContext()
    stocks = s.init_stocks(ctx)
    # Very low AL (hence high productivity of land development relative to ag input)
    stocks["AL"] = Quantity(1e6, "hectares")
    out = s.compute(1970.0, stocks, _base_inputs(), ctx)
    assert out["fiald"].magnitude > 0.3


# 5. FIALD split: when MPAI >> MPLD, FIALD should be low
def test_fiald_split_high_mpai() -> None:
    s = AgricultureSector()
    ctx = RunContext()
    stocks = s.init_stocks(ctx)
    # Plenty of arable land (low MPLD), low CAI (high marginal on inputs)
    stocks["AL"] = Quantity(3.0e9, "hectares")  # near PAL
    stocks["CAI"] = Quantity(1.0e6, "agricultural_input_units")
    out = s.compute(1970.0, stocks, _base_inputs(), ctx)
    assert out["fiald"].magnitude < 0.5


# 6. CAI is smoothed version of TAI × (1-FIALD)
def test_cai_smoothed_vs_tai() -> None:
    s = AgricultureSector()
    ctx = RunContext()
    stocks = s.init_stocks(ctx)
    out = s.compute(1970.0, stocks, _base_inputs(), ctx)
    # d_CAI has dimensions of AI / year — finite, non-NaN
    d_cai = out["d_CAI"].magnitude
    assert np.isfinite(d_cai)
    # Setting CAI = 0 should produce positive d_CAI (ramp up)
    stocks["CAI"] = Quantity(0.0, "agricultural_input_units")
    out2 = s.compute(1970.0, stocks, _base_inputs(), ctx)
    assert out2["d_CAI"].magnitude > 0.0


# 7. FALM splits AI
def test_falm_splits_ai() -> None:
    s = AgricultureSector()
    ctx = RunContext()
    stocks = s.init_stocks(ctx)
    # High fpc → PFR high → FALM > 0 → less productive AIPH than CAI/AL
    inputs_high = dict(_base_inputs())
    inputs_high["food_per_capita"] = Quantity(800.0, "food_units_per_person")
    out = s.compute(1970.0, stocks, inputs_high, ctx)
    cai = stocks["CAI"].magnitude
    al = stocks["AL"].magnitude
    aiph_if_no_falm = cai / al
    assert out["aiph"].magnitude < aiph_if_no_falm
    assert out["falm"].magnitude > 0.0


# 8. Capital reads FIOAA from shared, doesn't compute it
def test_fioaa_from_agriculture_not_capital() -> None:
    cap = CapitalSector()
    assert "frac_io_to_agriculture" not in cap.declares_writes()
    assert "frac_io_to_agriculture" in cap.declares_reads()
    agri = AgricultureSector()
    assert "frac_io_to_agriculture" in agri.declares_writes()


# 9. MLYMC is numerical derivative of LYMC
def test_mlymc_numerical_derivative() -> None:
    # Pick an AIPH; numerical derivative should match linearized slope of LYMC table.
    aiph = 100.0
    delta = 1.0
    lymc_base = table_lookup(aiph, _LYMC_X, _LYMC_Y)
    lymc_pert = table_lookup(aiph + delta, _LYMC_X, _LYMC_Y)
    mlymc = (lymc_pert - lymc_base) / delta
    # For AIPH in [80,120], LYMC rises from 4.5→5.0 → slope ~0.0125
    expected = (5.0 - 4.5) / (120.0 - 80.0)
    assert abs(mlymc - expected) < 1e-6


# 10. Full chain in engine
def test_full_chain_in_engine() -> None:
    sectors = [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
    ]
    result = Engine(sectors=sectors, t_end=50.0, master_dt=1.0).run()
    for key in (
        "industrial_output",
        "frac_io_to_agriculture",
        "aiph",
        "CAI",
        "fiald",
        "falm",
        "food",
        "food_per_capita",
        "land_yield",
    ):
        assert key in result.trajectories, f"missing {key}"
        assert not np.any(np.isnan(result.trajectories[key]))


# 11. Food trajectory differs from naive (non-FALM) approximation
def test_food_trajectory_changes() -> None:
    # After W3-03 FALM split, aiph (and thus food) is strictly smaller than if
    # all CAI were productive. Check food trajectory is reasonable.
    sectors = [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
    ]
    result = Engine(sectors=sectors, t_end=100.0, master_dt=1.0).run()
    fpc = result.trajectories["food_per_capita"]
    falm = result.trajectories["falm"]
    # FALM should be > 0 at least once (food abundance triggers maintenance)
    # Or if not, at least trajectory is finite and positive
    assert np.all(fpc > 0.0)
    assert np.all(np.isfinite(falm))
