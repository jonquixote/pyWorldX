"""USGS Mineral Commodity Summaries connector.

Source: USGS National Minerals Information Center
URL: https://www.usgs.gov/centers/national-minerals-information-center
Auth: None. Direct file download.

⚠️ NOTE: As of April 2026, USGS no longer provides direct CSV downloads
from a stable URL. The Mineral Commodity Summaries are published as PDF
reports with data tables. The connector below fetches the latest available
MCS publication page. Users may need to manually extract data from the PDF
or find an alternative source (e.g., OWID mineral data, or the USGS data
release if it becomes available again).

This connector is implemented as a manual download helper.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# USGS MCS publication page (DOI-based, stable)
URL = "https://doi.org/10.3133/mcs2026"


def fetch_usgs(
    config: PipelineConfig,
) -> FetchResult:
    """Fetch the USGS Mineral Commodity Summaries publication page.

    Note: As of April 2026, USGS does not provide direct CSV downloads.
    This connector fetches the publication page metadata. Users should
    manually extract data from the published PDF/HTML reports.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = "usgs_mcs"
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

    # Store as HTML metadata (not structured data)
    text = content.decode("utf-8", errors="replace")
    df = pd.DataFrame({
        "source_id": [source_id],
        "source_variable": ["mcs_publication_page"],
        "url": [URL],
        "fetched_at": [datetime.now(timezone.utc).isoformat()],
        "content_hash": [sha or ""],
        "content_length": [len(content)],
    })

    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "usgs", "MCS_2026",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=URL, fmt="html",
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
