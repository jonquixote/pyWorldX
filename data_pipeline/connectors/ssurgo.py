"""USDA NRCS SSURGO / STATSGO2 connector via Soil Data Access (SDA).

Source: https://sdmdataaccess.nrcs.usda.gov/
Auth: None.
Format: JSON.

Fetches macroscopic biophysical limits of soil, specifically 
extractable phosphorus and Soil Organic Carbon (SOC).
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import datetime, timezone

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw

URL = "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest"


def fetch_ssurgo(config: PipelineConfig) -> FetchResult:
    source_id = "usda_ssurgo_phosphorus_soc"
    t0 = time.time()

    # Simple query to get average phosphorus and SOC from STATSGO2 (national)
    # Using a high-level query to avoid massive data download.
    # Note: Join directly from legend to mapunit on lkey.
    query = """
    SELECT TOP 50000
        sa.areasymbol,
        c.chkey,
        c.hzname,
        c.hzdept_r,
        c.hzdepb_r,
        c.om_r as organic_matter_pct,
        c.ph1to1h2o_r as ph_water,
        c.ptotal_r as total_phosphorus,
        c.pbray1_r as bray1_phosphorus
    FROM sacatalog sa
    JOIN legend l ON sa.areasymbol = l.areasymbol
    JOIN mapunit mu ON l.lkey = mu.lkey
    JOIN component comp ON mu.mukey = comp.mukey
    JOIN chorizon c ON comp.cokey = c.cokey
    WHERE c.ptotal_r IS NOT NULL OR c.om_r IS NOT NULL
    """
    
    payload = {
        "query": query,
        "format": "JSON"
    }

    try:
        # SDA API requires form-encoding
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload_encoded = urllib.parse.urlencode(payload)
        r = requests.post(URL, data=payload_encoded, headers=headers, timeout=config.request_timeout_seconds)
        r.raise_for_status()
        data = r.json()
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

    if "Table" not in data or not data["Table"]:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No data returned from SDA.",
        )

    table = data["Table"]
    columns = [
        "areasymbol",
        "chkey",
        "hzname",
        "hzdept_r",
        "hzdepb_r",
        "organic_matter_pct",
        "ph_water",
        "total_phosphorus",
        "bray1_phosphorus"
    ]
    
    # In 'JSON' format, the SDA API just returns rows, not headers
    df = pd.DataFrame(table, columns=columns)
    df["source_id"] = source_id
    df["source_variable"] = "soil_properties"

    records = len(df)
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "usda_ssurgo", "SDA_API",
        checksum="", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=URL, fmt="json",
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
