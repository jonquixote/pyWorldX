"""Full calibration pipeline (Section 9.3).

Step 0: Structural identifiability pre-screen (profile likelihood)
Step 1: Morris elementary effects screening
Step 2: Deterministic calibration (NRMSD optimization)
Step 3: Sobol variance decomposition

This module ties together parameters, metrics, and sensitivity
into the complete calibration workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from pyworldx.calibration.metrics import (
    CalibrationResult,
    CrossValidationConfig,
)
from pyworldx.calibration.parameters import ParameterRegistry
from pyworldx.calibration.sensitivity import (
    IdentifiabilityReport,
    MorrisResult,
    SobolResult,
    run_morris_screening,
    run_profile_likelihood,
    run_sobol_analysis,
)


@dataclass
class PipelineReport:
    """Full calibration pipeline report."""

    identifiability: IdentifiabilityReport | None = None
    morris: MorrisResult | None = None
    calibration: CalibrationResult | None = None
    sobol: SobolResult | None = None
    screened_parameters: list[str] = field(default_factory=list)
    fixed_parameters: dict[str, float] = field(default_factory=dict)
    total_evaluations: int = 0


def _nelder_mead_optimize(
    objective_fn: Callable[[dict[str, float]], float],
    initial_params: dict[str, float],
    bounds: dict[str, tuple[float, float]],
    parameter_names: list[str],
    max_iter: int = 200,
    tol: float = 1e-6,
    seed: int = 42,
) -> tuple[dict[str, float], float, int, bool]:
    """Bounded Nelder-Mead optimization.

    Uses simplex method with reflection/expansion/contraction
    in normalized [0,1] space, then maps back to parameter bounds.

    Returns:
        (best_params, best_objective, iterations, converged)
    """
    n = len(parameter_names)

    # Normalize to [0, 1]
    def _to_unit(params: dict[str, float]) -> "np.ndarray[Any, Any]":
        x = np.zeros(n)
        for i, name in enumerate(parameter_names):
            lo, hi = bounds[name]
            x[i] = (params[name] - lo) / max(hi - lo, 1e-15)
        return np.clip(x, 0.0, 1.0)

    def _from_unit(x: "np.ndarray[Any, Any]") -> dict[str, float]:
        params = dict(initial_params)
        for i, name in enumerate(parameter_names):
            lo, hi = bounds[name]
            params[name] = lo + np.clip(x[i], 0.0, 1.0) * (hi - lo)
        return params

    def _eval(x: "np.ndarray[Any, Any]") -> float:
        return objective_fn(_from_unit(x))

    # Initialize simplex
    x0 = _to_unit(initial_params)
    simplex = np.zeros((n + 1, n))
    simplex[0] = x0
    for i in range(n):
        xi = x0.copy()
        xi[i] = min(1.0, xi[i] + 0.1) if xi[i] < 0.5 else max(0.0, xi[i] - 0.1)
        simplex[i + 1] = xi

    f_vals = np.array([_eval(simplex[i]) for i in range(n + 1)])

    alpha = 1.0  # reflection
    gamma = 2.0  # expansion
    rho = 0.5  # contraction
    sigma = 0.5  # shrink

    converged = False
    iteration = 0

    for iteration in range(max_iter):
        # Sort
        order = np.argsort(f_vals)
        simplex = simplex[order]
        f_vals = f_vals[order]

        # Check convergence
        if np.max(f_vals) - np.min(f_vals) < tol:
            converged = True
            break

        # Centroid (excluding worst)
        centroid = np.mean(simplex[:-1], axis=0)

        # Reflection
        xr = np.clip(centroid + alpha * (centroid - simplex[-1]), 0.0, 1.0)
        fr = _eval(xr)

        if f_vals[0] <= fr < f_vals[-2]:
            simplex[-1] = xr
            f_vals[-1] = fr
            continue

        # Expansion
        if fr < f_vals[0]:
            xe = np.clip(centroid + gamma * (xr - centroid), 0.0, 1.0)
            fe = _eval(xe)
            if fe < fr:
                simplex[-1] = xe
                f_vals[-1] = fe
            else:
                simplex[-1] = xr
                f_vals[-1] = fr
            continue

        # Contraction
        xc = np.clip(centroid + rho * (simplex[-1] - centroid), 0.0, 1.0)
        fc = _eval(xc)
        if fc < f_vals[-1]:
            simplex[-1] = xc
            f_vals[-1] = fc
            continue

        # Shrink
        for i in range(1, n + 1):
            simplex[i] = np.clip(
                simplex[0] + sigma * (simplex[i] - simplex[0]), 0.0, 1.0
            )
            f_vals[i] = _eval(simplex[i])

    best_idx = np.argmin(f_vals)
    best_params = _from_unit(simplex[best_idx])
    return best_params, float(f_vals[best_idx]), iteration + 1, converged


def run_calibration_pipeline(
    objective_fn: Callable[[dict[str, float]], float],
    registry: ParameterRegistry,
    cross_val_config: CrossValidationConfig | None = None,
    morris_trajectories: int = 10,
    morris_threshold: float = 0.9,
    sobol_samples: int = 256,
    profile_grid: int = 20,
    optimize_max_iter: int = 200,
    optimize_tol: float = 1e-6,
    seed: int = 42,
) -> PipelineReport:
    """Run the full calibration pipeline (Section 9.3).

    Step 0: Profile likelihood identifiability pre-screen
    Step 1: Morris elementary effects screening
    Step 2: Deterministic NRMSD optimization (Nelder-Mead)
    Step 3: Sobol variance decomposition

    Args:
        objective_fn: maps parameter dict → scalar NRMSD objective
        registry: parameter registry with bounds
        cross_val_config: train/validate configuration
        morris_trajectories: number of Morris trajectories
        morris_threshold: fraction of variance to retain
        sobol_samples: base sample size for Sobol
        profile_grid: grid points for profile likelihood
        optimize_max_iter: max optimizer iterations
        optimize_tol: optimizer convergence tolerance
        seed: random seed

    Returns:
        PipelineReport with all intermediate results
    """
    report = PipelineReport()

    if cross_val_config is None:
        cross_val_config = CrossValidationConfig()

    all_names = [e.name for e in registry.all_entries()]
    defaults = registry.get_defaults()
    bounds = registry.get_bounds()

    # ── Step 0: Profile likelihood pre-screen ────────────────────────
    risky = registry.get_risky_parameters()
    if risky:
        report.identifiability = run_profile_likelihood(
            objective_fn,
            registry,
            parameter_names=[p.name for p in risky],
            grid_resolution=profile_grid,
        )
        report.total_evaluations += report.identifiability.total_evaluations

        # Fix non-identifiable parameters at literature defaults
        non_id = report.identifiability.get_non_identifiable()
        for name in non_id:
            report.fixed_parameters[name] = defaults[name]

    # Active parameters = all minus fixed
    active_names = [n for n in all_names if n not in report.fixed_parameters]

    # ── Step 1: Morris screening ─────────────────────────────────────
    report.morris = run_morris_screening(
        objective_fn,
        registry,
        parameter_names=active_names,
        n_trajectories=morris_trajectories,
        seed=seed,
    )
    report.total_evaluations += len(active_names) * morris_trajectories

    # Retain influential parameters
    report.screened_parameters = report.morris.get_influential(
        threshold_fraction=morris_threshold
    )

    # ── Step 2: Deterministic optimization ───────────────────────────
    # Start from defaults, optimize only screened parameters
    initial = dict(defaults)
    best_params, best_obj, iters, converged = _nelder_mead_optimize(
        objective_fn,
        initial,
        bounds,
        report.screened_parameters,
        max_iter=optimize_max_iter,
        tol=optimize_tol,
        seed=seed,
    )
    report.total_evaluations += iters * (len(report.screened_parameters) + 1)

    report.calibration = CalibrationResult(
        parameters=best_params,
        nrmsd_scores={},  # caller fills per-variable scores
        total_nrmsd=best_obj,
        train_config=cross_val_config,
        iterations=iters,
        converged=converged,
    )

    # ── Step 3: Sobol analysis on screened set ───────────────────────
    report.sobol = run_sobol_analysis(
        objective_fn,
        registry,
        parameter_names=report.screened_parameters,
        n_samples=sobol_samples,
        seed=seed,
    )
    n_sobol = sobol_samples * (2 * len(report.screened_parameters) + 2)
    report.total_evaluations += n_sobol

    return report
