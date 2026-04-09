"""Gap detection — find missing years, flag them.

Transform step 7 of the pipeline. Identifies gaps in time series
data and adds quality flags.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def detect_gaps(
    df: pd.DataFrame,
    year_col: str = "year",
    value_col: str = "value",
    group_cols: Optional[list[str]] = None,
    expected_freq: str = "annual",
) -> pd.DataFrame:
    """Detect gaps in time series data and add quality flags.

    Args:
        df: DataFrame with time series data.
        year_col: Name of the year column.
        value_col: Column to check for NaN/missing values.
        group_cols: Columns to group by before detecting gaps.
        expected_freq: Expected frequency: "annual", "5-year", "decadal".

    Returns:
        DataFrame with additional columns:
        - gap_flag: True if the row is in a gap (NaN value or missing year)
        - gap_size: Number of consecutive missing years
        - quality_flag: "OK", "GAP_FILLED", or "INTERPOLATED"
    """
    if value_col not in df.columns or year_col not in df.columns:
        df["quality_flag"] = "OK"
        df["gap_flag"] = False
        df["gap_size"] = 0
        return df

    df = df.copy()
    df["quality_flag"] = "OK"
    df["gap_flag"] = df[value_col].isna()
    df["gap_size"] = 0

    if group_cols is None:
        group_cols = []

    # Determine expected gap size
    freq_map = {
        "annual": 1,
        "5-year": 5,
        "decadal": 10,
    }
    expected_gap = freq_map.get(expected_freq, 1)

    # Find gaps per group
    if group_cols:
        groups = df.groupby(group_cols, group_keys=False)
    else:
        groups = [(None, df)]

    result_frames = []

    for group_key, group_df in groups:
        group_df = group_df.sort_values(year_col).reset_index(drop=True)
        group_df[year_col] = pd.to_numeric(group_df[year_col], errors="coerce")

        years = group_df[year_col].values
        if len(years) < 2:
            result_frames.append(group_df)
            continue

        # Find gaps in year sequence
        diffs = np.diff(years)
        expected_diff = expected_gap

        gap_mask = diffs > expected_diff

        for i, is_gap in enumerate(gap_mask):
            if is_gap:
                gap_size = int(years[i + 1]) - int(years[i]) - expected_diff
                group_df.loc[group_df.index[i + 1], "gap_size"] = gap_size
                group_df.loc[group_df.index[i + 1], "quality_flag"] = "GAP_FILLED"

        # Flag NaN values as interpolated
        nan_mask = group_df[value_col].isna()
        group_df.loc[nan_mask, "quality_flag"] = "INTERPOLATED"
        group_df.loc[nan_mask, "gap_flag"] = True

        result_frames.append(group_df)

    if result_frames:
        return pd.concat(result_frames, ignore_index=True)

    return df


def gap_summary(
    df: pd.DataFrame,
    year_col: str = "year",
    group_cols: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Generate a summary of gaps in the data.

    Args:
        df: DataFrame with time series data.
        year_col: Year column.
        group_cols: Columns to group by.

    Returns:
        DataFrame with one row per group, summarizing gaps.
    """
    if group_cols is None:
        group_cols = []

    if not group_cols:
        # Treat entire dataset as one group
        group_cols = ["_all"]
        df = df.copy()
        df["_all"] = "all"

    records = []
    for group_key, group_df in df.groupby(group_cols):
        group_df = group_df.sort_values(year_col)
        years = pd.to_numeric(group_df[year_col], errors="coerce").dropna()

        if len(years) < 2:
            continue

        diffs = np.diff(years.values)
        gaps = diffs[diffs > 1]

        if isinstance(group_key, str):
            group_key = (group_key,)

        records.append({
            "group": str(group_key),
            "year_min": int(years.min()),
            "year_max": int(years.max()),
            "total_years": int(years.max()) - int(years.min()) + 1,
            "observed_years": len(years),
            "gap_count": len(gaps),
            "max_gap_size": int(gaps.max()) - 1 if len(gaps) > 0 else 0,
            "coverage_pct": len(years) / (int(years.max()) - int(years.min()) + 1) * 100,
        })

    return pd.DataFrame(records)
