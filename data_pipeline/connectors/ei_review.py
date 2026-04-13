"""EI Statistical Review connector via OWID API.

Source: https://ourworldindata.org/grapher/primary-energy-consumption
Auth: None. Direct JSON data API via OWID.
Format: JSON.
Coverage: 1965-2024, global primary energy consumption.

Note: The Energy Institute's direct download URLs return 403.
This connector uses OWID's energy data API as an alternative.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests  # type: ignore[import-untyped]

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# OWID indicator for primary energy consumption
INDICATOR_ID = 819339  # Primary energy consumption


def fetch_ei_review(
    config: PipelineConfig,
) -> FetchResult:
    """Download energy data via OWID API."""
    source_id = "ei_review"
    url = f"https://api.ourworldindata.org/v1/indicators/{INDICATOR_ID}.data.json"
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
    df["source_variable"] = "primary_energy_consumption"
    records_count = len(df)

    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "ei_review", "2024",
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
