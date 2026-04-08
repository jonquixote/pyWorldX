"""Uncertainty decomposition (Section 10.8).

Decomposes forecast spread into contributions from:
- parameter perturbations
- scenario differences
- exogenous input perturbations
- initial condition uncertainty
"""

from __future__ import annotations


import numpy as np

from pyworldx.core.result import RunResult
from pyworldx.forecasting.ensemble import UncertaintyType


def decompose_uncertainty(
    member_results: list[RunResult],
    uncertainty_labels: list[dict[str, UncertaintyType]],
    variables: list[str] | None = None,
    time_index: int = -1,
) -> dict[str, dict[str, float]]:
    """Decompose forecast variance by uncertainty source.

    Uses a variance-based approach: for each uncertainty type,
    compute the variance contributed by members where that type
    was perturbed.

    Args:
        member_results: list of RunResult from ensemble members
        uncertainty_labels: per-member dict mapping perturbed parameter
            names to their UncertaintyType
        variables: variables to decompose (None = all)
        time_index: time step at which to evaluate (default: final)

    Returns:
        dict[variable_name -> dict[uncertainty_type -> variance_fraction]]
    """
    if not member_results:
        return {}

    # Collect all variable names
    if variables is None:
        variables = list(member_results[0].trajectories.keys())

    decomposition: dict[str, dict[str, float]] = {}

    for var in variables:
        # Gather values at time_index
        values: list[float] = []
        for result in member_results:
            if var in result.trajectories:
                traj = result.trajectories[var]
                idx = time_index if time_index >= 0 else len(traj) + time_index
                if 0 <= idx < len(traj):
                    values.append(float(traj[idx]))

        if len(values) < 2:
            decomposition[var] = {
                "parameter": 0.0,
                "scenario": 0.0,
                "exogenous_input": 0.0,
                "initial_condition": 0.0,
            }
            continue

        total_var = float(np.var(values))
        if total_var < 1e-30:
            decomposition[var] = {
                "parameter": 0.0,
                "scenario": 0.0,
                "exogenous_input": 0.0,
                "initial_condition": 0.0,
            }
            continue

        # Group members by dominant uncertainty type
        type_values: dict[str, list[float]] = {
            "parameter": [],
            "scenario": [],
            "exogenous_input": [],
            "initial_condition": [],
        }

        for i, result in enumerate(member_results):
            if var not in result.trajectories:
                continue
            traj = result.trajectories[var]
            idx = time_index if time_index >= 0 else len(traj) + time_index
            if not (0 <= idx < len(traj)):
                continue
            val = float(traj[idx])

            if i < len(uncertainty_labels):
                labels = uncertainty_labels[i]
                # Attribute to most prominent uncertainty type
                for utype in labels.values():
                    key = utype.value
                    if key in type_values:
                        type_values[key].append(val)

        # Compute variance fraction per type
        fractions: dict[str, float] = {}
        accounted = 0.0
        for type_name, vals in type_values.items():
            if len(vals) >= 2:
                frac = float(np.var(vals)) / total_var
            else:
                frac = 0.0
            fractions[type_name] = frac
            accounted += frac

        # Normalize to sum to 1.0 (or leave residual unattributed)
        if accounted > 0:
            for key in fractions:
                fractions[key] /= accounted

        decomposition[var] = fractions

    return decomposition


def format_decomposition_report(
    decomposition: dict[str, dict[str, float]],
) -> str:
    """Format uncertainty decomposition as a readable report."""
    lines = ["Uncertainty Decomposition Report", "=" * 40]
    for var, fracs in decomposition.items():
        lines.append(f"\n{var}:")
        for source, frac in sorted(
            fracs.items(), key=lambda x: x[1], reverse=True
        ):
            pct = frac * 100
            bar = "#" * int(pct / 2)
            lines.append(f"  {source:20s}: {pct:5.1f}% {bar}")
    return "\n".join(lines)
