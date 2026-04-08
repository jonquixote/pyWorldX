"""Our World in Data (OWID) connector.

Sources:
- OWID Search API: https://search.owid.io/indicators
- OWID Chart pages: https://ourworldindata.org/grapher/{slug}

Auth: None.

⚠️ NOTE: As of April 2026, OWID's direct chart data export URLs have changed.
The `owid-catalog` library is the recommended access method but has a Python
version constraint (<3.15) that may conflict with newer Python installations.

This connector provides the OWID search API functionality for discovering
indicators and charts. Chart data downloads should use the `owid-catalog`
library or manual CSV downloads from chart pages.
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


SEARCH_URL = "https://search.owid.io/indicators"

# Key search terms for pyWorldX
KEY_SEARCHES = {
    "primary_energy": {"q": "primary energy", "kind": "indicator"},
    "fossil_co2": {"q": "fossil co2 emissions", "kind": "indicator"},
    "co2_per_capita": {"q": "co2 per capita", "kind": "indicator"},
    "gdp_maddison": {"q": "gdp per capita maddison", "kind": "indicator"},
    "population": {"q": "population", "kind": "indicator"},
    "life_expectancy": {"q": "life expectancy", "kind": "indicator"},
}


def search_owid(
    query: str,
    kind: str = "indicator",
    limit: int = 10,
) -> list[dict]:
    """Search OWID indicators.

    Args:
        query: Search query string.
        kind: "indicator" or "table".
        limit: Maximum results to return.

    Returns:
        List of indicator metadata dicts.
    """
    params = {"q": query, "kind": kind}
    r = requests.get(SEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = data.get("results", [])
    return results[:limit]


def fetch_owid_search(
    config: PipelineConfig,
    search_key: str = "primary_energy",
) -> FetchResult:
    """Fetch OWID search results for a predefined query.

    Stores the search results (indicator metadata) as a DataFrame.
    The actual data must be fetched separately via the `owid-catalog`
    library or manual chart downloads.

    Args:
        config: Pipeline configuration.
        search_key: Key from KEY_SEARCHES dict.

    Returns:
        FetchResult with status and metadata.
    """
    search_params = KEY_SEARCHES.get(search_key, {"q": search_key, "kind": "indicator"})
    source_id = f"owid_search_{search_key}"
    t0 = time.time()

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

    df = pd.DataFrame(results)
    df["source_id"] = source_id
    df["source_variable"] = search_key
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
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


def fetch_all(config: PipelineConfig) -> list[FetchResult]:
    """Fetch OWID search results for all predefined pyWorldX queries."""
    results = []
    for key in KEY_SEARCHES:
        result = fetch_owid_search(config, search_key=key)
        results.append(result)
    return results
