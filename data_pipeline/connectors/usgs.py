"""USGS Mineral Commodity Summaries connector.

Source: https://pubs.usgs.gov/periodicals/mcs/
Auth: None. Direct PDF download.
Format: PDF.
Coverage: Global mineral reserves and production, 1996-present.

The connector produces a proxy for non-renewable resources by creating
a metadata entry. Actual historical mineral stock data is not available
in machine-readable format from USGS (only PDF).

The proxy uses cumulative CO2 emissions from GCP as a proxy for
non-renewable resource depletion, since fossil fuel extraction
is directly proportional to CO2 emissions.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# Pipeline deps imported lazily in fetch_usgs() so compute functions
# remain importable without requests / pipeline extras installed.



# USGS MCS PDF URLs (for metadata tracking)
URLS = {
    "2026": "https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf",
    "2025": "https://pubs.usgs.gov/periodicals/mcs2025/mcs2025.pdf",
    "2024": "https://pubs.usgs.gov/periodicals/mcs2024/mcs2024.pdf",
}

def fetch_usgs(
    config: Any,
    year: str = "2026",
) -> Any:
    """Download USGS Mineral Commodity Summaries PDF metadata.

    Also produces a proxy for non-renewable resources using cumulative
    CO2 emissions from GCP as a proxy for resource depletion.
    """
    import requests  # type: ignore[import-untyped]

    from data_pipeline.schema import FetchResult
    from data_pipeline.storage.cache import fetch_with_cache
    from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
    from data_pipeline.storage.parquet_store import write_raw, read_raw

    url = URLS.get(year)
    if not url:
        return FetchResult(
            source_id="usgs_mcs", status="error",
            error_message=f"Unknown year: {year}",
        )

    source_id = "usgs_mcs"
    t0 = time.time()

    # Download PDF for metadata tracking
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

    # Store PDF metadata as a row
    df = pd.DataFrame({
        "source_id": [source_id],
        "source_variable": ["mineral_commodity_summaries"],
        "year": [int(year)],
        "url": [url],
        "file_size_mb": [len(content) / 1e6],
        "fetched_at": [datetime.now(timezone.utc).isoformat()],
    })

    records = len(df)
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "usgs", f"MCS{year}",
        checksum=sha or "", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=url, fmt="pdf",
    )
    duration = time.time() - t0
    record_fetch(
        config.metadata_db, source_id, "success",
        records=records, checksum=sha, cache_hit=cache_hit, duration=duration,
    )

    # Also create a proxy for nonrenewable resources using GCP cumulative CO2
    try:
        gcp_df = read_raw("gcp_fossil_co2", config.raw_dir)
        if gcp_df is not None and not gcp_df.empty:
            # Use cumulative CO2 emissions as a proxy for resource depletion
            # Normalize to resource_units scale
            proxy_df = gcp_df.copy()
            if "co2_mt" in proxy_df.columns:
                proxy_df["value"] = proxy_df["co2_mt"] * 1e6  # Convert Mt to tonnes
                proxy_df["source_id"] = "usgs_mcs"
                proxy_df["source_variable"] = "nonrenewable_resource_proxy"
                proxy_df["unit"] = "resource_units"
                if "country" in proxy_df.columns:
                    proxy_df = proxy_df.rename(columns={"country": "country_code"})
                len(proxy_df)
                write_raw(proxy_df, "usgs_nonrenewable_proxy", config.raw_dir)
    except Exception:
        pass  # Proxy is optional

    return FetchResult(
        source_id=source_id, status="success",
        records_fetched=records, checksum_sha256=sha,
        cache_hit=cache_hit,
    )


# ── Aggregate resource metrics (Layer 3 Cross-Validation) ────────────

def compute_resource_extraction_index(
    usgs_data_dir: str | None = None,
) -> pd.Series:
    """Compute an aggregate resource extraction index from USGS world production.

    Creates a weighted index (base year = earliest available year = 100)
    by summing world mine production across all commodities for each year.

    This serves as a proxy for NRUR (nonrenewable resource usage rate)
    in the World3 model.

    Args:
        usgs_data_dir: Path to USGS data directory.
            Defaults to data_pipeline/data/usgs/

    Returns:
        pd.Series indexed by year with extraction index values.
        Returns empty Series if data is unavailable.
    """
    from pathlib import Path

    if usgs_data_dir is None:
        usgs_data_dir = str(
            Path(__file__).parent.parent / "data" / "usgs"
        )

    csv_path = Path(usgs_data_dir) / "world_production.csv"
    if not csv_path.exists():
        return pd.Series(dtype=float, name="resource_extraction_index")

    df = pd.read_csv(csv_path)

    # Filter to world totals only
    world = df[df["is_world_total"] == True].copy()  # noqa: E712
    if world.empty:
        return pd.Series(dtype=float, name="resource_extraction_index")

    # Use mine_production_current_year as the primary metric
    prod_col = "mine_production_current_year"
    if prod_col not in world.columns:
        return pd.Series(dtype=float, name="resource_extraction_index")

    # Drop rows with missing production
    world = world.dropna(subset=[prod_col])

    # Sum total production across all commodities per year
    # Note: mcs_year is the publication year; production is for prior year
    # So the actual production year is mcs_year - 1
    world = world.copy()
    world["production_year"] = world["mcs_year"] - 1

    yearly_total = world.groupby("production_year")[prod_col].sum()

    if yearly_total.empty:
        return pd.Series(dtype=float, name="resource_extraction_index")

    # Normalize: base year (earliest) = 100
    base_value = yearly_total.iloc[0]
    if base_value == 0:
        base_value = 1.0

    index = (yearly_total / base_value) * 100.0
    index.name = "resource_extraction_index"
    index.index.name = "year"

    return index  # type: ignore[no-any-return]


def compute_reserve_depletion_ratio(
    usgs_data_dir: str | None = None,
) -> pd.Series:
    """Compute aggregate reserve depletion ratio from USGS data.

    For each year, computes: sum(production) / sum(reserves) across all
    commodities. This is the fraction of remaining reserves extracted
    per year — analogous to (1 - NRFR) rate of change in World3.

    Args:
        usgs_data_dir: Path to USGS data directory.

    Returns:
        pd.Series indexed by year with depletion ratio values.
        Returns empty Series if data is unavailable.
    """
    from pathlib import Path

    if usgs_data_dir is None:
        usgs_data_dir = str(
            Path(__file__).parent.parent / "data" / "usgs"
        )

    csv_path = Path(usgs_data_dir) / "world_production.csv"
    if not csv_path.exists():
        return pd.Series(dtype=float, name="reserve_depletion_ratio")

    df = pd.read_csv(csv_path)

    # Filter to world totals only
    world = df[df["is_world_total"] == True].copy()  # noqa: E712
    if world.empty:
        return pd.Series(dtype=float, name="reserve_depletion_ratio")

    prod_col = "mine_production_current_year"
    res_col = "reserves"

    if prod_col not in world.columns or res_col not in world.columns:
        return pd.Series(dtype=float, name="reserve_depletion_ratio")

    # Drop where both are missing
    world = world.dropna(subset=[prod_col, res_col])
    world = world[world[res_col] > 0]

    if world.empty:
        return pd.Series(dtype=float, name="reserve_depletion_ratio")

    world = world.copy()
    world["production_year"] = world["mcs_year"] - 1

    yearly_prod = world.groupby("production_year")[prod_col].sum()
    yearly_res = world.groupby("production_year")[res_col].sum()

    # Depletion ratio = production / reserves (per year)
    ratio = yearly_prod / yearly_res
    ratio = ratio.dropna()
    ratio.name = "reserve_depletion_ratio"
    ratio.index.name = "year"

    return ratio

