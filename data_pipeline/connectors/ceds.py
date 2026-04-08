"""CEDS connector — Community Emissions Data System.

Source: Zenodo record 12803197 (CEDS v_2024_07_08 Release Emission Data)
URL: https://zenodo.org/records/12803197
Auth: None.
Format: ZIP containing country-level CSV files per pollutant.
Coverage: 1750–2022, all countries, 7 pollutants × sectors.

Pollutants: SO2, NOx, BC, OC, CO, NH3, NMVOC

Note: The aggregate ZIP (~59MB) contains CSV files organized by pollutant.
The connector downloads and extracts the ZIP, then parses the relevant CSV.
"""

from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Zenodo record 12803197 — CEDS v_2024_07_08 aggregate emissions
# Check https://zenodo.org/records/12803197 if URL changes.
URL = (
    "https://zenodo.org/api/records/12803197/files/"
    "CEDS_v_2024_07_08_aggregate.zip/content"
)

# Map pollutant names to CSV file patterns in the ZIP
POLLUTANT_FILES = {
    "SO2": "CEDS_v2024_07_08_SO2_country_aggregates.csv",
    "NOx": "CEDS_v2024_07_08_NOx_country_aggregates.csv",
    "BC": "CEDS_v2024_07_08_BC_country_aggregates.csv",
    "OC": "CEDS_v2024_07_08_OC_country_aggregates.csv",
    "CO": "CEDS_v2024_07_08_CO_country_aggregates.csv",
    "NH3": "CEDS_v2024_07_08_NH3_country_aggregates.csv",
    "NMVOC": "CEDS_v2024_07_08_NMVOC_country_aggregates.csv",
}


def fetch_ceds_pollutant(
    config: PipelineConfig,
    pollutant: str = "SO2",
) -> FetchResult:
    """Download CEDS emissions for a specific pollutant.

    Downloads the full ZIP archive and extracts the relevant CSV file.

    Args:
        config: Pipeline configuration.
        pollutant: One of SO2, NOx, BC, OC, CO, NH3, NMVOC.

    Returns:
        FetchResult with status and metadata.
    """
    pollutant_upper = pollutant.upper()
    pollutant_lower = pollutant.lower()
    source_id = f"ceds_{pollutant_lower}"
    csv_filename = POLLUTANT_FILES.get(pollutant_upper)

    if not csv_filename:
        return FetchResult(
            source_id=source_id, status="error",
            error_message=f"Unknown pollutant: {pollutant}. "
            f"Valid: {list(POLLUTANT_FILES.keys())}",
        )

    t0 = time.time()

    # Download the ZIP
    try:
        content, sha, cache_hit = fetch_with_cache(
            url=URL,
            cache_dir=config.cache_dir,
            source_id="ceds_aggregate_zip",
            ttl_days=config.cache_ttl_days,
            timeout=120,  # ZIP is ~59MB, need more time
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

    # Extract the CSV from the ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if csv_filename not in zf.namelist():
                # Try to find a matching file
                matches = [n for n in zf.namelist() if pollutant_upper in n]
                if not matches:
                    raise FileNotFoundError(
                        f"Could not find {csv_filename} in ZIP. "
                        f"Available: {zf.namelist()[:10]}"
                    )
                csv_filename = matches[0]

            with zf.open(csv_filename) as csv_file:
                df = pd.read_csv(csv_file)
    except (zipfile.BadZipFile, FileNotFoundError, KeyError) as e:
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "error",
            error_message=str(e), duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="error",
            error_message=str(e), cache_hit=cache_hit,
        )

    # Standardize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Add metadata
    df["source_id"] = source_id
    df["source_variable"] = f"{pollutant_lower}_emissions"
    df["unit"] = "kt"
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "ceds", "v_2024_07_08",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=URL, fmt="zip",
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
    """Fetch all CEDS pollutants for pyWorldX.

    Downloads the ZIP once and extracts each pollutant CSV.
    """
    # Download ZIP once
    t0 = time.time()
    try:
        content, sha, cache_hit = fetch_with_cache(
            url=URL,
            cache_dir=config.cache_dir,
            source_id="ceds_aggregate_zip",
            ttl_days=config.cache_ttl_days,
            timeout=120,
        )
    except requests.RequestException as e:
        return [FetchResult(
            source_id="ceds_all", status="error",
            error_message=str(e), cache_hit=False,
        )]

    results = []
    for pollutant_upper, csv_filename in POLLUTANT_FILES.items():
        source_id = f"ceds_{pollutant_upper.lower()}"
        pollutant_lower = pollutant_upper.lower()

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                if csv_filename not in zf.namelist():
                    matches = [n for n in zf.namelist() if pollutant_upper in n]
                    if not matches:
                        results.append(FetchResult(
                            source_id=source_id, status="error",
                            error_message=f"File not found: {csv_filename}",
                            cache_hit=cache_hit,
                        ))
                        continue
                    csv_filename = matches[0]

                with zf.open(csv_filename) as csv_file:
                    df = pd.read_csv(csv_file)

            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            df["source_id"] = source_id
            df["source_variable"] = f"{pollutant_lower}_emissions"
            df["unit"] = "kt"
            records = len(df)

            raw_path = write_raw(df, source_id, config.raw_dir)

            init_db(config.metadata_db)
            record_source_version(
                config.metadata_db, "ceds", "v_2024_07_08",
                checksum=sha or "", records=records,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                url=URL, fmt="zip",
            )

            results.append(FetchResult(
                source_id=source_id, status="success",
                records_fetched=records, checksum_sha256=sha,
                cache_hit=cache_hit,
            ))

        except Exception as e:
            results.append(FetchResult(
                source_id=source_id, status="error",
                error_message=str(e), cache_hit=cache_hit,
            ))

    return results
