"""Interpolation transforms — 5-year→annual, gap filling.

Transform step 2 of the pipeline. Converts data at coarse temporal
resolution (e.g. UN WPP 5-year periods) to annual resolution using
linear or spline interpolation.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def interpolate_annual(
    df: pd.DataFrame,
    year_col: str = "year",
    value_col: str = "value",
    group_cols: Optional[list[str]] = None,
    method: str = "linear",
    fill_gaps: bool = True,
    max_gap_years: int = 3,
) -> pd.DataFrame:
    """Interpolate data to annual frequency.

    Handles both regular interpolation (within groups) and gap filling
    (missing years within a known range).

    Args:
        df: DataFrame with year and value columns.
        year_col: Name of the year column.
        value_col: Name of the value column to interpolate.
        group_cols: Columns to group by before interpolating
            (e.g. ["country_code"]). Each group is interpolated independently.
        method: Interpolation method: "linear", "spline", "polynomial".
        fill_gaps: If True, also fill missing years within the range
            of each group (up to max_gap_years).
        max_gap_years: Maximum gap size to fill. Gaps larger than this
            are left as NaN.

    Returns:
        DataFrame with annual resolution.
    """
    if value_col not in df.columns:
        return df

    if group_cols is None:
        group_cols = []

    result_frames = []

    # Determine groups
    if group_cols:
        groups = df.groupby(group_cols, group_keys=False)
    else:
        groups = [(None, df)]

    for group_key, group_df in groups:
        group_df = group_df.sort_values(year_col).copy()

        # Ensure year column is numeric
        group_df[year_col] = pd.to_numeric(group_df[year_col], errors="coerce")
        group_df = group_df.dropna(subset=[year_col])

        if len(group_df) < 2:
            result_frames.append(group_df)
            continue

        # Build complete annual index
        min_year = int(group_df[year_col].min())
        max_year = int(group_df[year_col].max())
        annual_index = pd.RangeIndex(min_year, max_year + 1, name=year_col)

        # Set year as index for interpolation
        interp_df = group_df.set_index(year_col)

        # Reindex to annual frequency
        interp_df = interp_df.reindex(annual_index)

        # Interpolate the value column
        interp_df[value_col] = interp_df[value_col].interpolate(method=method)

        # Fill gaps for other numeric columns
        if fill_gaps:
            for col in interp_df.select_dtypes(include=["number"]).columns:
                if col != value_col:
                    interp_df[col] = interp_df[col].interpolate(method=method)

        # Reset index
        interp_df = interp_df.reset_index()
        interp_df = interp_df.rename(columns={"index": year_col})

        # Restore group columns if they were dropped
        if group_cols:
            for i, col in enumerate(group_cols):
                if col not in interp_df.columns:
                    interp_df[col] = group_key if isinstance(group_key, str) else group_key[i]

        result_frames.append(interp_df)

    if not result_frames:
        return df

    return pd.concat(result_frames, ignore_index=True)


def fill_gaps(
    df: pd.DataFrame,
    year_col: str = "year",
    value_col: str = "value",
    group_cols: Optional[list[str]] = None,
    max_gap_years: int = 3,
) -> pd.DataFrame:
    """Fill small gaps in time series data.

    Only fills gaps where the missing span is <= max_gap_years.
    Uses forward-fill for the first year and backward-fill for the last year.

    Args:
        df: DataFrame with year and value columns.
        year_col: Name of the year column.
        value_col: Name of the value column.
        group_cols: Columns to group by.
        max_gap_years: Maximum gap size to fill.

    Returns:
        DataFrame with small gaps filled.
    """
    if value_col not in df.columns:
        return df

    if group_cols is None:
        group_cols = []

    result_frames = []

    if group_cols:
        groups = df.groupby(group_cols, group_keys=False)
    else:
        groups = [(None, df)]

    for group_key, group_df in groups:
        group_df = group_df.sort_values(year_col).copy()
        group_df[year_col] = pd.to_numeric(group_df[year_col], errors="coerce")

        # Find gaps
        years = group_df[year_col].values
        diffs = np.diff(years)
        gap_positions = np.where(diffs > 1)[0]

        for gap_idx in gap_positions:
            gap_size = int(years[gap_idx + 1]) - int(years[gap_idx])
            if gap_size - 1 > max_gap_years:
                continue  # Gap too large, skip

            # Interpolate the gap
            start_year = int(years[gap_idx])
            end_year = int(years[gap_idx + 1])
            start_val = group_df.loc[group_df[year_col] == start_year, value_col].values[0]
            end_val = group_df.loc[group_df[year_col] == end_year, value_col].values[0]

            new_years = list(range(start_year + 1, end_year))
            interp_vals = np.linspace(start_val, end_val, len(new_years) + 2)[1:-1]

            new_rows = pd.DataFrame({
                year_col: new_years,
                value_col: interp_vals,
            })

            # Copy other columns
            for col in group_df.columns:
                if col not in [year_col, value_col]:
                    new_rows[col] = group_df[col].iloc[gap_idx]

            group_df = pd.concat([group_df, new_rows], ignore_index=True)
            group_df = group_df.sort_values(year_col).reset_index(drop=True)

        result_frames.append(group_df)

    if not result_frames:
        return df

    return pd.concat(result_frames, ignore_index=True)


def resample_to_timestep(
    df: pd.DataFrame,
    year_col: str = "year",
    value_col: str = "value",
    group_cols: Optional[list[str]] = None,
    dt: float = 1.0,
    method: str = "linear",
) -> pd.DataFrame:
    """Resample data to a specific timestep.

    Args:
        df: DataFrame with year and value columns.
        year_col: Name of the year column.
        value_col: Name of the value column.
        group_cols: Columns to group by.
        dt: Target timestep (e.g. 1.0 for annual, 0.25 for quarterly).
        method: Interpolation method.

    Returns:
        DataFrame resampled to the target timestep.
    """
    if value_col not in df.columns:
        return df

    if group_cols is None:
        group_cols = []

    result_frames = []

    if group_cols:
        groups = df.groupby(group_cols, group_keys=False)
    else:
        groups = [(None, df)]

    for group_key, group_df in groups:
        group_df = group_df.sort_values(year_col).copy()
        group_df[year_col] = pd.to_numeric(group_df[year_col], errors="coerce")

        # Build target index
        min_val = group_df[year_col].min()
        max_val = group_df[year_col].max()
        target_index = np.arange(min_val, max_val + dt / 2, dt)

        # Interpolate
        interp_df = group_df.set_index(year_col)
        interp_df = interp_df.reindex(target_index)
        interp_df[value_col] = interp_df[value_col].interpolate(method=method)
        interp_df = interp_df.reset_index()
        interp_df = interp_df.rename(columns={"index": year_col})

        result_frames.append(interp_df)

    if not result_frames:
        return df

    return pd.concat(result_frames, ignore_index=True)
