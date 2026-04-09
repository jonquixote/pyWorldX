"""IHME Global Burden of Disease connector via OWID API.

Source: https://www.healthdata.org/data-tools-practices/interactive-visuals/gbd-results
Auth: None via OWID. Direct JSON data API.
Format: JSON.
Coverage: 204 countries, 1990-2023 (DALYs, mortality, disease burden).

Note: IHME requires registration for direct GBD data access, but OWID
provides IHME/GBD-sourced indicators (DALYs, child mortality, etc.)
via their public API.
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


# OWID indicators sourced from IHME/GBD data
INDICATORS = {
    "dalys": 563662,  # DALYs (Disability-Adjusted Life Years)
    "child_mortality": 3391,  # Child mortality rate
    "life_expectancy": 3281,  # Life expectancy at birth
}


def fetch_ihme_gbd(
    config: PipelineConfig,
    indicator: str = "dalys",
) -> FetchResult:
    """Download IHME GBD data via OWID API."""
    indicator_id = INDICATORS.get(indicator)
    if not indicator_id:
        return FetchResult(
            source_id=f"ihme_gbd_{indicator}", status="error",
            error_message=f"Unknown indicator: {indicator}",
        )

    source_id = f"ihme_gbd_{indicator}"
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
    df["source_variable"] = indicator
    records_count = len(df)

    raw_path = write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "ihme_gbd", f"2024_{indicator}",
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
