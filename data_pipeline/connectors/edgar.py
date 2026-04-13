"""EDGAR GHG emissions connector — JRC Emissions Database for Global Atmospheric Research.

Source: https://edgar.jrc.ec.europa.eu/
Auth: None. Direct ZIP download from JRC FTP.
Format: ZIP containing CSV files.
Coverage: 1970-2024, country-level CO2, CH4, N2O, F-gas emissions.

This replaces Climate Watch (api.climatewatchdata.org DNS failure).
"""

from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# EDGAR GHG 2025 download URLs
URLS = {
    "co2": "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/EDGAR_2025_GHG/IEA_EDGAR_CO2_1970_2024.zip",
    "ch4": "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/EDGAR_2025_GHG/EDGAR_CH4_1970_2024.zip",
    "n2o": "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/EDGAR_2025_GHG/EDGAR_N2O_1970_2024.zip",
}


def fetch_edgar(
    config: PipelineConfig,
    gas: str = "co2",
) -> FetchResult:
    """Download EDGAR GHG emissions data."""
    url = URLS.get(gas)
    if not url:
        return FetchResult(
            source_id=f"edgar_{gas}", status="error",
            error_message=f"Unknown gas: {gas}",
        )

    source_id = f"edgar_{gas}"
    t0 = time.time()

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

    # Extract and parse Excel from ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            # Try Excel first, then CSV
            excel_files = [n for n in zf.namelist() if n.endswith(('.xlsx', '.xls'))]
            csv_files = [n for n in zf.namelist() if n.endswith('.csv')]
            
            if excel_files:
                with zf.open(excel_files[0]) as excel_file:
                    df = pd.read_excel(io.BytesIO(excel_file.read()))
            elif csv_files:
                with zf.open(csv_files[0]) as csv_file:
                    df = pd.read_csv(csv_file)
            else:
                return FetchResult(
                    source_id=source_id, status="error",
                    error_message="No Excel or CSV files in EDGAR ZIP.",
                )

    except (zipfile.BadZipFile, Exception) as e:
        duration = time.time() - t0
        return FetchResult(
            source_id=source_id, status="error",
            error_message=f"Could not parse EDGAR ZIP: {e}",
        )

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["source_id"] = source_id
    df["source_variable"] = gas
    records = len(df)

    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "edgar", f"2025_{gas}",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="zip",
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


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch all EDGAR gases."""
    results = []
    for gas in URLS:
        result = fetch_edgar(config, gas=gas)
        results.append(result)
    return results
