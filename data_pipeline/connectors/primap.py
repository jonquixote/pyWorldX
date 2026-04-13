"""PRIMAP-hist connector — National historical GHG emissions.

Source: Zenodo record 10705513 (PRIMAP-hist v2.5.1 final)
URL: https://zenodo.org/record/10705513
Auth: None. Direct CSV download.
Format: CSV (long format).
Coverage: 1750–2022, 200+ countries, 42 IPCC categories.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Zenodo record 10705513 — PRIMAP-hist v2.5.1 final release
# Check https://zenodo.org/record/10705513 if URL changes.
URL = (
    "https://zenodo.org/api/records/10705513/files/"
    "Guetschow_et_al_2024-PRIMAP-hist_v2.5.1_final_no_rounding_27-Feb-2024.csv"
    "/content"
)


def fetch_primap(
    config: PipelineConfig,
    gas: Optional[str] = None,
    country: Optional[str] = None,
) -> FetchResult:
    """Download PRIMAP-hist national GHG emissions.

    Args:
        config: Pipeline configuration.
        gas: If provided, filter to this gas (e.g. "CO2", "CH4", "N2O").
        country: If provided, filter to this ISO3 country code.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = "primap_hist"
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
    text = content.decode("utf-8")
    df = pd.read_csv(io.StringIO(text))

    # Standardize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Apply filters
    if gas:
        for col in ["gas", "gas_code"]:
            if col in df.columns:
                df = df[df[col].str.upper() == gas.upper()]
                break

    if country:
        for col in ["country", "iso3", "country_code"]:
            if col in df.columns:
                df = df[df[col].str.upper() == country.upper()]
                break

    # Add metadata
    df["source_id"] = source_id
    df["source_variable"] = "ghg_emissions_multi_gas"
    records = len(df)

    # Write to raw store
    write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "primap", "v2.5.1",
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
