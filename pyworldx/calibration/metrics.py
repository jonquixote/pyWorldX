"""NRMSD calibration metrics (Section 9.1).

Three formulations:
- nrmsd_direct: mean-normalized RMSD for level-compared variables
- nrmsd_change_rate: change-rate NRMSD for rate-compared variables
- weighted_nrmsd: weighted composite of individual NRMSD scores
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def annual_pct_change(series: "pd.Series[float]") -> "pd.Series[float]":
    """Transform to annual percentage change rates.

    Matches Nebel et al. 2023 formulation:
        100 * (series.diff() / series.shift(1))
    """
    shifted = series.shift(1)
    # Avoid division by zero
    safe_shifted = shifted.replace(0, np.nan)
    result: "pd.Series[float]" = 100.0 * (series.diff() / safe_shifted)
    return result


def nrmsd_direct(
    series_true: "pd.Series[float]",
    series_pred: "pd.Series[float]",
) -> float:
    """Mean-normalized RMSD for level-compared variables.

    Used for population, HDI, ecological footprint.
    Normalization by mean(true) matches Nebel et al. 2023.
    """
    true_vals = np.asarray(series_true.values, dtype=np.float64)
    pred_vals = np.asarray(series_pred.values, dtype=np.float64)

    if len(true_vals) != len(pred_vals):
        raise ValueError(f"Series length mismatch: {len(true_vals)} vs {len(pred_vals)}")
    if len(true_vals) == 0:
        raise ValueError("Cannot compute NRMSD on empty series")

    mean_true = float(np.mean(true_vals))
    if abs(mean_true) < 1e-15:
        raise ValueError("Cannot normalize: mean(true) is zero")

    rmsd = float(np.sqrt(np.mean((pred_vals - true_vals) ** 2)))
    return rmsd / abs(mean_true)


def nrmsd_change_rate(
    series_true: "pd.Series[float]",
    series_pred: "pd.Series[float]",
) -> float:
    """Change-rate NRMSD for rate-compared variables.

    Used for industrial output, food per capita, pollution,
    non-renewables, service per capita.

    Both series are first transformed to annual percentage change
    rates, dropping the first NaN row. Then nrmsd_direct is applied.
    """
    true_pct = annual_pct_change(series_true).dropna()
    pred_pct = annual_pct_change(series_pred).dropna()

    # Align indices
    common_idx = true_pct.index.intersection(pred_pct.index)
    if len(common_idx) == 0:
        raise ValueError("No common indices after change-rate transformation")

    return nrmsd_direct(true_pct.loc[common_idx], pred_pct.loc[common_idx])


def weighted_nrmsd(
    metrics: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Weighted composite NRMSD score.

    Args:
        metrics: per-variable NRMSD scores
        weights: per-variable weights (must sum to > 0)

    Returns:
        Weighted average NRMSD
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for var, score in metrics.items():
        w = weights.get(var, 0.0)
        weighted_sum += score * w
        total_weight += w

    if total_weight <= 0:
        raise ValueError("Total weight must be positive")

    return weighted_sum / total_weight


@dataclass
class CrossValidationConfig:
    """Train/validate split configuration (Section 9.4)."""

    train_start: int = 1970
    train_end: int = 2010
    validate_start: int = 2010
    validate_end: int = 2023
    overfit_threshold: float = 0.20


# Named constant for Nebel et al. 2023 reproduction (Section 9.4)
NEBEL_2023_CALIBRATION_CONFIG = CrossValidationConfig(
    train_start=1970,
    train_end=2020,
    validate_start=2020,
    validate_end=2023,
    overfit_threshold=0.20,
)


# Nebel 2023 NRMSD upper bounds (Section 13.1)
NEBEL_2023_BOUNDS: dict[str, tuple[float, str]] = {
    "population": (0.019, "direct"),
    "industrial_output": (0.474, "change_rate"),
    "food_per_capita": (1.108, "change_rate"),
    "pollution": (0.337, "change_rate"),
    "nonrenewable_resources": (0.757, "change_rate"),
    "service_per_capita": (0.619, "change_rate"),
    "human_welfare_hdi": (0.178, "direct"),
    "ecological_footprint": (0.343, "direct"),
}

NEBEL_2023_TOTAL_NRMSD_BOUND: float = 0.2719


@dataclass
class CalibrationResult:
    """Result of a calibration run."""

    parameters: dict[str, float]
    nrmsd_scores: dict[str, float]
    total_nrmsd: float
    train_config: CrossValidationConfig
    iterations: int
    converged: bool
    validation_nrmsd: dict[str, float] | None = None
    overfit_flagged: bool = False
