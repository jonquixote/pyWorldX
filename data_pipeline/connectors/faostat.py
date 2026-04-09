"""FAOSTAT connector — Food Balance Sheets and bulk data.

Source: https://data.apps.fao.org/
Auth: Bearer token (FAOSTAT_TOKEN in .env).
API: https://faostatservices.fao.org/api/v1/en/
Format: JSON.

New API (April 2026):
- Discovery: GET /groupsanddomains
- Data: GET /data/{domainCode}?area={area}&item={item}&element={element}&year={year}
- Auth: Authorization: Bearer {token}

World area code: 5000
Key elements for FBS:
  - 511: Total Population (item 2501)
  - 664: Food supply (kcal/capita/day) (element only, no item filter → Grand Total)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


BASE_URL = "https://faostatservices.fao.org/api/v1/en"
WORLD_AREA = "5000"

# Domain configurations: list of param sets to query
DOMAIN_QUERIES = {
    "food_balance": {
        "domain": "FBS",
        "name": "Food Balance Sheets",
        "queries": [
            # Food supply (kcal/capita/day) — element 664, all products (Grand Total)
            {"element": "664"},
            # Population — item 2501, element 511
            {"item": "2501", "element": "511"},
        ],
    },
    "production": {
        "domain": "QCL",
        "name": "Production: Crops and Livestock",
        "queries": [
            # Wheat production — item 15, element 5510
            {"item": "15", "element": "5510"},
        ],
    },
    "land_use": {
        "domain": "RL",
        "name": "Land Use",
        "queries": [
            # Arable land — item 4035, element 5111
            {"item": "4035", "element": "5111"},
        ],
    },
}


def _get_token(config: PipelineConfig) -> Optional[str]:
    """Get FAOSTAT Bearer token from config or env."""
    if config.faostat_token:
        return config.faostat_token
    import os
    return os.environ.get("FAOSTAT_TOKEN")


def fetch_faostat(
    config: PipelineConfig,
    domain: str = "food_balance",
    start_year: int = 1961,
    end_year: int = 2024,
) -> FetchResult:
    """Fetch FAOSTAT data via the new Bearer-token API.

    Queries in 10-year chunks to avoid API limits.

    Args:
        config: Pipeline configuration.
        domain: Domain key from DOMAIN_QUERIES dict.
        start_year: First year to fetch.
        end_year: Last year to fetch.

    Returns:
        FetchResult with status and metadata.
    """
    domain_config = DOMAIN_QUERIES.get(domain)
    if not domain_config:
        return FetchResult(
            source_id=f"faostat_{domain}", status="error",
            error_message=f"Unknown domain: {domain}",
        )

    token = _get_token(config)
    if not token:
        return FetchResult(
            source_id=f"faostat_{domain}", status="error",
            error_message="FAOSTAT_TOKEN not set. Add to .env.",
        )

    source_id = f"faostat_{domain}"
    domain_code = domain_config["domain"]
    t0 = time.time()

    # Fetch all query sets for this domain
    all_records = []

    # Query in chunks of 10 years to avoid API limits
    years = list(range(start_year, end_year + 1))
    chunk_size = 10
    year_chunks = [years[i:i+chunk_size] for i in range(0, len(years), chunk_size)]

    for query in domain_config["queries"]:
        for year_chunk in year_chunks:
            url = f"{BASE_URL}/data/{domain_code}"
            year_list = ",".join(str(y) for y in year_chunk)
            params = {
                "area": WORLD_AREA,
                "year": year_list,
            }
            params.update(query)

            headers = {"Authorization": f"Bearer {token}"}

            try:
                r = requests.get(url, params=params, headers=headers, timeout=60)
                r.raise_for_status()
                data = r.json()
            except requests.HTTPError as e:
                if "403" in str(e):
                    return FetchResult(
                        source_id=source_id, status="skipped",
                        error_message=(
                            "FAOSTAT API token expired or revoked (403 Forbidden). "
                            "Food supply data is available via OWID daily caloric supply "
                            "(1274-2023) which covers the full Nebel calibration window. "
                            "To fix: refresh your FAOSTAT Bearer token at "
                            "https://data.apps.fao.org/ or rely on OWID fallback."
                        ),
                    )
                duration = time.time() - t0
                record_fetch(
                    config.metadata_db, source_id, "error",
                    error_message=str(e), duration=duration,
                )
                return FetchResult(
                    source_id=source_id, status="error",
                    error_message=f"FAOSTAT API error: {e}",
                )
            except (requests.RequestException, ValueError) as e:
                duration = time.time() - t0
                record_fetch(
                    config.metadata_db, source_id, "error",
                    error_message=str(e), duration=duration,
                )
                return FetchResult(
                    source_id=source_id, status="error",
                    error_message=f"FAOSTAT API error: {e}",
                )

            # Response: {"metadata": {...}, "data": [...]}
            records_list = data.get("data", [])
            all_records.extend(records_list)

    if not all_records:
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message=(
                f"No data returned from FAOSTAT API for {domain}. "
                f"Check domain code, year range ({start_year}-{end_year}), "
                f"and that the token is valid."
            ),
        )

    df = pd.DataFrame(all_records)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Convert value to numeric
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

    df["source_id"] = source_id
    df["source_variable"] = domain
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    # Record in metadata DB
    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "faostat", f"{domain_code}_2024",
        checksum="", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=f"{BASE_URL}/data/{domain_code}", fmt="json",
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
    """Fetch key FAOSTAT domains."""
    results = []
    for domain in DOMAIN_QUERIES:
        result = fetch_faostat(config, domain=domain)
        results.append(result)
    return results
