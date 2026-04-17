"""Pin 1900 IO baseline + Nebel 2023 trajectory; fail loudly if Phase 2 edits shift them.

Uses relative time t=0.0 (1900) → t=200.0 (2100) as per engine convention.
"""
from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

from pyworldx.core.engine import Engine
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.resources import ResourcesSector

_SNAPSHOT = Path(__file__).parent / "fixtures" / "nebel_2023_snapshot.npz"


def _run_phase1_only() -> dict[str, np.ndarray]:
    engine = Engine(
        sectors=[
            PopulationSector(),
            CapitalSector(),
            AgricultureSector(),
            ResourcesSector(),
            PollutionSector(),
        ],
        t_start=0.0,
        t_end=200.0,
        master_dt=1.0,
    )
    result = engine.run()
    return {k: np.asarray(v) for k, v in result.trajectories.items()}


def test_1900_baseline_io_pinned() -> None:
    """industrial_output at t=0 (year 1900) must be within calibrated range."""
    traj = _run_phase1_only()
    assert "industrial_output" in traj, "engine must record industrial_output"
    io_1900 = float(traj["industrial_output"][0])
    assert 6.5e10 <= io_1900 <= 6.8e10, f"IO(1900) = {io_1900:.3e}; expected 6.5e10–6.8e10"


@pytest.mark.skipif(not _SNAPSHOT.exists(), reason="snapshot not yet seeded")
def test_nebel_2023_trajectory_within_tolerance() -> None:
    """Full 1900–2100 run must stay within 1.5% RMS of pinned Nebel 2023 snapshot."""
    traj = _run_phase1_only()
    snapshot = np.load(_SNAPSHOT)
    for key in ("POP", "industrial_output", "food_per_capita"):
        if key not in snapshot or key not in traj:
            continue
        current = traj[key]
        pinned = snapshot[key]
        n = min(len(current), len(pinned))
        rms_err = float(
            np.sqrt(np.mean((current[:n] - pinned[:n]) ** 2))
            / np.mean(np.abs(pinned[:n]))
        )
        assert rms_err < 0.015, f"{key} drifted {rms_err * 100:.2f}% from pinned snapshot"
