"""UN Comtrade connector — Trade and production flows.

Source: https://comtradeplus.un.org/
Auth: None for bulk (500 calls/hour). Free registration for higher limits.
Format: JSON via REST API v2.
Coverage: 1962-present, all countries, all commodities.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


BASE_URL = "https://comtradeapi.un.org/data/v1/get"


def fetch_comtrade(
    config: PipelineConfig,
    commodity_code: str = "ALL",
    start_year: int = 1990,
    end_year: int = 2024,
) -> FetchResult:
    """Fetch UN Comtrade data for a commodity.

    Args:
        config: Pipeline configuration.
        commodity_code: HS commodity code (e.g. "2701" for coal).
        start_year: First year.
        end_year: Last year.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = f"comtrade_{commodity_code}"
    url = f"{BASE_URL}/C/A/{commodity_code}"
    t0 = time.time()

    params = {
        "period": f"{start_year}:{end_year}",
        "reporterCode": "all",
    }

    try:
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        data = r.json()
        sha = ""
        cache_hit = False
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

    records_list = data.get("results", [])
    if not records_list:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No results from Comtrade.",
        )

    df = pd.DataFrame(records_list)
    df["source_id"] = source_id
    df["source_variable"] = f"comtrade_{commodity_code}"
    records = len(df)

    # Write to raw store
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "comtrade", f"HS_{commodity_code}",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
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
