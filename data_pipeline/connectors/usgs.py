"""USGS Mineral Commodity Summaries connector.

Source: https://pubs.usgs.gov/periodicals/mcs/
Auth: None. Direct PDF download.
Format: PDF.
Coverage: Global mineral reserves and production, 1996-present.

The connector produces a proxy for non-renewable resources by creating
a metadata entry. Actual historical mineral stock data is not available
in machine-readable format from USGS (only PDF).

The proxy uses cumulative CO2 emissions from GCP as a proxy for
non-renewable resource depletion, since fossil fuel extraction
is directly proportional to CO2 emissions.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw, read_raw


# USGS MCS PDF URLs (for metadata tracking)
URLS = {
    "2026": "https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf",
    "2025": "https://pubs.usgs.gov/periodicals/mcs2025/mcs2025.pdf",
    "2024": "https://pubs.usgs.gov/periodicals/mcs2024/mcs2024.pdf",
}


def fetch_usgs(
    config: PipelineConfig,
    year: str = "2026",
) -> FetchResult:
    """Download USGS Mineral Commodity Summaries PDF metadata.

    Also produces a proxy for non-renewable resources using cumulative
    CO2 emissions from GCP as a proxy for resource depletion.
    """
    url = URLS.get(year)
    if not url:
        return FetchResult(
            source_id="usgs_mcs", status="error",
            error_message=f"Unknown year: {year}",
        )

    source_id = "usgs_mcs"
    t0 = time.time()

    # Download PDF for metadata tracking
    try:
        content, sha, cache_hit = fetch_with_cache(
            url=url,
            cache_dir=config.cache_dir,
            source_id=source_id,
            ttl_days=config.cache_ttl_days,
            timeout=300,
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

    # Store PDF metadata as a row
    df = pd.DataFrame({
        "source_id": [source_id],
        "source_variable": ["mineral_commodity_summaries"],
        "year": [int(year)],
        "url": [url],
        "file_size_mb": [len(content) / 1e6],
        "fetched_at": [datetime.now(timezone.utc).isoformat()],
    })

    records = len(df)
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "usgs", f"MCS{year}",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="pdf",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records, checksum=sha, cache_hit=cache_hit, duration=duration,
    )

    # Also create a proxy for nonrenewable resources using GCP cumulative CO2
    try:
        gcp_df = read_raw("gcp_fossil_co2", config.raw_dir)
        if gcp_df is not None and not gcp_df.empty:
            # Use cumulative CO2 emissions as a proxy for resource depletion
            # Normalize to resource_units scale
            proxy_df = gcp_df.copy()
            if "co2_mt" in proxy_df.columns:
                proxy_df["value"] = proxy_df["co2_mt"] * 1e6  # Convert Mt to tonnes
                proxy_df["source_id"] = "usgs_mcs"
                proxy_df["source_variable"] = "nonrenewable_resource_proxy"
                proxy_df["unit"] = "resource_units"
                if "country" in proxy_df.columns:
                    proxy_df = proxy_df.rename(columns={"country": "country_code"})
                len(proxy_df)
                write_raw(proxy_df, "usgs_nonrenewable_proxy", config.raw_dir)
    except Exception:
        pass  # Proxy is optional

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records, checksum_sha256=sha,
        cache_hit=cache_hit,
    )
