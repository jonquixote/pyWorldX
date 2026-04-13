"""Reshape transforms — wide→long, melt, pivot, column standardization.

Transform step 1 of the pipeline. Takes raw Parquet DataFrames and
produces long-format, standardized DataFrames ready for downstream
transforms.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def melt_wide_to_long(
    df: pd.DataFrame,
    id_cols: Optional[list[str]] = None,
    year_prefix: Optional[str] = None,
    value_name: str = "value",
    var_name: str = "year",
) -> pd.DataFrame:
    """Melt wide-format data (year columns) to long format.

    Handles the common case where raw data has years as column names
    (e.g. UN WPP, PWT, Maddison).

    Args:
        df: Wide-format DataFrame with year columns.
        id_cols: Columns to keep as identifiers. If None, auto-detects
            non-numeric columns as id columns.
        year_prefix: If provided, only melt columns starting with this
            prefix (e.g. "YR" for "YR1990", "YR1991").
        value_name: Name for the melted value column.
        var_name: Name for the year variable column.

    Returns:
        Long-format DataFrame with columns: id_cols + [year, value].
    """
    if id_cols is None:
        # Auto-detect: non-numeric columns are id columns
        id_cols = list(df.select_dtypes(exclude=["number"]).columns)

    # Find year columns (numeric column names or prefixed)
    value_cols = [c for c in df.columns if c not in id_cols]

    if year_prefix:
        value_cols = [c for c in value_cols if str(c).startswith(year_prefix)]
    else:
        # Keep only columns that look like years
        value_cols = [c for c in value_cols if str(c).isdigit() or (
            str(c).startswith("-") and str(c)[1:].isdigit()
        )]

    if not value_cols:
        # No year columns found — return as-is with a warning
        return df

    df = df.melt(
        id_vars=id_cols,
        value_vars=value_cols,
        var_name=var_name,
        value_name=value_name,
    )

    # Convert year column to numeric
    df[var_name] = pd.to_numeric(df[var_name], errors="coerce")
    df = df.dropna(subset=[var_name])
    df[var_name] = df[var_name].astype(int)

    return df


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names to lowercase snake_case.

    Args:
        df: DataFrame with arbitrary column names.

    Returns:
        DataFrame with standardized column names.
    """
    df.columns = [
        c.strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def rename_columns(
    df: pd.DataFrame,
    rename_map: dict[str, str],
) -> pd.DataFrame:
    """Rename columns using a mapping dict.

    Args:
        df: DataFrame to rename.
        rename_map: Dict mapping old names to new names.

    Returns:
        DataFrame with renamed columns.
    """
    return df.rename(columns=rename_map)


def pivot_long_to_wide(
    df: pd.DataFrame,
    index_cols: list[str],
    column: str,
    value: str,
) -> pd.DataFrame:
    """Pivot long-format data back to wide format.

    Inverse of melt_wide_to_long. Useful for creating entity-level
    DataFrames from multi-entity long format.

    Args:
        df: Long-format DataFrame.
        index_cols: Columns to use as the index.
        column: Column whose unique values become new column names.
        value: Column whose values fill the new columns.

    Returns:
        Wide-format DataFrame.
    """
    return df.pivot_table(
        index=index_cols,
        columns=column,
        values=value,
        aggfunc="first",
    ).reset_index()


def filter_by_year(
    df: pd.DataFrame,
    year_col: str = "year",
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> pd.DataFrame:
    """Filter DataFrame to a year range.

    Args:
        df: DataFrame with a year column.
        year_col: Name of the year column.
        start_year: Inclusive start year.
        end_year: Inclusive end year.

    Returns:
        Filtered DataFrame.
    """
    if year_col not in df.columns:
        return df

    mask: "pd.Series[bool]" = pd.Series(True, index=df.index)
    if start_year is not None:
        mask &= df[year_col] >= start_year
    if end_year is not None:
        mask &= df[year_col] <= end_year

    return df[mask].copy()  # type: ignore[return-value]


def filter_by_country(
    df: pd.DataFrame,
    country_col: str = "country_code",
    countries: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Filter DataFrame to specific countries.

    Args:
        df: DataFrame with a country column.
        country_col: Name of the country column.
        countries: List of country codes to keep. If None, keep all.

    Returns:
        Filtered DataFrame.
    """
    if country_col not in df.columns or countries is None:
        return df

    return df[df[country_col].isin(countries)].copy()  # type: ignore[return-value]
