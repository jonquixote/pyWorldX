"""IMF World Economic Outlook connector.

Source: https://www.imf.org/en/Publications/WEO
Auth: None. Direct Excel download.
Coverage: 1980-2029, 190+ countries.

Verified working April 2026: The April 2025 WEO historical data xlsx
is available at the IMF media CDN URL.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Working URL as of April 2026 (verified: 10MB xlsx file, PK header confirmed)
URL = "https://www.imf.org/-/media/files/publications/weo/weo-database/2025/april/weohistorical.xlsx"


def fetch_imf_weo(
    config: PipelineConfig,
    local_file: Optional[Path] = None,
) -> FetchResult:
    """Download IMF World Economic Outlook database."""
    source_id = "imf_weo"
    t0 = time.time()

    # Try local file first
    if local_file and local_file.exists():
        return _process_weo_file(config, local_file)

    # Try auto-download
    try:
        r = requests.get(URL, timeout=120)
        r.raise_for_status()
        content = r.content

        # Verify it's actually an Excel file
        if content[:4] != b'PK\x03\x04':
            return FetchResult(
                source_id=source_id, status="error",
                error_message="Downloaded file is not a valid Excel file.",
            )

        sha = ""
        cache_hit = False
        return _process_weo_content(config, content, sha, cache_hit, URL)
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


def _process_weo_file(config: PipelineConfig, local_file: Path) -> FetchResult:
    with open(local_file, "rb") as f:
        content = f.read()
    return _process_weo_content(config, content, "", False, str(local_file))


def _process_weo_content(
    config: PipelineConfig,
    content: bytes,
    sha: str,
    cache_hit: bool,
    url: str,
) -> FetchResult:
    source_id = "imf_weo"
    t0 = time.time()

    # Parse Excel — WEO has header rows, then data
    try:
        df = pd.read_excel(io.BytesIO(content), header=None)
    except ValueError as e:
        return FetchResult(
            source_id=source_id, status="error",
            error_message=f"Could not parse WEO file: {e}",
        )

    df["source_id"] = source_id
    df["source_variable"] = "imf_weo"
    records = len(df)

    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "imf", "WEO_Apr2025",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="xlsx",
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
