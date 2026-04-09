"""Penn World Table connector — PWT 11.0.

Source: https://www.rug.nl/ggdc/productivity/pwt/
Auth: None. Direct download via DataverseNL API.
Format: Stata (.dta).
Coverage: 185 countries, 1950-2019.
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


# DataverseNL API for PWT 11.0
DATAVERSE_API = "https://dataverse.nl/api/datasets/:persistentId/?persistentId=doi:10.34894/FABVLR"
DATAVERSE_DOWNLOAD = "https://dataverse.nl/api/access/datafile/{file_id}"

# Main PWT Stata file
MAIN_FILE_ID = 554030  # pwt110.dta


def fetch_pwt(
    config: PipelineConfig,
) -> FetchResult:
    """Download Penn World Table 11.0 via DataverseNL API."""
    source_id = "pwt"
    t0 = time.time()

    try:
        # Get dataset metadata
        r = requests.get(DATAVERSE_API, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK":
            return FetchResult(
                source_id=source_id, status="error",
                error_message=f"Dataverse API error: {data.get('message', 'Unknown')}",
            )

        # Download the main PWT Stata file
        download_url = DATAVERSE_DOWNLOAD.format(file_id=MAIN_FILE_ID)
        content_r = requests.get(download_url, timeout=120)
        content_r.raise_for_status()
        content = content_r.content

        # Parse Stata file
        df = pd.read_stata(io.BytesIO(content))
        df["source_id"] = source_id
        df["source_variable"] = "pwt110"
        records = len(df)

        # Write to raw store
        raw_path = write_raw(df, source_id, config.raw_dir)

        init_db(config.metadata_db)
        record_source_version(
            config.metadata_db, "pwt", "11.0",
            checksum="", records=records,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            url=download_url, fmt="dta",
        )
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "success",
            records=records, checksum="", cache_hit=False, duration=duration,
        )

        return FetchResult(
            source_id=source_id, status="success",
            records_fetched=records,
        )

    except (requests.RequestException, ValueError) as e:
        duration = time.time() - t0
        record_fetch(
            config.metadata_db, source_id, "error",
            error_message=str(e), duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="error",
            error_message=str(e), cache_hit=False,
        )
