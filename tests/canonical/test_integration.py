"""Canonical integration test: R-I-P model vs reference trajectory.

Section 17.4 pass criterion:
    max over all (t, variable) of:
        |pyWorldX_value - reference_value| / |reference_value| < 1e-4

This test verifies:
1. The engine runs the canonical R-I-P model deterministically
2. Multi-rate sub-stepping (R at 4:1)
3. Algebraic loop resolution (I<->P)
4. Results match the committed reference trajectory
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pyworldx.core.engine import Engine, IncompatibleTimestepError
from pyworldx.sectors.rip_sectors import (
    IndustrySector,
    PollutionSector,
    ResourceSector,
)


CANONICAL_DIR = Path(__file__).parent
REFERENCE_CSV = CANONICAL_DIR / "reference_trajectory.csv"

# Variables to check against reference
CHECK_VARS = [
    "R", "K", "P",
    "extraction_rate", "industrial_output",
    "pollution_fraction", "pollution_efficiency",
]


def load_reference() -> pd.DataFrame:
    """Load the committed reference trajectory, skipping comment header."""
    return pd.read_csv(REFERENCE_CSV, comment="#")


class TestCanonicalIntegration:
    """Full R-I-P canonical world against reference trajectory."""

    def test_engine_runs_deterministically(self) -> None:
        """Two consecutive runs produce identical output."""
        sectors1 = [ResourceSector(), IndustrySector(), PollutionSector()]
        sectors2 = [ResourceSector(), IndustrySector(), PollutionSector()]

        r1 = Engine(sectors=sectors1).run()
        r2 = Engine(sectors=sectors2).run()

        for var in CHECK_VARS:
            np.testing.assert_array_equal(
                r1.trajectories[var],
                r2.trajectories[var],
                err_msg=f"Non-deterministic output for {var}",
            )

    def test_matches_reference_trajectory(self) -> None:
        """Max relative error < 1e-4 across all variables and timesteps."""
        ref = load_reference()
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        result = Engine(sectors=sectors).run()

        max_rel_errors: dict[str, float] = {}

        for var in CHECK_VARS:
            ref_vals = ref[var].values
            eng_vals = result.trajectories[var]

            assert len(ref_vals) == len(eng_vals), (
                f"Length mismatch for {var}: ref={len(ref_vals)}, engine={len(eng_vals)}"
            )

            max_rel = 0.0
            for i in range(len(ref_vals)):
                ref_v = ref_vals[i]
                eng_v = eng_vals[i]
                if abs(ref_v) > 1e-12:
                    rel = abs(eng_v - ref_v) / abs(ref_v)
                    max_rel = max(max_rel, rel)
                else:
                    # Near-zero: use absolute check
                    assert abs(eng_v - ref_v) < 1e-10, (
                        f"{var} at t={ref['t'].values[i]}: "
                        f"abs error {abs(eng_v - ref_v):.2e} on near-zero ref"
                    )

            max_rel_errors[var] = max_rel

        for var, err in max_rel_errors.items():
            assert err < 1e-4, (
                f"{var}: max relative error = {err:.2e} (limit: 1e-4)"
            )

    def test_resource_depletes(self) -> None:
        """R should deplete significantly from 1000 over 200 years."""
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        result = Engine(sectors=sectors).run()
        r_final = result.trajectories["R"][-1]
        r_initial = result.trajectories["R"][0]
        assert r_final < r_initial * 0.01, (
            f"R did not deplete enough: {r_initial} -> {r_final}"
        )

    def test_pollution_rises_then_decays(self) -> None:
        """P should rise (industry emits) then eventually decay."""
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        result = Engine(sectors=sectors).run()
        p = result.trajectories["P"]
        p_max = np.max(p)
        p_final = p[-1]
        assert p_max > 10.0, f"Pollution never rose significantly: max={p_max}"
        assert p_final < p_max, "Pollution should decay from peak"

    def test_substep_ratio_4(self) -> None:
        """ResourceSector must run with substep_ratio=4."""
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        engine = Engine(sectors=sectors)
        assert engine.substep_ratios["resources"] == 4

    def test_incompatible_timestep_raises(self) -> None:
        """Non-integer ratio must raise IncompatibleTimestepError."""
        with pytest.raises(IncompatibleTimestepError):
            r = ResourceSector()
            r.timestep_hint = 0.3  # 1.0 / 0.3 is not integer
            Engine(sectors=[r, IndustrySector(), PollutionSector()])

    def test_result_has_correct_time_index(self) -> None:
        """Time index should go from 0 to 200 in steps of 1."""
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        result = Engine(sectors=sectors).run()
        expected_t = np.arange(0.0, 201.0, 1.0)
        np.testing.assert_array_almost_equal(result.time_index, expected_t)

    def test_analytical_decay_subcase(self) -> None:
        """Section 17.4 analytical sub-case: isolated pollution decay.

        With pollution_inflow=0, P(0)=100, tau_p=20, the ODE
            dP/dt = -P / tau_p
        has analytical solution P(t) = 100 * exp(-t / tau_p).

        Pass: relative error < 1e-4 for t ≤ 100, absolute error < 1e-6 for t > 100.
        """
        import numpy as np

        from pyworldx.core.quantities import POLLUTION_UNITS, Quantity
        from pyworldx.sectors.base import RunContext

        class _IsolatedPollution:
            """Pollution with inflow disabled — pure exponential decay."""

            name = "pollution"
            version = "1.0.0"
            timestep_hint: float | None = None

            def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
                return {"P": Quantity(100.0, POLLUTION_UNITS)}

            def compute(
                self,
                t: float,
                stocks: dict[str, Quantity],
                inputs: dict[str, Quantity],
                ctx: RunContext,
            ) -> dict[str, Quantity]:
                p = stocks["P"].magnitude
                return {"d_P": Quantity(-p / 20.0, POLLUTION_UNITS)}

            def declares_reads(self) -> list[str]:
                return []

            def declares_writes(self) -> list[str]:
                return ["P"]

            def algebraic_loop_hints(self) -> list[dict[str, object]]:
                return []

            def metadata(self) -> dict[str, object]:
                return {}

        result = Engine(
            sectors=[_IsolatedPollution()],
            master_dt=1.0,
            t_start=0.0,
            t_end=200.0,
        ).run()

        t_grid = result.time_index
        p_numerical = result.trajectories["P"]
        p_analytical = 100.0 * np.exp(-t_grid / 20.0)

        for ti, pn, pa in zip(t_grid, p_numerical, p_analytical):
            if ti <= 100.0:
                rel = abs(pn - pa) / max(abs(pa), 1e-12)
                assert rel < 1e-4, (
                    f"t={ti}: relative error {rel:.2e} exceeds 1e-4 "
                    f"(numerical={pn:.6g}, analytical={pa:.6g})"
                )
            else:
                assert abs(pn - pa) < 1e-6, (
                    f"t={ti}: absolute error {abs(pn - pa):.2e} exceeds 1e-6 "
                    f"(numerical={pn:.6g}, analytical={pa:.6g})"
                )

    def test_to_dataframe_works(self) -> None:
        """RunResult.to_dataframe() should produce a valid DataFrame."""
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        result = Engine(sectors=sectors).run()
        df = result.to_dataframe()
        assert "t" in df.columns
        for var in CHECK_VARS:
            assert var in df.columns
        assert len(df) == 201
