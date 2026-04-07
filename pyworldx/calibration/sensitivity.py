"""Sensitivity analysis: Morris screening and Sobol indices (Section 9.3).

Step 1: SALib Morris elementary effects screening
Step 3: First-order + total-order Sobol variance decomposition
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from pyworldx.calibration.parameters import ParameterRegistry


@dataclass
class MorrisResult:
    """Morris elementary effects screening result."""

    parameter_names: list[str]
    mu_star: dict[str, float]  # absolute mean of elementary effects
    sigma: dict[str, float]  # standard deviation of effects
    ranking: list[str]  # parameters ranked by mu_star descending

    def get_influential(
        self, threshold_fraction: float = 0.9
    ) -> list[str]:
        """Return parameters driving the given fraction of total mu_star."""
        total = sum(self.mu_star.values())
        if total <= 0:
            return list(self.parameter_names)

        cumulative = 0.0
        result: list[str] = []
        for name in self.ranking:
            cumulative += self.mu_star[name]
            result.append(name)
            if cumulative / total >= threshold_fraction:
                break
        return result


@dataclass
class SobolResult:
    """Sobol variance decomposition result."""

    parameter_names: list[str]
    s1: dict[str, float]  # first-order indices
    st: dict[str, float]  # total-order indices
    s1_conf: dict[str, float]  # confidence intervals for S1
    st_conf: dict[str, float]  # confidence intervals for ST
    interaction_notes: list[str] = field(default_factory=list)

    def get_dominant_parameters(
        self, st_threshold: float = 0.05
    ) -> list[str]:
        """Return parameters with total-order index above threshold."""
        return [
            name
            for name in self.parameter_names
            if self.st.get(name, 0.0) > st_threshold
        ]


@dataclass
class IdentifiabilityResult:
    """Profile likelihood identifiability result (Section 9.6)."""

    parameter: str
    grid_values: list[float]
    profile_objectives: list[float]
    classification: str  # "identifiable", "flat_plateau", "threshold_gated"
    min_objective: float
    range_ratio: float  # max/min of profile — flat means non-identifiable


@dataclass
class IdentifiabilityReport:
    """Full identifiability screening report."""

    results: list[IdentifiabilityResult]
    total_evaluations: int
    grid_resolution: int = 20

    def get_identifiable(self) -> list[str]:
        """Return identifiable parameters."""
        return [
            r.parameter
            for r in self.results
            if r.classification == "identifiable"
        ]

    def get_non_identifiable(self) -> list[str]:
        """Return non-identifiable parameters (fix at literature)."""
        return [
            r.parameter
            for r in self.results
            if r.classification in ("flat_plateau", "threshold_gated")
        ]


def run_morris_screening(
    objective_fn: Callable[[dict[str, float]], float],
    registry: ParameterRegistry,
    parameter_names: list[str] | None = None,
    n_trajectories: int = 10,
    n_levels: int = 4,
    seed: int = 42,
) -> MorrisResult:
    """Run Morris elementary effects screening.

    Args:
        objective_fn: function mapping parameter dict → scalar objective
        registry: parameter registry with bounds
        parameter_names: subset to screen (None = all)
        n_trajectories: number of Morris trajectories
        n_levels: number of levels in the grid
        seed: random seed

    Returns:
        MorrisResult with mu_star, sigma, and ranking
    """
    rng = np.random.default_rng(seed)
    names = parameter_names or [e.name for e in registry.all_entries()]
    bounds = registry.get_bounds()
    defaults = registry.get_defaults()
    k = len(names)

    # Generate Morris trajectories (simplified OAT design)
    delta = 1.0 / (n_levels - 1) if n_levels > 1 else 0.5
    effects: dict[str, list[float]] = {name: [] for name in names}

    for _ in range(n_trajectories):
        # Random base point in [0, 1]^k
        x0 = rng.random(k)
        # Map to parameter space
        params_base = dict(defaults)
        for i, name in enumerate(names):
            lo, hi = bounds[name]
            params_base[name] = lo + x0[i] * (hi - lo)

        f0 = objective_fn(params_base)

        # Perturb each parameter one at a time
        for i, name in enumerate(names):
            params_pert = dict(params_base)
            lo, hi = bounds[name]
            x_new = min(1.0, x0[i] + delta)
            if x_new == x0[i]:
                x_new = max(0.0, x0[i] - delta)
            params_pert[name] = lo + x_new * (hi - lo)

            f1 = objective_fn(params_pert)
            ee = (f1 - f0) / delta
            effects[name].append(ee)

    # Compute mu_star and sigma
    mu_star: dict[str, float] = {}
    sigma: dict[str, float] = {}
    for name in names:
        vals = np.array(effects[name])
        mu_star[name] = float(np.mean(np.abs(vals)))
        sigma[name] = float(np.std(vals))

    # Rank by mu_star descending
    ranking = sorted(names, key=lambda n: mu_star[n], reverse=True)

    return MorrisResult(
        parameter_names=names,
        mu_star=mu_star,
        sigma=sigma,
        ranking=ranking,
    )


def run_sobol_analysis(
    objective_fn: Callable[[dict[str, float]], float],
    registry: ParameterRegistry,
    parameter_names: list[str] | None = None,
    n_samples: int = 256,
    seed: int = 42,
) -> SobolResult:
    """Run Sobol sensitivity analysis.

    Computes first-order (S1) and total-order (ST) indices using
    the Saltelli sampling scheme.

    Args:
        objective_fn: function mapping parameter dict → scalar objective
        registry: parameter registry with bounds
        parameter_names: subset to analyze (None = all)
        n_samples: base sample size (total evals = N * (2k + 2))
        seed: random seed

    Returns:
        SobolResult with S1, ST indices and confidence intervals
    """
    rng = np.random.default_rng(seed)
    names = parameter_names or [e.name for e in registry.all_entries()]
    bounds = registry.get_bounds()
    defaults = registry.get_defaults()
    k = len(names)

    # Generate Saltelli samples: A, B matrices + AB_i recombinations
    a_matrix = rng.random((n_samples, k))
    b_matrix = rng.random((n_samples, k))

    def _eval_sample(sample: "np.ndarray[Any, Any]") -> float:
        params = dict(defaults)
        for i, name in enumerate(names):
            lo, hi = bounds[name]
            params[name] = lo + float(sample[i]) * (hi - lo)
        return objective_fn(params)

    # Evaluate A and B
    f_a = np.array([_eval_sample(a_matrix[j]) for j in range(n_samples)])
    f_b = np.array([_eval_sample(b_matrix[j]) for j in range(n_samples)])

    # Evaluate AB_i matrices
    f_ab: dict[str, "np.ndarray[Any, Any]"] = {}
    for i, name in enumerate(names):
        ab_i = np.copy(a_matrix)
        ab_i[:, i] = b_matrix[:, i]
        f_ab[name] = np.array(
            [_eval_sample(ab_i[j]) for j in range(n_samples)]
        )

    # Compute indices (Jansen estimator)
    var_total = float(np.var(np.concatenate([f_a, f_b])))
    if var_total < 1e-30:
        # All outputs are identical — no sensitivity
        return SobolResult(
            parameter_names=names,
            s1={n: 0.0 for n in names},
            st={n: 0.0 for n in names},
            s1_conf={n: 0.0 for n in names},
            st_conf={n: 0.0 for n in names},
        )

    s1: dict[str, float] = {}
    st: dict[str, float] = {}
    s1_conf: dict[str, float] = {}
    st_conf: dict[str, float] = {}

    for i, name in enumerate(names):
        f_ab_i = f_ab[name]

        # First-order: S1_i = V[E[Y|Xi]] / V[Y]
        s1_val = float(np.mean(f_b * (f_ab_i - f_a))) / var_total
        s1[name] = max(0.0, min(1.0, s1_val))

        # Total-order: ST_i = E[V[Y|X~i]] / V[Y]
        st_val = float(
            0.5 * np.mean((f_a - f_ab_i) ** 2)
        ) / var_total
        st[name] = max(0.0, min(1.0, st_val))

        # Bootstrap confidence (simplified: std error)
        n_boot = min(50, n_samples)
        boot_s1 = []
        boot_st = []
        for _ in range(n_boot):
            idx = rng.integers(0, n_samples, size=n_samples)
            bv = float(np.var(np.concatenate([f_a[idx], f_b[idx]])))
            if bv < 1e-30:
                continue
            bs1 = float(np.mean(f_b[idx] * (f_ab_i[idx] - f_a[idx]))) / bv
            bst = float(0.5 * np.mean((f_a[idx] - f_ab_i[idx]) ** 2)) / bv
            boot_s1.append(bs1)
            boot_st.append(bst)

        s1_conf[name] = float(np.std(boot_s1)) if boot_s1 else 0.0
        st_conf[name] = float(np.std(boot_st)) if boot_st else 0.0

    # Interaction notes
    interaction_notes: list[str] = []
    for name in names:
        gap = st[name] - s1[name]
        if gap > 0.1:
            interaction_notes.append(
                f"{name}: ST-S1={gap:.3f} suggests significant interactions"
            )

    return SobolResult(
        parameter_names=names,
        s1=s1,
        st=st,
        s1_conf=s1_conf,
        st_conf=st_conf,
        interaction_notes=interaction_notes,
    )


def run_profile_likelihood(
    objective_fn: Callable[[dict[str, float]], float],
    registry: ParameterRegistry,
    parameter_names: list[str] | None = None,
    grid_resolution: int = 20,
    flat_threshold: float = 0.10,
) -> IdentifiabilityReport:
    """Run profile likelihood identifiability screening (Section 9.6).

    For each parameter, fix it at grid points across its bounds and
    re-evaluate the objective. A flat profile indicates
    non-identifiability.

    Args:
        objective_fn: function mapping parameter dict → scalar objective
        registry: parameter registry with bounds
        parameter_names: subset to screen (None = risky parameters)
        grid_resolution: number of grid points per parameter
        flat_threshold: relative range below which a profile is "flat"

    Returns:
        IdentifiabilityReport
    """
    if parameter_names is None:
        risky = registry.get_risky_parameters()
        parameter_names = [p.name for p in risky]

    defaults = registry.get_defaults()
    bounds = registry.get_bounds()
    results: list[IdentifiabilityResult] = []
    total_evals = 0

    for name in parameter_names:
        lo, hi = bounds[name]
        grid = np.linspace(lo, hi, grid_resolution)
        profile: list[float] = []

        for val in grid:
            params = dict(defaults)
            params[name] = float(val)
            obj = objective_fn(params)
            profile.append(obj)
            total_evals += 1

        profile_arr = np.array(profile)
        min_obj = float(np.min(profile_arr))
        max_obj = float(np.max(profile_arr))
        range_ratio = (max_obj - min_obj) / max(abs(min_obj), 1e-15)

        if range_ratio < flat_threshold:
            classification = "flat_plateau"
        elif profile_arr[0] == min_obj or profile_arr[-1] == min_obj:
            classification = "threshold_gated"
        else:
            classification = "identifiable"

        results.append(IdentifiabilityResult(
            parameter=name,
            grid_values=[float(v) for v in grid],
            profile_objectives=profile,
            classification=classification,
            min_objective=min_obj,
            range_ratio=range_ratio,
        ))

    return IdentifiabilityReport(
        results=results,
        total_evaluations=total_evals,
        grid_resolution=grid_resolution,
    )
