"""Gap filling and missing data handling (Section 8.5 step 5)."""

from __future__ import annotations

from enum import Enum
from typing import Any

import pandas as pd


class GapFillMethod(Enum):
    """Supported gap-filling methods."""

    LINEAR = "linear"
    FORWARD_FILL = "ffill"
    BACKWARD_FILL = "bfill"
    CONSTANT = "constant"
    DROP = "drop"


def fill_gaps(
    series: "pd.Series[float]",
    method: GapFillMethod = GapFillMethod.LINEAR,
    constant_value: float = 0.0,
    max_gap: int | None = None,
    transform_log: list[str] | None = None,
) -> "pd.Series[Any]":
    """Fill missing values in a data series."""
    n_missing = int(series.isna().sum())
    if n_missing == 0:
        return series

    result: pd.Series[Any]
    if method == GapFillMethod.LINEAR:
        result = series.interpolate(method="linear", limit=max_gap)
    elif method == GapFillMethod.FORWARD_FILL:
        result = series.ffill(limit=max_gap)
    elif method == GapFillMethod.BACKWARD_FILL:
        result = series.bfill(limit=max_gap)
    elif method == GapFillMethod.CONSTANT:
        result = series.fillna(constant_value)
    elif method == GapFillMethod.DROP:
        result = series.dropna()
    else:
        raise ValueError(f"Unknown gap fill method: {method}")

    if transform_log is not None:
        remaining = int(result.isna().sum())
        transform_log.append(
            f"gap_fill: method={method.value}, "
            f"filled={n_missing - remaining}, remaining={remaining}"
        )
    return result


def detect_gaps(
    series: "pd.Series[float]",
) -> list[tuple[int, int]]:
    """Detect contiguous gaps. Returns (start_idx, length) tuples."""
    gaps: list[tuple[int, int]] = []
    is_na = series.isna()
    in_gap = False
    gap_start = 0
    for i, (idx, val) in enumerate(is_na.items()):
        if val and not in_gap:
            in_gap = True
            gap_start = i
        elif not val and in_gap:
            in_gap = False
            gaps.append((gap_start, i - gap_start))
    if in_gap:
        gaps.append((gap_start, len(series) - gap_start))
    return gaps
