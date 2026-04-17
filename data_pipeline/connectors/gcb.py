"""Global Carbon Budget (GCB) connector.

Source: Global Carbon Project (GCB 2024 via Robbie Andrew)
Auth: None.
Format: CSV.

Downloads the official GCB partitioning data to separate atmospheric growth 
into fossil, land-use, ocean sink, and land sink components.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw

# Using Robbie Andrew's machine-readable CSV mirror for GCB 2024
URL = "https://robbieandrew.github.io/GCB2024/CSV/s51_2024_Global_Sources_and_Sinks.csv"


def fetch_gcb(config: PipelineConfig) -> FetchResult:
    source_id = "gcb_carbon_budget"
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

    # Parse CSV
    try:
        df = pd.read_csv(io.BytesIO(content))
        
        # Mapping Robbie Andrew CSV columns to standard pipeline names
        # Note: Values are in GtCO2/yr. Conversion to GtC/yr (divide by 3.664) 
        # should happen in alignment/transforms.
        column_map = {
            "Year": "year",
            "fossil_carbon": "fossil_emissions",
            "land-use_change": "land_use_change_emissions",
            "atmosphere": "atmospheric_growth",
            "ocean": "ocean_sink",
            "land": "land_sink"
        }
        df = df.rename(columns=column_map)
        
        df = df.dropna(subset=["year"])
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df = df.dropna(subset=["year"])

        df["source_id"] = source_id
        df["source_variable"] = "carbon_flux_partitioning_gtco2"
        
        records = len(df)
        write_raw(df, source_id, config.raw_dir)
        
        init_db(config.metadata_db)
        record_source_version(
            config.metadata_db, "gcb", "2024_v1_ra",
            checksum=sha or "", records=records,
            fetched_at=datetime.now(timezone.utc).isoformat(),
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
    except Exception as e:
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "error",
            error_message=str(e), duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="error",
            error_message=str(e), cache_hit=cache_hit,
        )
