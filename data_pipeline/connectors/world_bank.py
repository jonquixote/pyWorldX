"""World Bank indicators connector.

Sources:
- Population: SP.POP.TOTL
- GDP: NY.GDP.MKTP.CD
- GNI per capita: NY.GNP.PCAP.CD
- GDP deflator: NY.GDP.DEFL.KD.ZG

API: https://api.worldbank.org/v2/
Auth: None.
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache, content_hash
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


INDICATORS = {
    "population_total": "SP.POP.TOTL",
    "gdp_current_usd": "NY.GDP.MKTP.CD",
    "gni_per_capita": "NY.GNP.PCAP.CD",
    "gdp_deflator": "NY.GDP.DEFL.KD.ZG",
}

BASE_URL = "https://api.worldbank.org/v2/country/all/indicator"


def fetch_indicator(
    indicator_code: str,
    config: PipelineConfig,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> FetchResult:
    """Fetch a single World Bank indicator.

    Args:
        indicator_code: World Bank indicator code (e.g. "SP.POP.TOTL").
        config: Pipeline configuration.
        start_year: First year to fetch (defaults to config.calibration_start).
        end_year: Last year to fetch (defaults to config.calibration_end).

    Returns:
        FetchResult with status and metadata.
    """
    source_id = f"world_bank_{indicator_code}"
    start = start_year or config.calibration_start
    end = end_year or config.calibration_end
    url = f"{BASE_URL}/{indicator_code}"
    params = {
        "date": f"{start}:{end}",
        "format": "json",
        "per_page": 10000,
    }
    headers = {"Accept": "application/json"}

    t0 = time.time()
    try:
        content, sha, cache_hit = fetch_with_cache(
            url=url,
            cache_dir=config.cache_dir,
            source_id=source_id,
            ttl_days=config.cache_ttl_days,
            headers=headers,
            params=params,
            timeout=config.request_timeout_seconds,
        )
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

    import json
    meta, data = json.loads(content)
    if not data:
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "skipped",
            error_message="No data returned", duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No data returned", cache_hit=cache_hit,
        )

    df = pd.DataFrame(data)
    df["date"] = pd.to_numeric(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["source_id"] = source_id
    df["source_variable"] = indicator_code
    df["unit"] = meta.get("name", "")
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "world_bank", "API_v2",
        checksum=sha or "", records=records,
        fetched_at=pd.Timestamp.now(tz="UTC").isoformat(),
        url=url, fmt="json",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records, checksum=sha, cache_hit=cache_hit, duration=duration,
    )

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records, checksum_sha256=sha,
        cache_hit=cache_hit,
    )


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch all World Bank indicators for pyWorldX."""
    results = []
    for name, code in INDICATORS.items():
        result = fetch_indicator(code, config)
        results.append(result)
    return results
