"""Deflation transforms — nominal→constant prices.

Transform step 4 of the pipeline. Converts nominal USD values to
constant prices using a GDP deflator series.

Runtime dependency: Requires World Bank GDP deflator data in the raw store.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from data_pipeline.storage.parquet_store import read_raw


def deflate_series(
    df: pd.DataFrame,
    value_col: str = "value",
    year_col: str = "year",
    country_col: str = "country_code",
    deflator_df: Optional[pd.DataFrame] = None,
    deflator_value_col: str = "value",
    base_year: int = 2017,
) -> pd.DataFrame:
    """Convert nominal values to constant prices using a GDP deflator.

    Args:
        df: DataFrame with nominal values.
        value_col: Column containing nominal values.
        year_col: Year column.
        country_col: Country identifier column.
        deflator_df: DataFrame with GDP deflator values. If None,
            attempts to load from the raw store (world_bank_NY.GDP.DEFL.KD.ZG).
        deflator_value_col: Name of the deflator value column in deflator_df.
        base_year: Base year for constant prices (deflator = 100 in this year).

    Returns:
        DataFrame with deflated values in a new column '{value_col}_real'.
    """
    if value_col not in df.columns:
        return df

    # Load deflator if not provided
    if deflator_df is None:
        deflator_df = read_raw(
            "world_bank_NY.GDP.DEFL.KD.ZG",
            raw_dir=None,  # Will be set by caller
        )
        if deflator_df is None:
            raise FileNotFoundError(
                "GDP deflator not found in raw store. "
                "Run world_bank connector first."
            )

    # Normalize deflator to base_year = 100
    deflator_normalized = deflator_df.copy()

    # Get base year deflator value (world average or first available)
    if country_col in deflator_normalized.columns:
        # Use world aggregate if available
        world_mask = deflator_normalized[country_col].isin(["WLD", ""])
        if world_mask.any():
            base_val = deflator_normalized.loc[
                world_mask & (deflator_normalized[year_col] == base_year),
                deflator_value_col,
            ]
        else:
            base_val = deflator_normalized.loc[
                deflator_normalized[year_col] == base_year,
                deflator_value_col,
            ]
    else:
        base_val = deflator_normalized.loc[
            deflator_normalized[year_col] == base_year,
            deflator_value_col,
        ]

    if len(base_val) == 0:
        # Base year not available — use first available year
        base_val = deflator_normalized[deflator_value_col].dropna().head(1)

    if len(base_val) == 0:
        raise ValueError("No valid deflator values found.")

    base = base_val.iloc[0]
    deflator_normalized["deflator_index"] = (
        deflator_normalized[deflator_value_col] / base * 100
    )

    # Merge deflator into main DataFrame
    merge_cols = [year_col]
    if country_col in df.columns and country_col in deflator_normalized.columns:
        merge_cols.append(country_col)

    merged = df.merge(
        deflator_normalized[[*merge_cols, "deflator_index"]],
        on=merge_cols,
        how="left",
    )

    # Deflate
    real_col = f"{value_col}_real"
    merged[real_col] = merged[value_col] / merged["deflator_index"] * 100

    return merged


def deflate_world_bank_values(
    df: pd.DataFrame,
    raw_dir,
    value_col: str = "value",
    year_col: str = "year",
    country_col: str = "country_code",
    base_year: int = 2017,
) -> pd.DataFrame:
    """Deflate using World Bank GDP deflator from the raw store.

    Convenience wrapper that loads the deflator from the raw store.

    Args:
        df: DataFrame with nominal values.
        raw_dir: Path to the raw Parquet store.
        value_col: Column containing nominal values.
        year_col: Year column.
        country_col: Country identifier column.
        base_year: Base year for constant prices.

    Returns:
        DataFrame with deflated values.
    """
    from pathlib import Path

    deflator_df = read_raw(
        "world_bank_NY.GDP.DEFL.KD.ZG",
        raw_dir=Path(raw_dir),
    )
    if deflator_df is None:
        raise FileNotFoundError(
            "GDP deflator not found in raw store. "
            "Run 'data_pipeline collect --source world_bank' first."
        )

    return deflate_series(
        df=df,
        value_col=value_col,
        year_col=year_col,
        country_col=country_col,
        deflator_df=deflator_df,
        base_year=base_year,
    )
