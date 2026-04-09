"""NASA GISS Surface Temperature connector.

Source: https://data.giss.nasa.gov/gistemp/
Auth: None. Direct text file download.
Format: Plain text with comment lines.
Coverage: 1880-present, global and zonal means.
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


URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.txt"


def fetch_nasa_giss(
    config: PipelineConfig,
) -> FetchResult:
    """Download NASA GISS global surface temperature anomalies."""
    source_id = "nasa_giss"
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

    # Parse text file — format is fixed-width with 18 columns
    # Year Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec J-D D-N DJF MAM JJA SON Year
    lines = content.decode("utf-8", errors="replace").split("\n")

    # Skip header lines (first 7 lines), then data lines until blank line
    col_names = ["year", "jan", "feb", "mar", "apr", "may", "jun",
                  "jul", "aug", "sep", "oct", "nov", "dec", "annual"]
    records = []
    for line in lines[7:]:
        line = line.strip()
        if not line or line.startswith("Divide") or line.startswith("Multiply") or line.startswith("Example"):
            break
        parts = line.split()
        if len(parts) >= 14 and parts[0].isdigit():
            row = {"year": int(parts[0])}
            # Annual anomaly is column 14 (0-indexed: 13)
            if len(parts) > 13:
                val = parts[13]
                if val != "*****" and val != "***":
                    row["anomaly_c"] = float(val) / 100.0
                    records.append(row)

    df = pd.DataFrame(records)
    df["anomaly_c"] = pd.to_numeric(df["anomaly_c"], errors="coerce")
    df = df.dropna(subset=["anomaly_c"])
    df["source_id"] = source_id
    df["source_variable"] = "surface_temperature_anomaly"
    records_count = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "nasa_giss", "GISTEMP_v4",
        checksum=sha or "", records=records_count,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=URL, fmt="txt",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records_count, checksum=sha, cache_hit=cache_hit, duration=duration,
    )

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records_count, checksum_sha256=sha,
        cache_hit=cache_hit,
    )
