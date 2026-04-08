"""Global Carbon Budget (GCP) connector.

Source: Zenodo record 14106218 (GCB 2024 fossil CO₂ emissions)
Auth: None.
Format: CSV files.

Note: The GCP publishes national fossil CO₂ emissions data annually.
The Zenodo record contains CSV files for territorial and consumption-
based emissions. If the Zenodo URL changes, check:
https://globalcarbonbudget.org/the-latest-gcb-data/
"""

from __future__ import annotations

import io
import time
from typing import Optional

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Zenodo record for GCB 2024 (v18) - flat territorial emissions CSV
# Record: https://zenodo.org/records/14106218
# If this URL changes, check the Zenodo API:
# https://zenodo.org/api/records/14106218
URL = (
    "https://zenodo.org/api/records/14106218/files/"
    "GCB2024v18_MtCO2_flat.csv/content"
)


def fetch_gcp(
    config: PipelineConfig,
    country: Optional[str] = None,
) -> FetchResult:
    """Download GCP national fossil CO₂ emissions.

    Args:
        config: Pipeline configuration.
        country: If provided, filter to this country code.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = "gcp_fossil_co2"
    t0 = time.time()

    try:
        content, sha, cache_hit = fetch_with_cache(
            url=URL,
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

    # Parse the CSV file
    text = content.decode("utf-8")
    df = pd.read_csv(io.StringIO(text))

    # Expected columns vary by release — standardize
    # Common: Country, ISO3, Year, Total, or similar
    # Normalize column names to lowercase
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Try to find country, year, and emissions columns
    country_col = None
    for c in ["country", "country_name", "name"]:
        if c in df.columns:
            country_col = c
            break

    iso_col = None
    for c in ["iso3", "iso3_code", "country_code", "code"]:
        if c in df.columns:
            iso_col = c
            break

    year_col = None
    for c in ["year", "date"]:
        if c in df.columns:
            year_col = c
            break

    emissions_col = None
    for c in ["total", "total_co2", "co2_emissions", "emissions", "fossil_co2"]:
        if c in df.columns:
            emissions_col = c
            break

    if not all([country_col, year_col, emissions_col]):
        duration = time.time() - t0
        error_msg = (
            f"Could not find expected columns. "
            f"Found: {list(df.columns)}"
        )
        record_fetch(
            config.metadata_db, source_id, "error",
            error_message=error_msg, duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="error",
            error_message=error_msg, cache_hit=cache_hit,
        )

    # Build standardized DataFrame
    result_df = pd.DataFrame({
        "country": df[country_col],
        "country_code": df[iso_col] if iso_col else "UNK",
        "year": pd.to_numeric(df[year_col], errors="coerce"),
        "co2_mt": pd.to_numeric(df[emissions_col], errors="coerce"),
        "source_id": source_id,
        "source_variable": "fossil_co2_emissions",
        "unit": "Mt_CO2",
    })
    result_df = result_df.dropna(subset=["year", "co2_mt"])

    if country:
        result_df = result_df[result_df["country_code"] == country]

    records = len(result_df)

    # Write to raw store
    raw_path = write_raw(result_df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "gcp", "2024v1.0",
        checksum=sha or "", records=records,
        fetched_at=pd.Timestamp.now(tz="UTC").isoformat(),
        url=URL, fmt="csv",
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
