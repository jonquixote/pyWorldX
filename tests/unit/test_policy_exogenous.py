"""Tests for policy event wiring (Task 1) and exogenous override injection (Task 2)."""

from __future__ import annotations


import numpy as np
import pandas as pd

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.scenarios.runner import build_exogenous_injector, build_policy_applier
from pyworldx.scenarios.scenario import PolicyEvent, PolicyShape, Scenario
from pyworldx.sectors.base import RunContext


# ── Minimal sector for testing ──────────────────────────────────────


class _StubSector:
    """Minimal sector that reads/writes a single auxiliary for testing."""

    name = "stub"
    substep_ratio: int | None = None
    timestep_hint: float | None = None

    def __init__(self, initial_val: float = 100.0) -> None:
        self._initial_val = initial_val
        self._compute_log: list[dict[str, float]] = []

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"S": Quantity(10.0, "units")}

    def declares_reads(self) -> list[str]:
        return ["aux_var"]

    def declares_writes(self) -> list[str]:
        return ["aux_var", "d_S"]

    def declares_stocks(self) -> list[str]:
        return ["S"]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"equation_source": "PLACEHOLDER"}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        aux = inputs.get("aux_var", Quantity(self._initial_val, "units"))
        self._compute_log.append({"t": t, "aux_var": aux.magnitude})
        return {
            "aux_var": aux,
            "d_S": Quantity(0.1, "units"),
        }


def _make_engine(
    sector: _StubSector | None = None,
    **kwargs: object,
) -> Engine:
    s = sector or _StubSector()
    return Engine(
        sectors=[s],
        master_dt=1.0,
        t_start=0.0,
        t_end=5.0,
        **kwargs,  # type: ignore[arg-type]
    )


# ── Task 1: Policy applier tests ────────────────────────────────────


class TestPolicyApplierNone:
    def test_none_produces_identical_output(self) -> None:
        """Engine with policy_applier=None matches default behavior."""
        s1 = _StubSector()
        s2 = _StubSector()
        r1 = _make_engine(s1).run()
        r2 = _make_engine(s2, policy_applier=None).run()
        np.testing.assert_array_equal(
            r1.trajectories["S"], r2.trajectories["S"]
        )


class TestPolicyApplierCalledEachTimestep:
    def test_called_per_master_step(self) -> None:
        call_count = 0

        def applier(values: dict[str, float], t: float) -> dict[str, float]:
            nonlocal call_count
            call_count += 1
            return values

        _make_engine(policy_applier=applier).run()
        assert call_count == 5  # t_end=5, dt=1 → 5 steps


class TestPolicyAppliedBeforeSectorCompute:
    def test_sectors_see_modified_values(self) -> None:
        """Sector receives policy-modified aux_var value."""
        sector = _StubSector(initial_val=100.0)

        def applier(values: dict[str, float], t: float) -> dict[str, float]:
            if "aux_var" in values:
                values["aux_var"] = 999.0
            return values

        _make_engine(sector, policy_applier=applier).run()
        # After bootstrap, sector should see 999.0 from policy
        # (first step at t=0 applies policy, then sector computes)
        modified_vals = [e["aux_var"] for e in sector._compute_log]
        # At least one compute should see the modified value
        assert any(v == 999.0 for v in modified_vals)


class TestStepPolicyModifiesShared:
    def test_step_sets_value(self) -> None:
        def applier(values: dict[str, float], t: float) -> dict[str, float]:
            if t >= 2.0 and "aux_var" in values:
                values["aux_var"] = 999.0
            return values

        sector = _StubSector(initial_val=100.0)
        _make_engine(sector, policy_applier=applier).run()
        # After t=2, at least one compute should see 999.0
        vals_after_2 = [e["aux_var"] for e in sector._compute_log if e["t"] >= 2.0]
        assert len(vals_after_2) > 0
        assert any(v == 999.0 for v in vals_after_2)


class TestPolicyNotAppliedToStocks:
    def test_stocks_unchanged_by_policy(self) -> None:
        """Policy applier should not modify stock values."""
        def applier(values: dict[str, float], t: float) -> dict[str, float]:
            # Try to modify stock S — should be blocked
            if "S" in values:
                values["S"] = 9999.0
            return values

        r = _make_engine(policy_applier=applier).run()
        # S should follow normal integration (0.1/step), not jump to 9999
        assert r.trajectories["S"][-1] < 100.0


class TestMultiplePolicies:
    def test_multiple_policies_applied(self) -> None:
        scenario = Scenario(
            name="multi",
            description="multiple policies",
            start_year=1900,
            end_year=1905,
            policy_events=[
                PolicyEvent("aux_var", PolicyShape.STEP, t_start=1.0, magnitude=10.0),
                PolicyEvent("aux_var", PolicyShape.STEP, t_start=2.0, magnitude=20.0),
            ],
        )
        applier = build_policy_applier(scenario)
        assert applier is not None
        result = applier({"aux_var": 100.0}, t=3.0)
        # Both policies active: +10 + +20 = +30
        assert result["aux_var"] == 130.0


