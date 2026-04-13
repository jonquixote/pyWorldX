"""Data normalization transforms (Section 8.5 step 5)."""

from __future__ import annotations

import pandas as pd


def per_capita(
    total_series: "pd.Series[float]",
    population_series: "pd.Series[float]",
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Compute per-capita values."""
    common = total_series.index.intersection(population_series.index)
    result: "pd.Series[float]" = total_series.loc[common] / population_series.loc[common]
    if transform_log is not None:
        transform_log.append("per_capita: total / population")
    return result


def z_score(
    series: "pd.Series[float]",
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Z-score normalization."""
    mean = series.mean()
    std = series.std()
    if std < 1e-15:
        result = series - mean
    else:
        result = (series - mean) / std
    if transform_log is not None:
        transform_log.append(f"z_score: mean={mean:.4f}, std={std:.4f}")
    return result


def min_max_scale(
    series: "pd.Series[float]",
    feature_range: tuple[float, float] = (0.0, 1.0),
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Min-max scaling."""
    s_min = series.min()
    s_max = series.max()
    rng = s_max - s_min
    lo, hi = feature_range
    if rng < 1e-15:
        result: "pd.Series[float]" = pd.Series(lo, index=series.index)
    else:
        result = (series - s_min) / rng * (hi - lo) + lo
    if transform_log is not None:
        transform_log.append(
            f"min_max_scale: [{s_min:.4f}, {s_max:.4f}] -> [{lo}, {hi}]"
        )
    return result


def cumulative_sum(
    series: "pd.Series[float]",
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Cumulative sum for flow-to-stock reconstruction."""
    result = series.cumsum()
    if transform_log is not None:
        transform_log.append("cumulative_sum: flow -> cumulative stock")
    return result
