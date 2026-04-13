"""Outlier detection — Z-score and IQR-based anomaly flags.

Transform step 8 of the pipeline. Identifies anomalous values in
time series data using statistical methods.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def detect_outliers_zscore(
    df: pd.DataFrame,
    value_col: str = "value",
    group_cols: Optional[list[str]] = None,
    z_threshold: float = 3.0,
) -> pd.DataFrame:
    """Flag outliers using Z-score method.

    Values with |z-score| > z_threshold are flagged as outliers.

    Args:
        df: DataFrame with time series data.
        value_col: Column to check for outliers.
        group_cols: Columns to group by before computing Z-scores.
        z_threshold: Z-score threshold (default 3.0).

    Returns:
        DataFrame with additional columns:
        - z_score: Z-score of each value
        - outlier_flag: "OUTLIER" if |z| > threshold, else "OK"
    """
    if value_col not in df.columns:
        df["z_score"] = np.nan
        df["outlier_flag"] = "OK"
        return df

    df = df.copy()
    df["z_score"] = np.nan
    df["outlier_flag"] = "OK"

    if group_cols is None:
        group_cols = []

    if group_cols:
        for group_key, group_df in df.groupby(group_cols):
            values = group_df[value_col]
            mean = values.mean()
            std = values.std()

            if std > 0:
                z_scores: "pd.Series[float]" = (values - mean) / std
                df.loc[group_df.index, "z_score"] = z_scores
                outlier_mask = group_df.index[z_scores.abs() > z_threshold]  # type: ignore[assignment]
                df.loc[outlier_mask, "outlier_flag"] = "OUTLIER"
    else:
        values = df[value_col]
        mean = values.mean()
        std = values.std()

        if std > 0:
            z_scores = (values - mean) / std
            df["z_score"] = z_scores
            outlier_mask = z_scores.abs() > z_threshold
            df.loc[outlier_mask, "outlier_flag"] = "OUTLIER"

    return df


def detect_outliers_iqr(
    df: pd.DataFrame,
    value_col: str = "value",
    group_cols: Optional[list[str]] = None,
    iqr_multiplier: float = 1.5,
) -> pd.DataFrame:
    """Flag outliers using IQR (Interquartile Range) method.

    Values below Q1 - iqr_multiplier*IQR or above Q3 + iqr_multiplier*IQR
    are flagged as outliers.

    Args:
        df: DataFrame with time series data.
        value_col: Column to check for outliers.
        group_cols: Columns to group by.
        iqr_multiplier: IQR multiplier (default 1.5 for standard outlier,
            3.0 for extreme outlier).

    Returns:
        DataFrame with additional columns:
        - iqr_lower: Lower bound (Q1 - multiplier * IQR)
        - iqr_upper: Upper bound (Q3 + multiplier * IQR)
        - outlier_flag: "OUTLIER" if outside bounds, else "OK"
    """
    if value_col not in df.columns:
        df["iqr_lower"] = np.nan
        df["iqr_upper"] = np.nan
        df["outlier_flag_iqr"] = "OK"
        return df

    df = df.copy()
    df["iqr_lower"] = np.nan
    df["iqr_upper"] = np.nan
    df["outlier_flag_iqr"] = "OK"

    if group_cols is None:
        group_cols = []

    if group_cols:
        for group_key, group_df in df.groupby(group_cols):
            values = group_df[value_col]
            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)
            iqr = q3 - q1

            lower = q1 - iqr_multiplier * iqr
            upper = q3 + iqr_multiplier * iqr

            df.loc[group_df.index, "iqr_lower"] = lower
            df.loc[group_df.index, "iqr_upper"] = upper

            outlier_mask = group_df.index[
                (values < lower) | (values > upper)
            ]
            df.loc[outlier_mask, "outlier_flag_iqr"] = "OUTLIER"
    else:
        values = df[value_col]
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr

        df["iqr_lower"] = lower
        df["iqr_upper"] = upper

        outlier_mask: "pd.Series[bool]" = (values < lower) | (values > upper)
        df.loc[outlier_mask, "outlier_flag_iqr"] = "OUTLIER"

    return df


def detect_sudden_changes(
    df: pd.DataFrame,
    value_col: str = "value",
    year_col: str = "year",
    group_cols: Optional[list[str]] = None,
    change_threshold: float = 5.0,
) -> pd.DataFrame:
    """Flag sudden year-over-year changes exceeding a threshold.

    Args:
        df: DataFrame with time series data.
        value_col: Column to check.
        year_col: Year column.
        group_cols: Columns to group by.
        change_threshold: Maximum allowed relative change (e.g. 5.0 = 500%).

    Returns:
        DataFrame with additional columns:
        - yoy_change: Year-over-year relative change
        - sudden_change_flag: "SUDDEN_CHANGE" if |yoy_change| > threshold
    """
    if value_col not in df.columns or year_col not in df.columns:
        df["yoy_change"] = np.nan
        df["sudden_change_flag"] = "OK"
        return df

    df = df.copy()
    df["yoy_change"] = np.nan
    df["sudden_change_flag"] = "OK"

    if group_cols is None:
        group_cols = []

    if group_cols:
        groups = df.sort_values([*group_cols, year_col]).groupby(group_cols)
    else:
        df = df.sort_values(year_col)
        groups: list[tuple[None, pd.DataFrame]] = [(None, df)]

    for group_key, group_df in groups:
        idx = group_df.index
        values = group_df[value_col]

        # Calculate year-over-year relative change
        yoy = values.pct_change()
        df.loc[idx, "yoy_change"] = yoy

        # Flag sudden changes
        sudden_mask = yoy.abs() > change_threshold
        df.loc[idx[sudden_mask], "sudden_change_flag"] = "SUDDEN_CHANGE"

    return df
