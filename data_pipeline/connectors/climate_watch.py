"""Climate Watch / WRI connector — GHG Emissions.

Source: https://www.climatewatchdata.org/ghg-emissions
Auth: None. Direct CSV download.
Format: CSV.
Coverage: 1990-present, all countries, sector breakdowns.
"""

from __future__ import annotations

import time


from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult


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
    time.time()

    return FetchResult(
        source_id=source_id, status="skipped",
        error_message=(
            "Climate Watch requires authentication for API access. "
            "Download data manually from https://www.climatewatchdata.org/ghg-emissions "
            "or use EDGAR/PRIMAP data as alternatives."
        ),
    )
