"""Global Carbon Atlas connector.

Source: https://globalcarbonatlas.org
Auth: None. Direct CSV download via GCP Zenodo record.
Format: CSV.
Coverage: 1751-present, country-level fossil CO2 emissions (MtCO2).
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Actual numeric emissions data (MtCO2)
URL = "https://zenodo.org/api/records/14106218/files/GCB2024v18_MtCO2_flat.csv/content"


def fetch_carbon_atlas(
    config: PipelineConfig,
) -> FetchResult:
    """Download Global Carbon Project fossil CO2 emissions data."""
    source_id = "global_carbon_atlas"
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

    text = content.decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    df["source_id"] = source_id
    df["source_variable"] = "fossil_co2_emissions"
    records = len(df)

    # Write to raw store
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "carbon_atlas", "GCB2024v18_MtCO2",
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
