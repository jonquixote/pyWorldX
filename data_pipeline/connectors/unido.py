"""UNIDO connector — Industrial Statistics Database.

Source: World Bank API (manufacturing value added)
Auth: None. Direct API access.
Format: JSON.
Coverage: 1960-2024, country-level manufacturing value added (constant 2015 US$).

Note: UNIDO stat.unido.org API returns 403. This connector uses World Bank API
as an alternative source for UNIDO-industry data (manufacturing value added).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# World Bank API endpoints for UNIDO-industry indicators
INDICATORS = {
    "manufacturing_value_added": "NV.IND.MANF.KD",  # Manufacturing, value added (constant 2015 US$)
    "industry_value_added": "NV.IND.TOTL.KD",  # Industry, value added (constant 2015 US$)
}

WB_URL = "https://api.worldbank.org/v2"


def fetch_unido(
    config: PipelineConfig,
    indicator: str = "manufacturing_value_added",
    start_year: int = 1960,
    end_year: int = 2024,
) -> FetchResult:
    """Download UNIDO-industry data via World Bank API."""
    indicator_code = INDICATORS.get(indicator)
    if not indicator_code:
        return FetchResult(
            source_id=f"unido_{indicator}", status="error",
            error_message=f"Unknown indicator: {indicator}",
        )

    source_id = f"unido_{indicator}"
    url = f"{WB_URL}/country/all/indicator/{indicator_code}"
    t0 = time.time()

    params = {
        "date": f"{start_year}:{end_year}",
        "format": "json",
        "per_page": 5000,
    }

    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "error",
            error_message=str(e), duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="error",
            error_message=str(e), cache_hit=False,
        )

    # World Bank API returns [metadata, data]
    if not isinstance(data, list) or len(data) < 2:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="Invalid World Bank API response.",
        )

    records_list = data[1]
    if not records_list:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No data returned from World Bank API.",
        )

    df = pd.DataFrame(records_list)
    # Rename columns to standard format
    if "date" in df.columns:
        df = df.rename(columns={"date": "year"})
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if "countryiso3code" in df.columns:
        df = df.rename(columns={"countryiso3code": "country_code"})
    if "indicator" in df.columns and "value" in df["indicator"].iloc[0]:
        df["indicator_name"] = df["indicator"].apply(lambda x: x.get("value", "") if isinstance(x, dict) else "")

    df["source_id"] = source_id
    df["source_variable"] = indicator
    df = df.dropna(subset=["year", "value"])

    records_count = len(df)
    raw_path = write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "unido", f"wb_{indicator}",
        checksum="", records=records_count,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="json",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records_count, checksum="", cache_hit=False, duration=duration,
    )

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records_count,
    )


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch all UNIDO indicators."""
    results = []
    for indicator in INDICATORS:
        result = fetch_unido(config, indicator=indicator)
        results.append(result)
    return results
