"""Consistency checks — cross-source correlation and stock level agreement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from data_pipeline.storage.parquet_store import read_raw, list_sources


def check_flow_consistency(
    raw_dir: Path,
    sources_a: list[str],
    sources_b: list[str],
    value_col: str = "value",
    year_col: str = "year",
    country_col: str = "country_code",
    country: str = "WLD",
) -> dict[str, Any]:
    """Check Pearson correlation between two flow sources.

    Args:
        raw_dir: Path to the raw store.
        sources_a: List of source IDs for source A.
        sources_b: List of source IDs for source B.
        value_col: Column containing values.
        year_col: Year column.
        country_col: Country column.
        country: Country code to check (default "WLD" for world).

    Returns:
        Dict with correlation and divergence metrics.
    """
    # Concatenate sources
    frames_a = []
    for s in sources_a:
        df = read_raw(s, raw_dir=raw_dir)
        if df is not None:
            frames_a.append(df)

    frames_b = []
    for s in sources_b:
        df = read_raw(s, raw_dir=raw_dir)
        if df is not None:
            frames_b.append(df)

    if not frames_a or not frames_b:
        return {"status": "insufficient_data"}

    df_a = pd.concat(frames_a, ignore_index=True)
    df_b = pd.concat(frames_b, ignore_index=True)

    # Filter to common country and year range
    if country_col in df_a.columns:
        df_a = df_a[df_a[country_col] == country]
    if country_col in df_b.columns:
        df_b = df_b[df_b[country_col] == country]

    if value_col not in df_a.columns or value_col not in df_b.columns:
        return {"status": "missing_value_column"}

    # Merge on year
    merged = df_a.merge(
        df_b,
        on=year_col,
        suffixes=("_a", "_b"),
        how="inner",
    )

    if len(merged) < 3:
        return {"status": "insufficient_overlap"}

    val_a = merged[f"{value_col}_a"]
    val_b = merged[f"{value_col}_b"]

    correlation = val_a.corr(val_b)
    max_divergence = ((val_a - val_b).abs() / val_a.replace(0, np.nan)).dropna().max()

    return {
        "status": "ok",
        "overlap_years": len(merged),
        "year_min": int(merged[year_col].min()),
        "year_max": int(merged[year_col].max()),
        "correlation": round(correlation, 4),
        "max_relative_divergence": round(max_divergence, 4) if not np.isnan(max_divergence) else None,
    }


def check_stock_level_agreement(
    raw_dir: Path,
    source_id: str,
    independent_estimate: Optional[pd.DataFrame] = None,
    value_col: str = "value",
    year_col: str = "year",
    country_col: str = "country_code",
) -> dict[str, Any]:
    """Check stock level against an independent estimate.

    Args:
        raw_dir: Path to the raw store.
        source_id: Source ID to check.
        independent_estimate: Optional DataFrame with independent values.
        value_col: Column containing values.
        year_col: Year column.
        country_col: Country column.

    Returns:
        Dict with level agreement metrics.
    """
    df = read_raw(source_id, raw_dir=raw_dir)
    if df is None or independent_estimate is None:
        return {"status": "insufficient_data"}

    if value_col not in df.columns:
        return {"status": "missing_value_column"}

    # Merge on year (and country if available)
    merge_cols = [year_col]
    if country_col in df.columns and country_col in independent_estimate.columns:
        merge_cols.append(country_col)

    merged = df.merge(
        independent_estimate,
        on=merge_cols,
        suffixes=("_source", "_independent"),
        how="inner",
    )

    if len(merged) < 1:
        return {"status": "no_overlap"}

    val_source = merged[f"{value_col}_source"]
    val_indep = merged[f"{value_col}_independent"]

    # Compute NRMSD (simple version)
    mean_val = val_indep.mean()
    if mean_val == 0:
        return {"status": "zero_mean"}

    nrmsd = np.sqrt(((val_source - val_indep) ** 2).mean()) / abs(mean_val)

    return {
        "status": "ok",
        "overlap_years": len(merged),
        "source_value_latest": val_source.iloc[-1] if len(val_source) > 0 else None,
        "independent_value_latest": val_indep.iloc[-1] if len(val_indep) > 0 else None,
        "nrmsd": round(nrmsd, 4),
    }
