"""Task E1: Phase 2 full-stack integration smoke test."""
from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from tests._phase2_helpers import make_phase2_sectors


def test_all_phase2_sectors_integrate() -> None:
    """200-year run with all Phase 2 sectors: no crash, no NaN, no Inf."""
    sectors = make_phase2_sectors()
    engine = Engine(
        sectors=sectors,
        master_dt=1.0,
        t_start=0.0,
        t_end=200.0,
    )
    result = engine.run()

    assert len(result.time_index) == 201, (
        f"Expected 201 time points, got {len(result.time_index)}"
    )

    for name, traj in result.trajectories.items():
        arr = np.asarray(traj)
        assert not np.any(np.isnan(arr)), f"NaN in trajectory '{name}'"
        assert not np.any(np.isinf(arr)), f"Inf in trajectory '{name}'"


def test_phase2_key_trajectories_present() -> None:
    """Core Phase 2 outputs must appear in result trajectories."""
    sectors = make_phase2_sectors()
    engine = Engine(sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0)
    result = engine.run()

    required = [
        "POP",
        "industrial_output",
        "food_per_capita",
        "temperature_anomaly",
        "radiative_forcing_ghg",   # emitted by climate.py
        "disease_death_rate",       # emitted by seir.py (D1)
        "tech_metals_availability", # emitted by resources.py (C1)
        "soc_resilience_multiplier", # emitted by phosphorus.py
    ]
    missing = [k for k in required if k not in result.trajectories]
    assert not missing, f"Missing trajectories: {missing}"


def test_phase2_population_positive_throughout() -> None:
    """POP must stay positive across the entire 200-year run."""
    sectors = make_phase2_sectors()
    engine = Engine(sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0)
    result = engine.run()

    pop = np.asarray(result.trajectories["POP"])
    assert np.all(pop > 0), f"POP went non-positive: min={pop.min():.2e}"
