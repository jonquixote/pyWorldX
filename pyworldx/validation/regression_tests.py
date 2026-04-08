"""Regression test utilities (Section 13.5).

Known reference scenarios are pinned so accidental structural
drift is caught immediately.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from pyworldx.core.result import RunResult


@dataclass
class RegressionCheckResult:
    """Result of a regression check against a reference trajectory."""

    variable: str
    max_relative_error: float
    max_absolute_error: float
    tolerance: float
    passed: bool
    worst_time: float = 0.0
    notes: str = ""


@dataclass
class RegressionReport:
    """Collection of regression check results."""

    reference_file: str
    results: list[RegressionCheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def n_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)


def load_reference_trajectory(
    path: str | Path,
) -> dict[str, "np.ndarray[Any, Any]"]:
    """Load a reference trajectory CSV.

    Expected format: columns [t, var1, var2, ...] with optional
    header comments starting with #.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Reference trajectory not found: {path}")

    data: dict[str, list[float]] = {}
    with open(path) as f:
        reader = csv.reader(f)
        headers: list[str] = []
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if not headers:
                headers = [h.strip() for h in row]
                for h in headers:
                    data[h] = []
                continue
            for i, val in enumerate(row):
                if i < len(headers):
                    data[headers[i]].append(float(val))

    return {k: np.array(v) for k, v in data.items()}


def check_regression(
    result: RunResult,
    reference: dict[str, "np.ndarray[Any, Any]"],
    variables: list[str] | None = None,
    relative_tol: float = 1e-4,
    absolute_tol: float = 1e-6,
    hybrid_crossover_time: float | None = None,
) -> RegressionReport:
    """Check model output against reference trajectory.

    Args:
        result: RunResult from engine
        reference: loaded reference trajectory
        variables: variables to check (None = all common)
        relative_tol: maximum relative error (for large values)
        absolute_tol: maximum absolute error (for near-zero values)
        hybrid_crossover_time: if set, use relative_tol for t <= crossover,
            absolute_tol for t > crossover (Section 17.4)

    Returns:
        RegressionReport
    """
    ref_file = "in-memory"
    report = RegressionReport(reference_file=ref_file)

    t_ref = reference.get("t")
    _t_model = result.time_index

    if t_ref is None:
        report.results.append(RegressionCheckResult(
            variable="t",
            max_relative_error=0.0,
            max_absolute_error=0.0,
            tolerance=relative_tol,
            passed=False,
            notes="No time column in reference",
        ))
        return report

    # Find common variables
    if variables is None:
        variables = [
            v for v in reference if v != "t" and v in result.trajectories
        ]

    for var in variables:
        if var not in reference or var not in result.trajectories:
            report.results.append(RegressionCheckResult(
                variable=var,
                max_relative_error=0.0,
                max_absolute_error=0.0,
                tolerance=relative_tol,
                passed=False,
                notes=f"Missing from {'reference' if var not in reference else 'model'}",
            ))
            continue

        ref_vals = reference[var]
        mod_vals = result.trajectories[var]

        # Align by minimum length
        n = min(len(ref_vals), len(mod_vals))
        ref_v = ref_vals[:n]
        mod_v = mod_vals[:n]
        t_v = t_ref[:n] if len(t_ref) >= n else np.arange(n)

        abs_err = np.abs(mod_v - ref_v)
        rel_err = np.where(
            np.abs(ref_v) > 1e-15,
            abs_err / np.abs(ref_v),
            0.0,
        )

        if hybrid_crossover_time is not None:
            # Section 17.4: hybrid pass criterion
            early_mask = t_v <= hybrid_crossover_time
            late_mask = t_v > hybrid_crossover_time

            early_pass = True
            late_pass = True
            max_rel = 0.0
            max_abs = 0.0
            worst_t = 0.0

            if np.any(early_mask):
                max_rel = float(np.max(rel_err[early_mask]))
                if max_rel >= relative_tol:
                    early_pass = False
                    worst_idx = int(np.argmax(rel_err[early_mask]))
                    worst_t = float(t_v[early_mask][worst_idx])

            if np.any(late_mask):
                max_abs = float(np.max(abs_err[late_mask]))
                if max_abs >= absolute_tol:
                    late_pass = False
                    worst_idx = int(np.argmax(abs_err[late_mask]))
                    worst_t = float(t_v[late_mask][worst_idx])

            passed = early_pass and late_pass
            report.results.append(RegressionCheckResult(
                variable=var,
                max_relative_error=max_rel,
                max_absolute_error=max_abs,
                tolerance=relative_tol,
                passed=passed,
                worst_time=worst_t,
                notes=f"hybrid: rel<{relative_tol} for t<={hybrid_crossover_time}, "
                      f"abs<{absolute_tol} for t>{hybrid_crossover_time}",
            ))
        else:
            max_rel = float(np.max(rel_err)) if len(rel_err) > 0 else 0.0
            max_abs = float(np.max(abs_err)) if len(abs_err) > 0 else 0.0
            worst_idx = int(np.argmax(rel_err)) if len(rel_err) > 0 else 0
            worst_t = float(t_v[worst_idx]) if worst_idx < len(t_v) else 0.0

            passed = max_rel < relative_tol
            report.results.append(RegressionCheckResult(
                variable=var,
                max_relative_error=max_rel,
                max_absolute_error=max_abs,
                tolerance=relative_tol,
                passed=passed,
                worst_time=worst_t,
            ))

    return report
