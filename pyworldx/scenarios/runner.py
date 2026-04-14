"""Parallel scenario runner (Section 11.4).

Executes multiple scenarios against a common model definition
and emits harmonized RunResult sets.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from pyworldx.core.result import RunResult
from pyworldx.scenarios.scenario import Scenario


@dataclass
class ScenarioRunResult:
    """Result of running a single scenario."""

    scenario_name: str
    result: RunResult
    parameter_overrides: dict[str, float]
    tags: list[str]


@dataclass
class ScenarioSuiteResult:
    """Result of running a suite of scenarios."""

    results: dict[str, ScenarioRunResult] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def n_completed(self) -> int:
        return len(self.results)

    @property
    def n_failed(self) -> int:
        return len(self.failed)


def build_policy_applier(
    scenario: Scenario,
) -> Callable[[dict[str, float], float], dict[str, float]] | None:
    """Build a policy applier callable from a Scenario's policy events."""
    if not scenario.policy_events:
        return None

    def applier(values: dict[str, float], t: float) -> dict[str, float]:
        return scenario.apply_policies(values, t)

    return applier


def build_exogenous_injector(
    scenario: Scenario,
) -> Callable[[float], dict[str, float]] | None:
    """Build an exogenous injector callable from a Scenario's exogenous overrides."""
    if not scenario.exogenous_overrides:
        return None

    def injector(t: float) -> dict[str, float]:
        result: dict[str, float] = {}
        for name, series in scenario.exogenous_overrides.items():
            idx = series.index
            if t <= idx.min():
                result[name] = float(series.iloc[0])
            elif t >= idx.max():
                result[name] = float(series.iloc[-1])
            else:
                result[name] = float(
                    np.interp(t, idx.astype(float), np.asarray(series.values, dtype=float))
                )
        return result

    return injector


def _run_single_scenario(
    scenario: Scenario,
    sector_factory: Any,
    engine_kwargs: dict[str, Any],
) -> ScenarioRunResult:
    """Run a single scenario (picklable for multiprocessing)."""
    from pyworldx.core.engine import Engine

    sectors = sector_factory(scenario.parameter_overrides)
    engine = Engine(
        sectors=sectors,
        t_start=float(scenario.start_year - 1900),
        t_end=float(scenario.end_year - 1900),
        policy_applier=build_policy_applier(scenario),
        exogenous_injector=build_exogenous_injector(scenario),
        **engine_kwargs,
    )
    result = engine.run()
    return ScenarioRunResult(
        scenario_name=scenario.name,
        result=result,
        parameter_overrides=scenario.parameter_overrides,
        tags=scenario.tags,
    )


def run_scenarios(
    scenarios: list[Scenario],
    sector_factory: Any,
    engine_kwargs: dict[str, Any] | None = None,
    max_workers: int = 1,
) -> ScenarioSuiteResult:
    """Run multiple scenarios, optionally in parallel.

    Args:
        scenarios: list of Scenario objects to execute
        sector_factory: callable(parameter_overrides) -> list[sector]
        engine_kwargs: additional kwargs for Engine (master_dt, etc.)
        max_workers: number of parallel workers (1 = serial)

    Returns:
        ScenarioSuiteResult with per-scenario results
    """
    if engine_kwargs is None:
        engine_kwargs = {}

    suite = ScenarioSuiteResult()

    if max_workers <= 1:
        # Serial execution
        for scenario in scenarios:
            try:
                sr = _run_single_scenario(
                    scenario, sector_factory, engine_kwargs
                )
                suite.results[scenario.name] = sr
            except Exception as e:
                suite.failed[scenario.name] = str(e)
    else:
        # Parallel execution
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _run_single_scenario,
                    scenario,
                    sector_factory,
                    engine_kwargs,
                ): scenario
                for scenario in scenarios
            }
            for future in as_completed(futures):
                scenario = futures[future]
                try:
                    sr = future.result()
                    suite.results[scenario.name] = sr
                except Exception as e:
                    suite.failed[scenario.name] = str(e)

    return suite
