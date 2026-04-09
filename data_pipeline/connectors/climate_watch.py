"""Climate Watch / WRI connector — GHG Emissions.

Source: https://www.climatewatchdata.org/ghg-emissions
Auth: None. Direct CSV download.
Format: CSV.
Coverage: 1990-present, all countries, sector breakdowns.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.cache import fetch_with_cache
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Climate Watch API endpoint for GHG emissions
URL = "https://www.climatewatchdata.org/ghg-emissions"


def fetch_climate_watch(
    config: PipelineConfig,
) -> FetchResult:
    """Fetch Climate Watch GHG emissions data.

    Note: Climate Watch uses a GraphQL API that requires session tokens.
    This connector serves as a manual download helper.
    """
    source_id = "climate_watch"
    t0 = time.time()

    return FetchResult(
        source_id=source_id, status="skipped",
        error_message=(
            "Climate Watch requires authentication for API access. "
            "Download data manually from https://www.climatewatchdata.org/ghg-emissions "
            "or use EDGAR/PRIMAP data as alternatives."
        ),
    )
