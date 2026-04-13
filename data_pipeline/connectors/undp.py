"""UNDP HDR connector — Human Development Report.

Source: https://hdr.undp.org/data-center/documentation-and-downloads
Auth: None. Direct CSV download.
Format: CSV.
Coverage: 1990-2023, 193 countries.
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


# Direct CSV download URL (may change — check the HDR page if broken)
URL = "https://hdr.undp.org/sites/default/files/2023-24_HDR/HDR23-24_Composite_indices_complete_time_series.csv"


def fetch_undp_hdr(
    config: PipelineConfig,
) -> FetchResult:
    """Download UNDP Human Development Report data.

    Args:
        config: Pipeline configuration.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = "undp_hdr"
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
    text = content.decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Melt wide format (year columns) to long
    id_cols = [c for c in df.columns if not str(c).isdigit()]
    year_cols = [c for c in df.columns if c not in id_cols]

    if year_cols:
        df = df.melt(
            id_vars=id_cols,
            value_vars=year_cols,
            var_name="year",
            value_name="hdi_value",
        )
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["value"] = pd.to_numeric(df["hdi_value"], errors="coerce")
        df = df.drop(columns=["hdi_value"], errors="ignore")
    else:
        df["value"] = pd.to_numeric(df.iloc[:, -1], errors="coerce") if len(df.columns) > 0 else 0.0

    df = df.dropna(subset=["value"])
    df["source_id"] = source_id
    df["source_variable"] = "hdr"
    records = len(df)

    # Write to raw store
    write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "undp", "HDR_2023-24",
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
