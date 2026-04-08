"""Nebel et al. (2023) supplementary data connector.

Source: PLOS ONE article DOI 10.1371/journal.pone.0275865
URL: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0275865
Auth: None. Open access.

⚠️ NOTE: The article has one supplementary file (s001.docx, 3.7MB) which
contains supplementary information but may not contain the raw calibration
data series. The exact GDP-deflated industrial output, food, service, and
pollution proxy series used in the paper may need to be:
1. Extracted from tables/figures in the supplementary document, or
2. Reconstructed from the raw data sources cited in the paper, or
3. Obtained by contacting the authors.

This connector downloads the supplementary document. The transform step
(`transforms/nebcal_transform.py`) should attempt to extract calibration
series from it, or fall back to reconstructing them from the paper's
cited data sources.
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


SUPPLEMENT_URL = (
    "https://journals.plos.org/plosone/article/file"
    "?type=supplementary&id=10.1371/journal.pone.0275865.s001"
)


def fetch_nebel_supplement(
    config: PipelineConfig,
) -> FetchResult:
    """Download Nebel 2023 supplementary information document.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = "nebel_2023_supplement"
    t0 = time.time()

    try:
        content, sha, cache_hit = fetch_with_cache(
            url=SUPPLEMENT_URL,
            cache_dir=config.cache_dir,
            source_id=source_id,
            ttl_days=config.cache_ttl_days,
            timeout=60,  # 3.7MB file
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

    # Store metadata about the downloaded file
    df = pd.DataFrame({
        "source_id": [source_id],
        "source_variable": ["nebel_2023_supplementary_info"],
        "file_type": ["docx"],
        "file_size_bytes": [len(content)],
        "content_hash": [sha or ""],
        "fetched_at": [datetime.now(timezone.utc).isoformat()],
        "note": [
            "Supplementary information document (docx). "
            "Raw calibration data series may need to be extracted from "
            "tables/figures or reconstructed from cited data sources."
        ],
    })

    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "nebel_2023", "PLOS_ONE_2023",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=SUPPLEMENT_URL, fmt="docx",
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
