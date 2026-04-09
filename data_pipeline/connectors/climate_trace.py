"""Climate TRACE connector.

Source: https://climatetrace.org
Auth: None. Open data download.
Format: ZIP containing CSV files.
Coverage: 2015-2025, global, 67 sub-sectors.

⚠️ NOTE: The direct CSV URL changed. The working download as of
April 2026 is the summary data ZIP from the communications endpoint.
"""

from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Working URL as of April 2026
URL = "https://downloads.climatetrace.org/communications/v5.5.0/ClimateTRACE-release5_5_0-SummaryData.zip"


def fetch_climate_trace(
    config: PipelineConfig,
) -> FetchResult:
    """Download Climate TRACE summary emissions data."""
    source_id = "climate_trace"
    t0 = time.time()

    try:
        content, sha, cache_hit = fetch_with_cache(
            url=URL,
            cache_dir=config.cache_dir,
            source_id=source_id,
            ttl_days=config.cache_ttl_days,
            timeout=120,
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

    # Extract and parse the first CSV from the ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            csv_files = [n for n in zf.namelist() if n.endswith('.csv')]
            if not csv_files:
                return FetchResult(
                    source_id=source_id, status="error",
                    error_message="No CSV files found in Climate TRACE ZIP.",
                )

            # Read the first (largest) CSV
            csv_name = csv_files[0]
            with zf.open(csv_name) as csv_file:
                df = pd.read_csv(csv_file)

    except (zipfile.BadZipFile, Exception) as e:
        duration = time.time() - t0
        return FetchResult(
            source_id=source_id, status="error",
            error_message=f"Could not parse Climate TRACE ZIP: {e}",
        )

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["source_id"] = source_id
    df["source_variable"] = "climate_trace_emissions"
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "climate_trace", "v5.5.0",
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
