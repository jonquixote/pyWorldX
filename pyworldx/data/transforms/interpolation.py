"""Interpolation and resampling (Section 8.5 step 4)."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd


def interpolate_annual(
    series: "pd.Series[float]",
    method: str = "linear",
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Interpolate to annual frequency."""
    if series.empty:
        return series
    start = int(series.index.min())
    end = int(series.index.max())
    annual_idx = pd.RangeIndex(start, end + 1)
    reindexed = series.reindex(annual_idx)
    result: pd.Series[Any] = reindexed.interpolate(method=cast(Any, method))
    if transform_log is not None:
        transform_log.append(
            f"interpolate_annual: method={method}, {start}-{end}"
        )
    return result


def resample_to_timestep(
    series: "pd.Series[float]",
    dt: float = 1.0,
    method: str = "linear",
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Resample series to match simulation timestep."""
    if series.empty:
        return series
    start = float(series.index.min())
    end = float(series.index.max())
    new_idx = np.arange(start, end + dt / 2, dt)
    reindexed = series.reindex(pd.Index(new_idx))
    result: pd.Series[Any] = reindexed.interpolate(method=cast(Any, method))
    if transform_log is not None:
        transform_log.append(
            f"resample_to_timestep: dt={dt}, method={method}"
        )
    return result
