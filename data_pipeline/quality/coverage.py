"""Coverage assessment — year coverage % per source/variable."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_pipeline.storage.parquet_store import list_sources, read_raw


def compute_coverage(
    raw_dir: Path,
    calibration_start: int = 1900,
    calibration_end: int = 2020,
) -> pd.DataFrame:
    """Compute year coverage for each source in the raw store.

    Args:
        raw_dir: Path to the raw Parquet store.
        calibration_start: Start of calibration period.
        calibration_end: End of calibration period.

    Returns:
        DataFrame with coverage statistics per source.
    """
    sources = list_sources(raw_dir)
    records = []

    for source_id in sources:
        df = read_raw(source_id, raw_dir=raw_dir)
        if df is None:
            continue

        # Find year column
        year_col = None
        for col in ["year", "date"]:
            if col in df.columns:
                year_col = col
                break

        if year_col is None:
            continue

        years = pd.to_numeric(df[year_col], errors="coerce").dropna()
        if len(years) == 0:
            continue

        min_year = int(years.min())
        max_year = int(years.max())
        observed = len(years.unique())

        # Coverage within calibration period
        cal_years = set(range(calibration_start, calibration_end + 1))
        observed_cal = len(set(years.unique()) & cal_years)
        total_cal = len(cal_years)

        records.append({
            "source_id": source_id,
            "year_min": min_year,
            "year_max": max_year,
            "observed_years": observed,
            "calibration_coverage": observed_cal,
            "calibration_total": total_cal,
            "coverage_pct": observed_cal / total_cal * 100 if total_cal > 0 else 0,
        })

    return pd.DataFrame(records)