class TestBuildPolicyApplier:
    def test_none_for_no_events(self) -> None:
        s = Scenario(
            name="empty", description="", start_year=1900, end_year=2100
        )
        assert build_policy_applier(s) is None

    def test_custom_fn(self) -> None:
        scenario = Scenario(
            name="custom",
            description="custom policy",
            start_year=1900,
            end_year=2100,
            policy_events=[
                PolicyEvent(
                    "x",
                    PolicyShape.CUSTOM,
                    t_start=0.0,
                    custom_fn=lambda base, t: base * 2,
                ),
            ],
        )
        applier = build_policy_applier(scenario)
        assert applier is not None
        result = applier({"x": 50.0}, t=10.0)
        assert result["x"] == 100.0


# ── Task 2: Exogenous injector tests ────────────────────────────────


class TestExogenousInjectorNone:
    def test_none_produces_identical_output(self) -> None:
        s1 = _StubSector()
        s2 = _StubSector()
        r1 = _make_engine(s1).run()
        r2 = _make_engine(s2, exogenous_injector=None).run()
        np.testing.assert_array_equal(
            r1.trajectories["S"], r2.trajectories["S"]
        )


class TestExogenousInjectorCalledPerStep:
    def test_called_per_master_step(self) -> None:
        call_count = 0

        def injector(t: float) -> dict[str, float]:
            nonlocal call_count
            call_count += 1
            return {}

        _make_engine(exogenous_injector=injector).run()
        assert call_count == 5


class TestOntologyNameTranslation:
    def test_ontology_to_engine_name(self) -> None:
        """Exogenous injector translates ontology names via ENTITY_TO_ENGINE_MAP."""
        from pyworldx.data.bridge import ENTITY_TO_ENGINE_MAP

        # Find a mapping that exists
        ontology_name = "population.total"
        engine_name = ENTITY_TO_ENGINE_MAP[ontology_name]
        assert engine_name == "POP"

        # Build injector with ontology name
        scenario = Scenario(
            name="test_translate",
            description="",
            start_year=1900,
            end_year=1905,
            exogenous_overrides={
                ontology_name: pd.Series([5e9, 6e9], index=[0, 200]),
            },
        )
        injector = build_exogenous_injector(scenario)
        assert injector is not None
        result = injector(100.0)
        assert ontology_name in result
        # The engine translates ontology → engine name internally


class TestExogenousReplacesShared:
    def test_override_replaces_value(self) -> None:
        sector = _StubSector(initial_val=100.0)

        def injector(t: float) -> dict[str, float]:
            return {"aux_var": 777.0}

        _make_engine(sector, exogenous_injector=injector).run()
        vals = [e["aux_var"] for e in sector._compute_log]
        # Should see overridden value
        assert any(v == 777.0 for v in vals)


class TestExogenousMissingKey:
    def test_silently_ignored(self) -> None:
        """Unknown keys in exogenous overrides are silently ignored."""
        def injector(t: float) -> dict[str, float]:
            return {"totally_nonexistent_variable": 42.0}

        # Should not raise
        r = _make_engine(exogenous_injector=injector).run()
        assert len(r.trajectories) > 0


class TestBuildExogenousInjector:
    def test_none_for_empty(self) -> None:
        s = Scenario(
            name="empty", description="", start_year=1900, end_year=2100
        )
        assert build_exogenous_injector(s) is None

    def test_interpolation_at_non_integer_t(self) -> None:
        scenario = Scenario(
            name="interp",
            description="",
            start_year=1900,
            end_year=2100,
            exogenous_overrides={
                "some_var": pd.Series([100.0, 200.0], index=[0.0, 10.0]),
            },
        )
        injector = build_exogenous_injector(scenario)
        assert injector is not None
        result = injector(5.0)
        assert abs(result["some_var"] - 150.0) < 1e-10

    def test_clamp_before_range(self) -> None:
        scenario = Scenario(
            name="clamp",
            description="",
            start_year=1900,
            end_year=2100,
            exogenous_overrides={
                "x": pd.Series([10.0, 20.0], index=[5.0, 15.0]),
            },
        )
        injector = build_exogenous_injector(scenario)
        assert injector is not None
        assert injector(0.0)["x"] == 10.0  # clamped to first value

    def test_clamp_after_range(self) -> None:
        scenario = Scenario(
            name="clamp",
            description="",
            start_year=1900,
            end_year=2100,
            exogenous_overrides={
                "x": pd.Series([10.0, 20.0], index=[5.0, 15.0]),
            },
        )
        injector = build_exogenous_injector(scenario)
        assert injector is not None
        assert injector(100.0)["x"] == 20.0  # clamped to last value
