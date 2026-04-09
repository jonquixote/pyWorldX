"""NRMSD computation — compare model trajectories against historical data.

Implements NRMSD (Normalized Root Mean Square Deviation) as specified
in Section 9.1 of the pyWorldX spec:
- nrmsd_direct: mean-normalized
- nrmsd_change_rate: annual-pct-change normalized
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def nrmsd_direct(
    model: np.ndarray | pd.Series,
    reference: np.ndarray | pd.Series,
) -> float:
    """Compute NRMSD with mean normalization (Section 9.1).
    
    NRMSD = sqrt(mean((model - ref)^2)) / mean(ref)
    
    Args:
        model: Model trajectory values.
        reference: Reference (historical) trajectory values.
    
    Returns:
        NRMSD value. Lower is better (0 = perfect match).
    """
    model = np.asarray(model, dtype=float)
    reference = np.asarray(reference, dtype=float)
    
    # Trim to common length
    min_len = min(len(model), len(reference))
    model = model[:min_len]
    reference = reference[:min_len]
    
    if len(model) == 0:
        return float("nan")
    
    mean_ref = np.mean(reference)
    if mean_ref == 0:
        return float("nan")
    
    rmse = np.sqrt(np.mean((model - reference) ** 2))
    return rmse / abs(mean_ref)


def nrmsd_change_rate(
    model: np.ndarray | pd.Series,
    reference: np.ndarray | pd.Series,
) -> float:
    """Compute NRMSD on annual percent change rates.
    
    First computes annual pct change for both series, then NRMSD.
    This compares trends rather than absolute levels.
    """
    model = np.asarray(model, dtype=float)
    reference = np.asarray(reference, dtype=float)
    
    # Trim to common length
    min_len = min(len(model), len(reference))
    model = model[:min_len]
    reference = reference[:min_len]
    
    if len(model) < 2:
        return float("nan")
    
    # Annual percent change (matches spec §9.1: 100 * diff / shift(1))
    def pct_change(arr: np.ndarray) -> np.ndarray:
        return np.diff(arr) / arr[:-1] * 100
    
    model_pct = pct_change(model)
    ref_pct = pct_change(reference)
    
    # Filter out NaN/inf
    valid = np.isfinite(model_pct) & np.isfinite(ref_pct) & (np.abs(ref_pct) > 1e-10)
    if not valid.any():
        return float("nan")
    
    return nrmsd_direct(model_pct[valid], ref_pct[valid])


def weighted_nrmsd(
    model: dict[str, np.ndarray | pd.Series],
    reference: dict[str, np.ndarray | pd.Series],
    weights: Optional[dict[str, float]] = None,
) -> float:
    """Compute weighted NRMSD across multiple variables.
    
    Args:
        model: Dict of variable name → model trajectory.
        reference: Dict of variable name → reference trajectory.
        weights: Optional weights per variable. Equal weights if None.
    
    Returns:
        Weighted NRMSD.
    """
    common_vars = set(model.keys()) & set(reference.keys())
    if not common_vars:
        return float("nan")
    
    if weights is None:
        weights = {v: 1.0 for v in common_vars}
    
    total_weight = sum(weights.get(v, 0) for v in common_vars)
    if total_weight == 0:
        return float("nan")
    
    weighted_sum = 0.0
    for var in common_vars:
        w = weights.get(var, 0)
        if w == 0:
            continue
        nrmsd = nrmsd_direct(model[var], reference[var])
        if np.isfinite(nrmsd):
            weighted_sum += w * nrmsd
    
    return weighted_sum / total_weight


def compare_calibrated_series(
    model_csv: Path,
    reference_csv: Path,
    year_col: str = "year",
    value_col: str = "value",
) -> dict[str, float]:
    """Compare a model CSV against a reference CSV.
    
    Args:
        model_csv: Path to model output CSV.
        reference_csv: Path to reference (historical) CSV.
        year_col: Column name for year.
        value_col: Column name for values.
    
    Returns:
        Dict with nrmsd_direct and nrmsd_change_rate.
    """
    model_df = pd.read_csv(model_csv, comment="#")
    ref_df = pd.read_csv(reference_csv, comment="#")
    
    # Merge on year
    merged = model_df.merge(
        ref_df,
        on=year_col,
        suffixes=("_model", "_ref"),
        how="inner",
    )
    
    if len(merged) < 2:
        return {"nrmsd_direct": float("nan"), "nrmsd_change_rate": float("nan")}
    
    model_vals = merged[f"{value_col}_model"].values
    ref_vals = merged[f"{value_col}_ref"].values
    
    return {
        "nrmsd_direct": nrmsd_direct(model_vals, ref_vals),
        "nrmsd_change_rate": nrmsd_change_rate(model_vals, ref_vals),
        "overlap_years": int(len(merged)),
    }
