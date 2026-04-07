"""Ensemble validation tests (Section 13.4).

- Deterministic equivalence when all perturbation widths are zero
- Stable percentile summaries under repeated seeded execution
- Correct threshold counting on synthetic fixtures
"""

from __future__ import annotations

from typing import Any

import numpy as np

from pyworldx.forecasting.ensemble import (
    EnsembleSpec,
    ThresholdQuery,
    run_ensemble,
)
from pyworldx.scenarios.scenario import Scenario


def _rip_factory(overrides: dict[str, float]) -> list[Any]:
    from pyworldx.sectors.rip_sectors import (
        IndustrySector,
        PollutionSector,
        ResourceSector,
    )
    return [ResourceSector(), IndustrySector(), PollutionSector()]


class TestEnsembleValidation:
    def test_zero_width_deterministic_equivalence(self) -> None:
        """Ensemble with zero perturbation width should produce
        identical members (Section 13.4)."""
        spec = EnsembleSpec(
            n_runs=3,
            base_scenario=Scenario("test", "test", 1900, 1910),
            parameter_distributions={},
            seed=42,
            store_member_runs=True,
        )
        result = run_ensemble(
            spec, _rip_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        assert result.members is not None
        # All members should be identical
        for var in result.summary:
            for i in range(1, len(result.members)):
                np.testing.assert_array_equal(
                    result.members[0].trajectories[var],
                    result.members[i].trajectories[var],
                )

    def test_stable_percentiles_under_reseeding(self) -> None:
        """Same seed should produce identical summary stats."""
        kwargs = dict(
            n_runs=5,
            base_scenario=Scenario("test", "test", 1900, 1910),
            parameter_distributions={},
            seed=12345,
        )
        r1 = run_ensemble(
            EnsembleSpec(**kwargs), _rip_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        r2 = run_ensemble(
            EnsembleSpec(**kwargs), _rip_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        for var in r1.summary:
            if var in r2.summary:
                np.testing.assert_array_equal(
                    r1.summary[var]["mean"].values,
                    r2.summary[var]["mean"].values,
                )

    def test_threshold_counting_synthetic(self) -> None:
        """Threshold counting on a deterministic fixture: R always depletes
        below initial value, so P(R < R0) at t=10 should be 1.0."""
        spec = EnsembleSpec(
            n_runs=5,
            base_scenario=Scenario("test", "test", 1900, 1910),
            parameter_distributions={},
            threshold_queries=[
                ThresholdQuery("r_below_1000", "R", "below", 1000.0, 1910),
            ],
            seed=42,
        )
        result = run_ensemble(
            spec, _rip_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        # R starts at 1000 and depletes — at t=10 it should be below 1000
        prob = result.probability_of_threshold("r_below_1000")
        assert prob == 1.0
