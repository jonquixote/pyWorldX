"""OECD connector via SDMX-JSON API.

Source: https://data.oecd.org/
Auth: None. SDMX-JSON protocol.
Format: JSON (SDMX-JSON format).
Coverage: 1960-2024, 38 OECD countries + partners.
"""

from __future__ import annotations

import json
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


# OECD SDMX-JSON API endpoint
BASE_URL = "https://stats.oecd.org/sdmx-json/data"

# Key OECD datasets for pyWorldX
DATASETS = {
    "sna_table4": "SNA_TABLE4",  # GDP by expenditure
}


def _parse_oecd_sdmx_json(data: dict) -> pd.DataFrame:
    """Parse OECD SDMX-JSON response into DataFrame.
    
    SDMX-JSON structure:
    - series dimensions are indices in the series key
    - observations within each series have time period index as key
    - Need to look up dimension values from structures
    """
    data_section = data.get("data", data)
    datasets = data_section.get("dataSets", [])
    if not datasets:
        return pd.DataFrame()
    
    ds = datasets[0]
    series = ds.get("series", {})
    if not series:
        return pd.DataFrame()
    
    # Get dimension definitions
    structures = data_section.get("structures", [])
    if not structures:
        return pd.DataFrame()
    
    dims = structures[0].get("dimensions", {})
    series_dims = dims.get("series", [])
    obs_dims = dims.get("observation", [])
    
    # Build value lookup for each dimension
    # Values are stored in a nested structure under "series" key
    # For SNA_TABLE4, we need REF_AREA (country), TIME_PERIOD (year), OBS_VALUE
    dim_id_to_idx = {}
    dim_id_to_values = {}
    
    # Get the codelists from the data structure
    # OECD SDMX-JSON v2.0 uses 'links' and 'annotations' for metadata
    # Series key parts map to series_dims by position
    
    records = []
    for series_key, series_data in series.items():
        parts = series_key.split(":")
        
        # Build dimension values for this series
        dim_values = {}
        for i, part in enumerate(parts):
            if i < len(series_dims):
                dim_id = series_dims[i].get("id", f"dim_{i}")
                dim_values[dim_id] = part
        
        # Parse observations within this series
        observations = series_data.get("observations", {})
        for obs_key, obs_values in observations.items():
            if not obs_values:
                continue
            
            record = dict(dim_values)
            
            # Map observation dimension
            for i, part in enumerate(obs_key.split(":")):
                if i < len(obs_dims):
                    dim_id = obs_dims[i].get("id", f"obs_{i}")
                    record[dim_id] = part
            
            # First element is the value
            if isinstance(obs_values, list) and len(obs_values) > 0:
                record["OBS_VALUE"] = obs_values[0]
            
            records.append(record)
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    
    # Convert numeric columns
    if "TIME_PERIOD" in df.columns:
        df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce").astype("Int64")
    if "OBS_VALUE" in df.columns:
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    
    return df


def fetch_oecd(
    config: PipelineConfig,
    dataset: str = "sna_table4",
) -> FetchResult:
    """Fetch OECD data via SDMX-JSON API.

    Args:
        config: Pipeline configuration.
        dataset: Dataset key from DATASETS dict.

    Returns:
        FetchResult with status and metadata.
    """
    dataset_id = DATASETS.get(dataset)
    if not dataset_id:
        return FetchResult(
            source_id=f"oecd_{dataset}", status="error",
            error_message=f"Unknown dataset: {dataset}",
        )

    source_id = f"oecd_{dataset}"
    url = f"{BASE_URL}/{dataset_id}"
    t0 = time.time()

    try:
        content, sha, cache_hit = fetch_with_cache(
            url=url,
            cache_dir=config.cache_dir,
            source_id=source_id,
            ttl_days=config.cache_ttl_days,
            timeout=120,  # OECD can be slow
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

    # Parse SDMX-JSON
    try:
        data = json.loads(content)
        df = _parse_oecd_sdmx_json(data)
    except (json.JSONDecodeError, Exception) as e:
        duration = time.time() - t0
        return FetchResult(
            source_id=source_id, status="error",
            error_message=f"Could not parse OECD SDMX-JSON: {e}",
        )

    if df.empty:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No data in OECD SDMX response.",
        )

    df["source_id"] = source_id
    df["source_variable"] = dataset
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "oecd", dataset_id,
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
