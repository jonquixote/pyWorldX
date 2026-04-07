"""Tests for scenario management."""

from __future__ import annotations

from pyworldx.scenarios.scenario import (
    BUILTIN_SCENARIOS,
    PolicyEvent,
    PolicyShape,
    Scenario,
    baseline_world3,
)


class TestPolicyEvent:
    def test_step_before_start(self) -> None:
        pe = PolicyEvent("x", PolicyShape.STEP, t_start=50.0, magnitude=10.0)
        assert pe.apply(100.0, 30.0) == 100.0

    def test_step_after_start(self) -> None:
        pe = PolicyEvent("x", PolicyShape.STEP, t_start=50.0, magnitude=10.0)
        assert pe.apply(100.0, 60.0) == 110.0

    def test_step_with_end(self) -> None:
        pe = PolicyEvent(
            "x", PolicyShape.STEP, t_start=50.0, t_end=80.0, magnitude=10.0
        )
        assert pe.apply(100.0, 60.0) == 110.0
        assert pe.apply(100.0, 90.0) == 100.0  # after t_end

    def test_ramp(self) -> None:
        pe = PolicyEvent(
            "x", PolicyShape.RAMP, t_start=10.0, t_end=20.0, rate=5.0
        )
        assert pe.apply(100.0, 5.0) == 100.0  # before start
        assert pe.apply(100.0, 15.0) == 125.0  # 5 years * rate 5
        assert pe.apply(100.0, 25.0) == 150.0  # capped at t_end-t_start=10

    def test_pulse(self) -> None:
        pe = PolicyEvent(
            "x", PolicyShape.PULSE, t_start=10.0, t_end=15.0, magnitude=50.0
        )
        assert pe.apply(100.0, 12.0) == 150.0
        assert pe.apply(100.0, 20.0) == 100.0

    def test_custom(self) -> None:
        pe = PolicyEvent(
            "x",
            PolicyShape.CUSTOM,
            t_start=0.0,
            custom_fn=lambda base, t: base * (1 + t / 100),
        )
        assert pe.apply(100.0, 50.0) == 150.0


class TestScenario:
    def test_baseline(self) -> None:
        s = baseline_world3()
        assert s.name == "baseline_world3"
        assert len(s.parameter_overrides) == 0

    def test_apply_policies(self) -> None:
        s = Scenario(
            name="test",
            description="test",
            start_year=1900,
            end_year=2100,
            policy_events=[
                PolicyEvent("x", PolicyShape.STEP, t_start=50.0, magnitude=10.0)
            ],
        )
        result = s.apply_policies({"x": 100.0, "y": 200.0}, t=60.0)
        assert result["x"] == 110.0
        assert result["y"] == 200.0

    def test_builtin_scenarios(self) -> None:
        assert len(BUILTIN_SCENARIOS) >= 5
        for name, factory in BUILTIN_SCENARIOS.items():
            s = factory()
            assert s.name == name
            assert s.start_year < s.end_year
