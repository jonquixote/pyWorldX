"""EIA connector — US Energy Information Administration.

Source: https://api.eia.gov/v2/
Auth: API key required (free registration).
Format: JSON.
Coverage: US energy data 1900-present by fuel type.
"""

from __future__ import annotations

import os
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


BASE_URL = "https://api.eia.gov/v2"

# Key EIA data routes
ROUTES = {
    "total_energy": "/total-energy/data",
    "co2_emissions": "/co2-emissions/data",
}


def _get_api_key(config: PipelineConfig) -> str:
    """Get EIA API key from config or env var."""
    if config.eia_api_key:
        return config.eia_api_key
    return os.environ.get("EIA_API_KEY", "")


def fetch_eia(
    config: PipelineConfig,
    route: str = "total_energy",
    facets: Optional[dict] = None,
    start_year: int = 1900,
    end_year: int = 2024,
) -> FetchResult:
    """Fetch EIA energy data.

    Args:
        config: Pipeline configuration.
        route: Data route key from ROUTES dict.
        facets: Optional facet filters (e.g. {"sourceTypeId": ["Fossil Fuel"]}).
        start_year: First year to fetch.
        end_year: Last year to fetch.

    Returns:
        FetchResult with status and metadata.
    """
    api_key = _get_api_key(config)
    if not api_key:
        return FetchResult(
            source_id=f"eia_{route}", status="error",
            error_message="EIA_API_KEY not set. Add to .env or config.",
        )

    route_path = ROUTES.get(route, f"/{route}/data")
    source_id = f"eia_{route}"
    url = f"{BASE_URL}{route_path}"
    t0 = time.time()

    params = {
        "api_key": api_key,
        "frequency": "annual",
        "data[]": "value",  # Explicit value column
        "start": str(start_year),
        "end": str(end_year),
        "length": 5000,  # Max rows per request
    }
    # Note: EIA v2 API facets require special encoding; skip for now
    if facets:
        for facet_name, facet_values in facets.items():
            for val in facet_values:
                params.setdefault(f"facets[{facet_name}][]", []).append(val)

    try:
        r = requests.get(url, params=params, timeout=120)
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

    # Parse response
    records_list = data.get("response", {}).get("data", [])
    if not records_list:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message="No data returned from EIA.",
        )

    df = pd.DataFrame(records_list)
    df["source_id"] = source_id
    df["source_variable"] = route
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "eia", f"v2_{route}",
        checksum="", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="json",
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


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch all key EIA data routes for pyWorldX."""
    results = []
    # Total energy (no facets to avoid encoding issues)
    result = fetch_eia(
        config, route="total_energy",
        facets=None,
        start_year=1960,
        end_year=2024,
    )
    results.append(result)

    # CO2 emissions
    result = fetch_eia(config, route="co2_emissions", start_year=1960, end_year=2024)
    results.append(result)

    return results
