"""Forecast summary statistics (Section 10.6).

Per variable: mean, median, p05, p25, p75, p95, min, max.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_summary(
    trajectories: dict[str, list["np.ndarray[Any, Any]"]],
    time_index: "np.ndarray[Any, Any] | None" = None,
) -> dict[str, pd.DataFrame]:
    """Compute ensemble summary statistics per variable.

    Args:
        trajectories: variable name -> list of trajectory arrays
        time_index: optional time array for DataFrame index

    Returns:
        dict of variable name -> DataFrame with columns:
        mean, median, p05, p25, p75, p95, min, max
    """
    summary: dict[str, pd.DataFrame] = {}

    for var_name, traj_list in trajectories.items():
        if not traj_list:
            continue

        arr = np.array(traj_list)  # (n_runs, n_timesteps)

        df = pd.DataFrame({
            "mean": np.mean(arr, axis=0),
            "median": np.median(arr, axis=0),
            "p05": np.percentile(arr, 5, axis=0),
            "p25": np.percentile(arr, 25, axis=0),
            "p75": np.percentile(arr, 75, axis=0),
            "p95": np.percentile(arr, 95, axis=0),
            "min": np.min(arr, axis=0),
            "max": np.max(arr, axis=0),
        })

        if time_index is not None and len(time_index) == df.shape[0]:
            df.index = pd.Index(time_index, name="t")

        summary[var_name] = df

    return summary


def extract_percentile_band(
    summary: dict[str, pd.DataFrame],
    variable: str,
    lower: str = "p05",
    upper: str = "p95",
) -> tuple["np.ndarray[Any, Any]", "np.ndarray[Any, Any]"]:
    """Extract a percentile band for a variable.

    Returns:
        (lower_array, upper_array)
    """
    if variable not in summary:
        raise KeyError(f"Variable '{variable}' not in summary")
    df = summary[variable]
    return (
        np.asarray(df[lower].values),
        np.asarray(df[upper].values),
    )
