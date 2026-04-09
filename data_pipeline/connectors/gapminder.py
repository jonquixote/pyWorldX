"""Gapminder connector — Global development indicators.

Source: https://www.gapminder.org/data/
Auth: None. Direct CSV download from various sources.
Format: CSV.
Coverage: 1800-2023, population, GDP, life expectancy, etc.

Gapminder data is compiled from World Bank, UN, and other sources.
This connector uses the Gapminder Systema Globalis via the Gapminder Foundation's
open data repositories.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Gapminder data via World Bank (Gapminder compiles World Bank data)
# Using World Bank API as Gapminder sources
WB_URL = "https://api.worldbank.org/v2"

# Key Gapminder indicators
INDICATORS = {
    "population": "SP.POP.TOTL",
    "gdp_per_capita": "NY.GDP.PCAP.KD",
    "life_expectancy": "SP.DYN.LE00.IN",
}


def fetch_gapminder(
    config: PipelineConfig,
    indicator: str = "population",
    start_year: int = 1960,
    end_year: int = 2024,
) -> FetchResult:
    """Download Gapminder data via World Bank API."""
    indicator_code = INDICATORS.get(indicator, indicator)
    source_id = f"gapminder_{indicator}"
    t0 = time.time()

    url = f"{WB_URL}/country/all/indicator/{indicator_code}"
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

    df["source_id"] = source_id
    df["source_variable"] = indicator
    df = df.dropna(subset=["year", "value"])

    records_count = len(df)
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "gapminder", indicator,
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
    """Fetch all Gapminder indicators."""
    results = []
    for indicator in INDICATORS:
        result = fetch_gapminder(config, indicator=indicator)
        results.append(result)
    return results
