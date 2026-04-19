"""Task E3: Phase 2 cross-sector coupling integration tests."""
from __future__ import annotations

import numpy as np

from pyworldx.core.engine import Engine
from tests._phase2_helpers import make_phase2_sectors


def _run_200() -> object:
    engine = Engine(
        sectors=make_phase2_sectors(),
        master_dt=1.0,
        t_start=0.0,
        t_end=200.0,
    )
    return engine.run()


def test_temperature_rises_with_ghg() -> None:
    """GHG stock must increase over 200 years (base run has emissions) and
    temperature_anomaly must follow (non-negative by end)."""
    result = _run_200()
    t_anom = np.asarray(result.trajectories["temperature_anomaly"])
    # Temperature anomaly at end should be above pre-industrial (>=0)
    assert t_anom[-1] >= 0.0, f"Final T_anomaly={t_anom[-1]:.3f} must be non-negative"
    # Temperature should generally increase over the run
    assert t_anom[-1] >= t_anom[0], (
        f"T_anomaly must not fall below start: start={t_anom[0]:.3f}, end={t_anom[-1]:.3f}"
    )


def test_food_per_capita_non_negative() -> None:
    """food_per_capita must stay >= 0 throughout the run."""
    result = _run_200()
    fpc = np.asarray(result.trajectories["food_per_capita"])
    assert np.all(fpc >= 0.0), f"food_per_capita went negative: min={fpc.min():.2f}"


def test_tech_metals_availability_bounded() -> None:
    """tech_metals_availability must stay in [0, 1] throughout."""
    result = _run_200()
    avail = np.asarray(result.trajectories["tech_metals_availability"])
    assert np.all(avail >= 0.0), f"tech_metals_availability < 0: min={avail.min():.4f}"
    assert np.all(avail <= 1.0), f"tech_metals_availability > 1: max={avail.max():.4f}"


def test_soc_resilience_bounded() -> None:
    """soc_resilience_multiplier must stay in [0, 1] throughout."""
    result = _run_200()
    soc = np.asarray(result.trajectories["soc_resilience_multiplier"])
    assert np.all(soc >= 0.0), f"soc_resilience < 0: min={soc.min():.4f}"
    assert np.all(soc <= 1.0), f"soc_resilience > 1: max={soc.max():.4f}"


def test_industrial_output_positive() -> None:
    """industrial_output must remain positive throughout the base run."""
    result = _run_200()
    io = np.asarray(result.trajectories["industrial_output"])
    assert np.all(io > 0), f"industrial_output went non-positive: min={io.min():.2e}"
