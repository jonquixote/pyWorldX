"""Berkeley Earth Surface Temperature connector.

Source: https://berkeleyearth.org/data/
Auth: None. Direct text file download.

⚠️ NOTE: As of April 2026, the Berkeley Earth data download servers
are completely unreachable. The main website (berkeleyearth.org) is up
and publishing reports, but the data download endpoints
(berkeleyearth.org/auto/, berkeleyearth.lbl.gov/auto/) return 404/403
or connection timeouts.

This is a DNS/server-level outage affecting all data download endpoints.
The project team is aware and working on a resolution.

In the meantime, use these alternatives:
- NASA GISS: Already available via nasa_giss connector (1880-present)
- OWID temperature: https://ourworldindata.org/grapher/average-temperature-anomaly
- Redivis mirror: https://redivis.com/datasets/1e0a-f4931vvyg (requires auth)

This connector serves as a manual download helper for when the servers
come back online.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


PORTAL_URL = "https://berkeleyearth.org/data/"
ALTERNATIVE = "Use NASA GISS data (nasa_giss connector) as alternative."


def fetch_berkeley_earth(
    config: PipelineConfig,
    local_file: Optional[Path] = None,
) -> FetchResult:
    """Process Berkeley Earth temperature data from a local file.

    The Berkeley Earth data servers are currently unreachable.
    Users must download data manually when servers come back online.

    Args:
        config: Pipeline configuration.
        local_file: Path to the downloaded Global_complete.txt file.

    Returns:
        FetchResult with status and metadata.
    """
    source_id = "berkeley_earth"

    if local_file is None:
        local_file = config.raw_dir / "berkeley_earth_global_complete.txt"

    if not local_file.exists():
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message=(
                f"File not found: {local_file}. "
                f"Berkeley Earth data servers are currently unreachable. "
                f"Check {PORTAL_URL} for server status. "
                f"{ALTERNATIVE}"
            ),
        )

    t0 = time.time()

    # Parse the Berkeley Earth text file
    # Format: Year Month Decimal_Date Anomaly Uncertainty
    text = local_file.read_text(encoding="utf-8", errors="replace")
    df = pd.read_csv(
        io.StringIO(text),
        comment="%",
        sep=r"\s+",
        names=["year", "month", "decimal_date", "anomaly", "uncertainty"],
    )

    df["anomaly"] = pd.to_numeric(df["anomaly"], errors="coerce")
    df = df.dropna(subset=["anomaly"])
    df["source_id"] = source_id
    df["source_variable"] = "temperature_anomaly"
    records = len(df)

    # Write to raw store
    raw_path = write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "berkeley_earth", "complete",
        checksum="", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=PORTAL_URL, fmt="txt",
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
