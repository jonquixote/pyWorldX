"""Per-capita transforms — total→per-capita conversions.

Transform step 5 of the pipeline. Converts aggregate values to
per-capita using population series.

Runtime dependency: Requires a population series in the raw store or
passed as an argument.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from data_pipeline.storage.parquet_store import read_raw


def per_capita(
    df: pd.DataFrame,
    value_col: str = "value",
    year_col: str = "year",
    country_col: str = "country_code",
    population_df: Optional[pd.DataFrame] = None,
    population_col: str = "value",
    population_source: Optional[str] = None,
    raw_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Convert total values to per-capita.

    Args:
        df: DataFrame with total values.
        value_col: Column containing total values.
        year_col: Year column.
        country_col: Country identifier column.
        population_df: Optional DataFrame with population data.
            If None, loads from raw store.
        population_col: Name of the population value column.
        population_source: Source ID to load from raw store if
            population_df is None (e.g. "world_bank_SP.POP.TOTL").
        raw_dir: Path to raw store (required if population_df is None).

    Returns:
        DataFrame with per-capita values in '{value_col}_per_capita'.
    """
    if value_col not in df.columns:
        return df

    # Load population if not provided
    if population_df is None:
        if raw_dir is None:
            raise ValueError("raw_dir is required when population_df is None")

        pop_source = population_source or "world_bank_SP.POP.TOTL"
        population_df = read_raw(pop_source, raw_dir=Path(raw_dir))
        if population_df is None:
            raise FileNotFoundError(
                f"Population data '{pop_source}' not found in raw store. "
                "Run world_bank connector first."
            )

    # Merge population data
    merge_cols = [year_col]
    if country_col in df.columns and country_col in population_df.columns:
        merge_cols.append(country_col)

    pop_df = population_df[[*merge_cols, population_col]].copy()
    pop_df = pop_df.rename(columns={population_col: "population"})

    merged = df.merge(pop_df, on=merge_cols, how="left")

    # Calculate per-capita
    per_capita_col = f"{value_col}_per_capita"
    merged[per_capita_col] = merged[value_col] / merged["population"]

    return merged
