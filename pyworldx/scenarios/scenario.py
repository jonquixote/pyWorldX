"""Scenario management (Section 11).

PolicyEvent: STEP/RAMP/PULSE/CUSTOM policy interventions
Scenario: bundles parameter overrides + policy events + metadata
ScenarioRunner: parallel scenario execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import pandas as pd


class PolicyShape(Enum):
    """Shape of a policy intervention."""

    STEP = "step"
    RAMP = "ramp"
    PULSE = "pulse"
    CUSTOM = "custom"


@dataclass
class PolicyEvent:
    """A single policy intervention (Section 11.1).

    Attributes:
        target: variable or parameter name affected
        shape: type of intervention
        t_start: start time of intervention
        t_end: end time (None = permanent for STEP)
        magnitude: size of change (STEP/PULSE)
        rate: rate of change (RAMP)
        custom_fn: custom transformation (CUSTOM shape)
        description: human-readable description
    """

    target: str
    shape: PolicyShape
    t_start: float
    t_end: float | None = None
    magnitude: float | None = None
    rate: float | None = None
    custom_fn: Callable[[float, float], float] | None = None
    description: str = ""

    def apply(self, baseline_value: float, t: float) -> float:
        """Apply this policy to a baseline value at time t.

        Returns:
            Modified value after policy application
        """
        if t < self.t_start:
            return baseline_value

        if self.shape == PolicyShape.STEP:
            if self.t_end is not None and t > self.t_end:
                return baseline_value
            mag = self.magnitude if self.magnitude is not None else 0.0
            return baseline_value + mag

        if self.shape == PolicyShape.RAMP:
            r = self.rate if self.rate is not None else 0.0
            t_end = self.t_end if self.t_end is not None else t
            elapsed = min(t - self.t_start, t_end - self.t_start)
            return baseline_value + r * elapsed

        if self.shape == PolicyShape.PULSE:
            if self.t_end is not None and t > self.t_end:
                return baseline_value
            mag = self.magnitude if self.magnitude is not None else 0.0
            return baseline_value + mag

        if self.shape == PolicyShape.CUSTOM:
            if self.custom_fn is not None:
                return self.custom_fn(baseline_value, t)

        return baseline_value


@dataclass
class Scenario:
    """A named scenario configuration (Section 11.2).

    Every override is typed, dated, and recorded in provenance.
    """

    name: str
    description: str
    start_year: int
    end_year: int
    parameter_overrides: dict[str, float] = field(default_factory=dict)
    exogenous_overrides: dict[str, "pd.Series[Any]"] = field(
        default_factory=dict
    )
    policy_events: list[PolicyEvent] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def apply_policies(
        self, values: dict[str, float], t: float
    ) -> dict[str, float]:
        """Apply all policy events to current values at time t."""
        result = dict(values)
        for event in self.policy_events:
            if event.target in result:
                result[event.target] = event.apply(
                    result[event.target], t
                )
        return result

    @classmethod
    def from_preset(
        cls,
        preset_name: str,
        name: str | None = None,
        start_year: int = 1900,
        end_year: int = 2100,
        extra_overrides: dict[str, float] | None = None,
        policy_events: list[PolicyEvent] | None = None,
        tags: list[str] | None = None,
    ) -> "Scenario":
        """Create a Scenario from a ModelPreset.

        Merges the preset's parameter overrides with any extra_overrides.
        Extra overrides take precedence over the preset.

        Args:
            preset_name: Name of the preset (e.g., "world3_03", "nebel_2024")
            name: Scenario name (defaults to preset name)
            start_year: Simulation start year
            end_year: Simulation end year
            extra_overrides: Additional parameter overrides on top of preset
            policy_events: Policy events to apply
            tags: Scenario tags
        """
        from pyworldx.presets import get_preset

        preset = get_preset(preset_name)
        overrides = dict(preset.parameter_overrides)
        if extra_overrides:
            overrides.update(extra_overrides)

        return cls(
            name=name or f"{preset.name}_scenario",
            description=f"Scenario from preset: {preset.description}",
            start_year=start_year,
            end_year=end_year,
            parameter_overrides=overrides,
            policy_events=policy_events or [],
            tags=tags or [preset.name],
        )


def apply_parameter_overrides(scenario: "Scenario", sectors: list[Any]) -> None:
    """Mutate sector instances in-place with scenario.parameter_overrides.

    Format: "{sector_name}.{attr}" → value
    Silently skips unknown sectors or attributes.
    """
    for dotted_key, value in scenario.parameter_overrides.items():
        if "." not in dotted_key:
            continue
        sector_name, attr = dotted_key.split(".", 1)
        target = next((s for s in sectors if s.name == sector_name), None)
        if target is None:
            continue
        if hasattr(target, attr):
            setattr(target, attr, value)


# ── Built-in scenarios (Section 11.3) ────────────────────────────────


def baseline_world3() -> Scenario:
    """Standard World3-03 baseline — no interventions."""
    return Scenario(
        name="baseline_world3",
        description="World3-03 standard run with default parameters",
        start_year=1900,
        end_year=2100,
        tags=["baseline", "world3"],
    )


def high_resource_discovery() -> Scenario:
    """Double the initial NR stock."""
    return Scenario(
        name="high_resource_discovery",
        description="Non-renewable resources doubled by discovery",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"resources.initial_nr": 2.0e12},
        tags=["resource", "optimistic"],
    )


def pollution_control_push() -> Scenario:
    """Halve industrial pollution intensity starting year 50."""
    return Scenario(
        name="pollution_control_push",
        description="Industrial pollution intensity halved via regulation",
        start_year=1900,
        end_year=2100,
        policy_events=[
            PolicyEvent(
                target="pollution_index",
                shape=PolicyShape.STEP,
                t_start=50.0,
                magnitude=-0.005,
                description="Halve industrial pollution intensity by 2050",
            )
        ],
        tags=["pollution", "intervention"],
    )


def agricultural_efficiency_push() -> Scenario:
    """Increase land yield base by 50% via technology."""
    return Scenario(
        name="agricultural_efficiency_push",
        description="Agricultural yield improvement from green revolution",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"agriculture.land_yield_base": 900.0},
        tags=["agriculture", "technology"],
    )


def capital_reallocation_to_maintenance() -> Scenario:
    """Lower depreciation rate by investing in maintenance."""
    return Scenario(
        name="capital_reallocation_to_maintenance",
        description="Capital reallocation: lower depreciation through maintenance",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"capital.alic": 33.0},  # longer life = lower depreciation
        tags=["capital", "maintenance"],
    )


def wiliam_high_military_drag() -> Scenario:
    """WILIAM scenario: high military spending drags productive capital."""
    return Scenario(
        name="wiliam_high_military_drag",
        description="Military spending increased to 5% of output, crowding out productive investment",
        start_year=1900,
        end_year=2100,
        parameter_overrides={"wiliam_economy.military_fraction": 0.05},
        tags=["wiliam", "military", "drag"],
    )


# Collection of all built-in scenarios (Section 11.3)
BUILTIN_SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "baseline_world3": baseline_world3,
    "high_resource_discovery": high_resource_discovery,
    "pollution_control_push": pollution_control_push,
    "agricultural_efficiency_push": agricultural_efficiency_push,
    "capital_reallocation_to_maintenance": capital_reallocation_to_maintenance,
    "wiliam_high_military_drag": wiliam_high_military_drag,
}
