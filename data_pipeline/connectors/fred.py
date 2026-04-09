"""FRED connector — Federal Reserve Economic Data.

Source: https://api.stlouisfed.org/fred/
Auth: API key required (free registration).
Format: JSON.
Coverage: 816,000+ time series, 1776-present.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES = {
    "gdp_deflator": "GDPDEF",
    "cpi": "CPIAUCSL",
    "fed_funds": "FEDFUNDS",
    "gdp_current": "GDP",
    "gdp_real": "GDPC1",
    "inflation_expectations": "MICH",
}


def _get_api_key(config: PipelineConfig) -> str:
    """Get FRED API key from config or env var."""
    if config.fred_api_key:
        return config.fred_api_key
    return os.environ.get("FRED_API_KEY", "")


def fetch_fred_series(
    config: PipelineConfig,
    series_id: Optional[str] = None,
    series_key: Optional[str] = None,
) -> FetchResult:
    """Fetch a single FRED series.

    Args:
        config: Pipeline configuration.
        series_id: Direct FRED series ID (e.g. "GDPDEF").
        series_key: Key from SERIES dict (e.g. "gdp_deflator").

    Returns:
        FetchResult with status and metadata.
    """
    api_key = _get_api_key(config)
    if not api_key:
        return FetchResult(
            source_id=f"fred_{series_key or series_id}", status="error",
            error_message="FRED_API_KEY not set. Add to .env or config.",
        )

    if series_key and series_key in SERIES:
        series_id = SERIES[series_key]
    elif not series_id:
        return FetchResult(
            source_id="fred_unknown", status="error",
            error_message="Must provide series_id or series_key.",
        )

    source_id = f"fred_{series_id}"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
        "limit": 100000,
    }
    t0 = time.time()

    try:
        # Direct request with API key (required for FRED)
        r = requests.get(BASE_URL, params=params, timeout=config.request_timeout_seconds)
        r.raise_for_status()
        data = r.json()
        sha = ""
        cache_hit = False
    except requests.RequestException as e:
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "error",
            error_message=str(e), duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="error",
            error_message=str(e), cache_hit=False,
        )

    # Parse JSON (need to inject API key for actual request)
    params["file_type"] = "json"
    r = requests.get(BASE_URL, params=params, timeout=config.request_timeout_seconds)
    r.raise_for_status()
    data = r.json()

    df = pd.DataFrame(data.get("observations", []))
    if df.empty:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No observations returned.",
        )

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["source_id"] = source_id
    df["source_variable"] = series_id
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "fred", "API_v1",
        checksum="", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=BASE_URL, fmt="json",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records, checksum="", cache_hit=False, duration=duration,
    )

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records,
    )


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch all predefined FRED series for pyWorldX."""
    results = []
    for key in SERIES:
        result = fetch_fred_series(config, series_key=key)
        results.append(result)
    return results
