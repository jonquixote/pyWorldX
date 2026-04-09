"""Aggregation transforms — country→world aggregate.

Transform step 3 of the pipeline. Converts country-level data to
world-aggregated series using population-weighted or simple summation.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def aggregate_world(
    df: pd.DataFrame,
    value_col: str = "value",
    year_col: str = "year",
    country_col: str = "country_code",
    method: str = "sum",
    population_df: Optional[pd.DataFrame] = None,
    population_col: str = "population",
) -> pd.DataFrame:
    """Aggregate country-level data to world total.

    Args:
        df: DataFrame with country-level data.
        value_col: Column to aggregate.
        year_col: Year column.
        country_col: Country identifier column.
        method: Aggregation method: "sum", "mean", "population_weighted".
        population_df: Optional DataFrame with population data for
            population-weighted aggregation. Must have year_col,
            country_col, and population_col columns.
        population_col: Name of the population column in population_df.

    Returns:
        DataFrame with one row per year, world-aggregated values.
    """
    if value_col not in df.columns:
        return df

    if method == "sum":
        result = df.groupby(year_col)[value_col].sum().reset_index()

    elif method == "mean":
        result = df.groupby(year_col)[value_col].mean().reset_index()

    elif method == "population_weighted":
        if population_df is None:
            raise ValueError(
                "population_df is required for population_weighted aggregation"
            )

        # Merge population data
        merged = df.merge(
            population_df[[year_col, country_col, population_col]],
            on=[year_col, country_col],
            how="left",
        )

        # Calculate weighted value
        merged["weighted_value"] = merged[value_col] * merged[population_col]
        merged["total_pop"] = merged[population_col]

        result = merged.groupby(year_col).agg(
            **{
                value_col: ("weighted_value", "sum"),
                "total_population": ("total_pop", "sum"),
            }
        ).reset_index()

    else:
        raise ValueError(f"Unknown aggregation method: {method}")

    result["source_id"] = "world_aggregate"
    result["country_code"] = "WLD"
    result["country_name"] = "World"

    return result


def aggregate_region(
    df: pd.DataFrame,
    region_col: str,
    value_col: str = "value",
    year_col: str = "year",
    method: str = "sum",
) -> pd.DataFrame:
    """Aggregate country-level data to regional totals.

    Args:
        df: DataFrame with country-level data.
        region_col: Column identifying the region (e.g. "region", "continent").
        value_col: Column to aggregate.
        year_col: Year column.
        method: Aggregation method: "sum" or "mean".

    Returns:
        DataFrame with one row per region per year.
    """
    if value_col not in df.columns:
        return df

    if method == "sum":
        result = df.groupby([region_col, year_col])[value_col].sum().reset_index()
    elif method == "mean":
        result = df.groupby([region_col, year_col])[value_col].mean().reset_index()
    else:
        raise ValueError(f"Unknown aggregation method: {method}")

    return result
