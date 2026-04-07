"""Ensemble forecasting layer (Section 10).

Repeatedly executes the deterministic engine under controlled
perturbations and summarizes the forecast distribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from pyworldx.core.result import RunResult
from pyworldx.scenarios.scenario import Scenario


class UncertaintyType(Enum):
    """Uncertainty classes (Section 10.2)."""

    PARAMETER = "parameter"
    SCENARIO = "scenario"
    EXOGENOUS_INPUT = "exogenous_input"
    INITIAL_CONDITION = "initial_condition"
    STRUCTURAL_NOTE = "structural_note"


class DistributionType(Enum):
    """Supported distribution types (Section 10.3)."""

    UNIFORM = "uniform"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    TRUNCATED_NORMAL = "truncated_normal"


@dataclass
class ParameterDistribution:
    """Distribution spec for a single parameter (Section 10.3)."""

    dist_type: DistributionType
    params: dict[str, float]
    seed_stream: str
    uncertainty_type: UncertaintyType  # mandatory — no default

    def sample(
        self, rng: np.random.Generator, n: int = 1
    ) -> "np.ndarray[Any, Any]":
        """Draw n samples from this distribution."""
        if self.dist_type == DistributionType.UNIFORM:
            lo = self.params.get("low", 0.0)
            hi = self.params.get("high", 1.0)
            return rng.uniform(lo, hi, n)

        if self.dist_type == DistributionType.NORMAL:
            mu = self.params.get("mean", 0.0)
            sd = self.params.get("std", 1.0)
            return rng.normal(mu, sd, n)

        if self.dist_type == DistributionType.LOGNORMAL:
            mu = self.params.get("mean", 0.0)
            sd = self.params.get("sigma", 1.0)
            return rng.lognormal(mu, sd, n)

        if self.dist_type == DistributionType.TRUNCATED_NORMAL:
            mu = self.params.get("mean", 0.0)
            sd = self.params.get("std", 1.0)
            lo = self.params.get("low", mu - 3 * sd)
            hi = self.params.get("high", mu + 3 * sd)
            samples = rng.normal(mu, sd, n * 3)  # oversample
            clipped = samples[(samples >= lo) & (samples <= hi)]
            if len(clipped) >= n:
                return clipped[:n]
            # Fallback: clip
            return np.clip(rng.normal(mu, sd, n), lo, hi)

        raise ValueError(f"Unknown distribution type: {self.dist_type}")


@dataclass(frozen=True)
class ThresholdQuery:
    """A threshold query declared in EnsembleSpec (Section 10.4)."""

    name: str
    variable: str
    op: str  # "below" | "above" | "crosses"
    threshold: float
    by_year: int
    unit: str | None = None


@dataclass
class ThresholdQueryResult:
    """Result of evaluating a threshold query."""

    query: ThresholdQuery
    probability: float
    member_count: int


class UndeclaredThresholdQueryError(KeyError):
    """Raised when accessing an undeclared threshold query."""


@dataclass
class EnsembleSpec:
    """Specification for an ensemble run (Section 10.5)."""

    n_runs: int
    base_scenario: Scenario
    parameter_distributions: dict[str, ParameterDistribution]
    exogenous_perturbations: dict[str, ParameterDistribution] = field(
        default_factory=dict
    )
    initial_condition_perturbations: dict[str, ParameterDistribution] = field(
        default_factory=dict
    )
    threshold_queries: list[ThresholdQuery] = field(default_factory=list)
    seed: int = 42
    store_member_runs: bool = False


@dataclass
class EnsembleResult:
    """Result of an ensemble run (Section 10.6)."""

    members: list[RunResult] | None
    summary: dict[str, pd.DataFrame]
    threshold_results: dict[str, ThresholdQueryResult]
    uncertainty_decomposition: dict[str, dict[str, float]]
    manifest_refs: list[str] = field(default_factory=list)

    def probability_of_threshold(self, query_name: str) -> float:
        """Access threshold probability (Section 10.7)."""
        if query_name not in self.threshold_results:
            raise UndeclaredThresholdQueryError(
                f"Threshold query '{query_name}' was not declared in EnsembleSpec. "
                f"Re-run the ensemble with the query declared."
            )
        return self.threshold_results[query_name].probability


def run_ensemble(
    spec: EnsembleSpec,
    sector_factory: Any,
    engine_kwargs: dict[str, Any] | None = None,
) -> EnsembleResult:
    """Execute an ensemble of model runs.

    Args:
        spec: EnsembleSpec defining perturbations and queries
        sector_factory: callable(parameter_overrides) -> list[sector]
        engine_kwargs: additional kwargs for Engine

    Returns:
        EnsembleResult with summary statistics and threshold results
    """
    from pyworldx.core.engine import Engine

    if engine_kwargs is None:
        engine_kwargs = {}

    rng = np.random.default_rng(spec.seed)
    members: list[RunResult] = []
    all_trajectories: dict[str, list["np.ndarray[Any, Any]"]] = {}

    # Pre-sample all perturbations
    param_samples: dict[str, "np.ndarray[Any, Any]"] = {}
    for name, dist in spec.parameter_distributions.items():
        param_samples[name] = dist.sample(rng, spec.n_runs)

    ic_samples: dict[str, "np.ndarray[Any, Any]"] = {}
    for name, dist in spec.initial_condition_perturbations.items():
        ic_samples[name] = dist.sample(rng, spec.n_runs)

    # Run ensemble members
    for i in range(spec.n_runs):
        # Build parameter overrides for this member
        overrides = dict(spec.base_scenario.parameter_overrides)
        for name, samples in param_samples.items():
            overrides[name] = float(samples[i])

        # Build sectors and run
        sectors = sector_factory(overrides)
        engine = Engine(
            sectors=sectors,
            t_start=float(spec.base_scenario.start_year - 1900),
            t_end=float(spec.base_scenario.end_year - 1900),
            **engine_kwargs,
        )
        result = engine.run()

        if spec.store_member_runs:
            members.append(result)

        # Accumulate trajectories
        for var_name, traj in result.trajectories.items():
            if var_name not in all_trajectories:
                all_trajectories[var_name] = []
            all_trajectories[var_name].append(traj)

    # ── Compute summary statistics (Section 10.6) ────────────────────
    summary: dict[str, pd.DataFrame] = {}
    for var_name, traj_list in all_trajectories.items():
        arr = np.array(traj_list)  # (n_runs, n_timesteps)
        summary[var_name] = pd.DataFrame({
            "mean": np.mean(arr, axis=0),
            "median": np.median(arr, axis=0),
            "p05": np.percentile(arr, 5, axis=0),
            "p25": np.percentile(arr, 25, axis=0),
            "p75": np.percentile(arr, 75, axis=0),
            "p95": np.percentile(arr, 95, axis=0),
            "min": np.min(arr, axis=0),
            "max": np.max(arr, axis=0),
        })

    # ── Evaluate threshold queries ───────────────────────────────────
    threshold_results: dict[str, ThresholdQueryResult] = {}
    for query in spec.threshold_queries:
        if query.variable not in all_trajectories:
            threshold_results[query.name] = ThresholdQueryResult(
                query=query, probability=0.0, member_count=0
            )
            continue

        traj_list = all_trajectories[query.variable]
        # Find time index for by_year
        t_start = spec.base_scenario.start_year
        year_idx = query.by_year - t_start
        hits = 0
        for traj in traj_list:
            if year_idx < 0 or year_idx >= len(traj):
                continue
            val = traj[year_idx]
            if query.op == "below" and val < query.threshold:
                hits += 1
            elif query.op == "above" and val > query.threshold:
                hits += 1
            elif query.op == "crosses":
                # Check if trajectory crosses threshold before by_year
                sub = traj[: year_idx + 1]
                crossed = np.any(
                    (sub[:-1] - query.threshold)
                    * (sub[1:] - query.threshold)
                    < 0
                )
                if crossed:
                    hits += 1

        threshold_results[query.name] = ThresholdQueryResult(
            query=query,
            probability=hits / max(len(traj_list), 1),
            member_count=hits,
        )

    # ── Uncertainty decomposition (simplified) ───────────────────────
    decomposition: dict[str, dict[str, float]] = {}
    # TODO: Full decomposition requires tagged runs; for now report
    # total variance attributable to parameter perturbations
    for var_name, traj_list in all_trajectories.items():
        arr = np.array(traj_list)
        total_var = float(np.var(arr[:, -1]))  # variance at final time
        decomposition[var_name] = {
            "parameter": total_var,
            "scenario": 0.0,
            "exogenous_input": 0.0,
            "initial_condition": 0.0,
        }

    return EnsembleResult(
        members=members if spec.store_member_runs else None,
        summary=summary,
        threshold_results=threshold_results,
        uncertainty_decomposition=decomposition,
    )
