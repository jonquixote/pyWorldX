"""Our World in Data (OWID) connector.

Sources:
- OWID Search API: https://search.owid.io/indicators
- OWID Catalog: https://catalog.ourworldindata.org/

Auth: None.

The search API returns metadata including parquet_url for each indicator.
This connector follows the parquet URLs to download actual time series data.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


SEARCH_URL = "https://search.owid.io/indicators"

# Key search terms for pyWorldX — with entity names
KEY_SEARCHES = {
    "primary_energy": {"q": "primary energy consumption", "kind": "indicator"},
    "fossil_co2": {"q": "fossil co2 emissions", "kind": "indicator"},
    "co2_per_capita": {"q": "co2 per capita", "kind": "indicator"},
    "gdp_maddison": {"q": "gdp per capita maddison", "kind": "indicator"},
    "population": {"q": "population total", "kind": "indicator"},
    "life_expectancy": {"q": "life expectancy", "kind": "indicator"},
}


def search_owid(
    query: str,
    kind: str = "indicator",
    limit: int = 10,
) -> list[dict]:
    """Search OWID indicators."""
    params = {"q": query, "kind": kind}
    r = requests.get(SEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = data.get("results", [])
    return results[:limit]


def _download_owid_parquet(parquet_url: str) -> pd.DataFrame:
    """Download and parse an OWID catalog parquet file.
    
    Returns DataFrame with columns: [entity, year, {column_name}]
    """
    r = requests.get(parquet_url, timeout=120)
    r.raise_for_status()
    
    # Parse parquet
    df = pd.read_parquet(io.BytesIO(r.content))
    return df


def fetch_owid_search(
    config: PipelineConfig,
    search_key: str = "primary_energy",
) -> FetchResult:
    """Fetch OWID search results and follow parquet URLs to download actual data.
    
    Args:
        config: Pipeline configuration.
        search_key: Key from KEY_SEARCHES dict.

    Returns:
        FetchResult with status and metadata.
    """
    search_params = KEY_SEARCHES.get(search_key, {"q": search_key, "kind": "indicator"})
    source_id = f"owid_search_{search_key}"
    t0 = time.time()

    # Step 1: Search for indicators
    try:
        results = search_owid(
            query=search_params["q"],
            kind=search_params["kind"],
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

    if not results:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No OWID results found.",
        )

    # Step 2: Download parquet data from top result
    best_result = results[0]
    parquet_url = best_result.get("metadata", {}).get("parquet_url", "")
    column_name = best_result.get("metadata", {}).get("column", "")
    indicator_id = best_result.get("indicator_id", 0)
    
    if not parquet_url or not column_name:
        # Fall back to storing search metadata
        df = pd.DataFrame(results)
        df["source_id"] = source_id
        df["source_variable"] = search_key
        records = len(df)
        
        write_raw(df, source_id, config.raw_dir)
        init_db(config.metadata_db)
        record_source_version(
            config.metadata_db, "owid", f"search_{search_key}",
            checksum="", records=records,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            url=SEARCH_URL, fmt="json",
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

    # Step 3: Download actual data
    try:
        data_df = _download_owid_parquet(parquet_url)
        
        # Standardize columns
        # OWID parquet typically has: [country, year, {column_name}]
        renamed = {}
        if "country" in data_df.columns:
            renamed["country"] = "country_code"
        if column_name in data_df.columns:
            renamed[column_name] = "value"
        
        if renamed:
            data_df = data_df.rename(columns=renamed)
        
        # Filter to world/Global if available
        if "country_code" in data_df.columns:
            world_codes = ["World", "Global"]
            world_mask = data_df["country_code"].isin(world_codes)
            if world_mask.any():
                data_df = data_df[world_mask].copy()
        
        # Ensure numeric year and value
        if "year" in data_df.columns:
            data_df["year"] = pd.to_numeric(data_df["year"], errors="coerce")
        if "value" in data_df.columns:
            data_df["value"] = pd.to_numeric(data_df["value"], errors="coerce")
        
        # Drop rows with missing year or value
        data_df = data_df.dropna(subset=["year", "value"])
        
        # Add metadata
        data_df["source_id"] = source_id
        data_df["source_variable"] = search_key
        data_df["indicator_id"] = indicator_id
        if column_name:
            data_df["original_column"] = column_name
        
        records = len(data_df)
        write_raw(data_df, source_id, config.raw_dir)
        
        init_db(config.metadata_db)
        record_source_version(
            config.metadata_db, "owid", f"indicator_{indicator_id}",
            checksum="", records=records,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            url=parquet_url, fmt="parquet",
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
        
    except (requests.RequestException, Exception):
        duration = time.time() - t0
        # Fall back to search metadata
        df = pd.DataFrame(results)
        df["source_id"] = source_id
        df["source_variable"] = search_key
        records = len(df)
        
        write_raw(df, source_id, config.raw_dir)
        init_db(config.metadata_db)
        record_source_version(
            config.metadata_db, "owid", f"search_{search_key}",
            checksum="", records=records,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            url=SEARCH_URL, fmt="json",
        )
        record_fetch(
            config.metadata_db, source_id, "success",
            records=records, checksum="", cache_hit=False, duration=duration,
        )
        return FetchResult(
            source_id=source_id, status="success",
            records_fetched=records,
        )


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch OWID search results for all predefined pyWorldX queries."""
    results = []
    for key in KEY_SEARCHES:
        result = fetch_owid_search(config, search_key=key)
        results.append(result)
    return results


# ── Direct Indicator Fetch ─────────────────────────────────────────

# Direct indicator IDs for specific data not available via search
DIRECT_INDICATORS = {
    "daily_caloric_supply": 1205780,  # Daily calorie supply per person (kcal), 1274-2023
}


def fetch_owid_indicator(
    config: PipelineConfig,
    indicator_key: str = "daily_caloric_supply",
) -> FetchResult:
    """Fetch a specific OWID indicator by ID.

    Useful for indicators not easily found via search API.

    Args:
        config: Pipeline configuration.
        indicator_key: Key from DIRECT_INDICATORS dict.

    Returns:
        FetchResult with status and metadata.
    """
    indicator_id = DIRECT_INDICATORS.get(indicator_key)
    if not indicator_id:
        return FetchResult(
            source_id=f"owid_{indicator_key}", status="error",
            error_message=f"Unknown OWID indicator: {indicator_key}",
        )

    source_id = f"owid_{indicator_key}"
    url = f"https://api.ourworldindata.org/v1/indicators/{indicator_id}.data.json"
    t0 = time.time()

    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        data = r.json()
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

    # Parse OWID data format: {values, years, entities}
    values = data.get("values", [])
    years = data.get("years", [])
    entities = data.get("entities", [])

    if not values or not years or not entities:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No data in OWID response.",
        )

    # Build DataFrame
    records = []
    for i, val in enumerate(values):
        year_idx = i % len(years)
        entity_idx = i // len(years)
        if entity_idx < len(entities):
            records.append({
                "entity": entities[entity_idx],
                "year": years[year_idx],
                "value": val,
            })

    df = pd.DataFrame(records)
    df["source_id"] = source_id
    df["source_variable"] = indicator_key
    records_count = len(df)

    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "owid", f"indicator_{indicator_id}",
        checksum="", records=records_count,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="json",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records_count, checksum="", cache_hit=False, duration=duration,
    )

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records_count,
    )
