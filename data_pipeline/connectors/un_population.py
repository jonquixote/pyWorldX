"""UN Population Division WPP 2024 connector via HDX.

Source: https://data.humdata.org/dataset/world-population-prospects-2024
Auth: None. Direct download via Humanitarian Data Exchange.
Format: CSV.
Coverage: 200+ countries/regions, 1950-2100 (population, fertility, mortality).
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# HDX resource metadata endpoint
HDX_RESOURCE_META = "https://data.humdata.org/dataset/dc7bf928-c6ea-420c-ac44-c3b95de82c49/resource/1556653b-bdd3-4392-8a0a-8a1bd97269db/download_metadata?format=json"


def fetch_un_population(
    config: PipelineConfig,
) -> FetchResult:
    """Download UN World Population Prospects 2024 via HDX."""
    source_id = "un_population"
    t0 = time.time()

    try:
        # Get download URL from HDX
        r = requests.get(HDX_RESOURCE_META, timeout=15)
        r.raise_for_status()
        meta = r.json()
        download_url = meta.get("download_url", "")
        
        if not download_url:
            return FetchResult(
                source_id=source_id, status="error",
                error_message="No download URL in HDX metadata.",
            )

        # Download the CSV/Excel file
        content_r = requests.get(download_url, timeout=300, stream=True)
        content_r.raise_for_status()
        content = content_r.content

        # Parse Excel (WPP 2024 is in Excel format)
        df = pd.read_excel(io.BytesIO(content))
        df["source_id"] = source_id
        df["source_variable"] = "wpp_2024"
        records = len(df)

        write_raw(df, source_id, config.raw_dir)

        init_db(config.metadata_db)
        record_source_version(
            config.metadata_db, "un_population", "WPP2024",
            checksum="", records=records,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            url=download_url, fmt="xlsx",
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
