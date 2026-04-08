"""NOAA CO₂ connector — Mauna Loa Observatory.

Sources:
- Annual mean: https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt
- Monthly mean: https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt

Auth: None.
Format: Plain text, space-delimited with comment lines.
"""

from __future__ import annotations

import io
import time

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache, content_hash
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


URLS = {
    "annual": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt",
    "monthly": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt",
}


def fetch_noaa_co2(
    config: PipelineConfig,
    frequency: str = "annual",
) -> FetchResult:
    """Fetch NOAA Mauna Loa CO₂ data.

    Args:
        config: Pipeline configuration.
        frequency: "annual" or "monthly".

    Returns:
        FetchResult with status and metadata.
    """
    source_id = f"noaa_co2_{frequency}"
    url = URLS[frequency]

    t0 = time.time()
    try:
        content, sha, cache_hit = fetch_with_cache(
            url=url,
            cache_dir=config.cache_dir,
            source_id=source_id,
            ttl_days=config.cache_ttl_days,
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

    # Parse the text file
    text = content.decode("utf-8")
    if frequency == "annual":
        df = pd.read_csv(
            io.StringIO(text),
            comment="#",
            sep=r"\s+",
            names=["year", "co2_ppm", "uncertainty"],
        )
    else:
        df = pd.read_csv(
            io.StringIO(text),
            comment="#",
            sep=r"\s+",
            names=[
                "year", "month", "decimal", "monthly_mean",
                "interpolated", "trend", "n_days",
            ],
        )

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["source_id"] = source_id
    df["source_variable"] = "atmospheric_co2"
    df["unit"] = "ppm"
    df["country_code"] = "WLD"  # Mauna Loa is a global proxy
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "noaa_co2", "GML_v4",
        checksum=sha or "", records=records,
        fetched_at=pd.Timestamp.now(tz="UTC").isoformat(),
        url=url, fmt="txt",
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
