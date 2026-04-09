"""NASA Earthdata connector — Global temperature and climate datasets.

Source: https://earthdata.nasa.gov/
Auth: NASA Earthdata Login required (free registration).
Format: NetCDF, HDF, CSV.
Coverage: Various global climate datasets.

Note: This connector currently provides a manual download helper.
The automated API requires:
1. Free NASA Earthdata Login registration
2. Token-based authentication
3. NetCDF file parsing (netCDF4 library)

When the above prerequisites are met, the connector can auto-download
from the GES DISC and PO.DAAC archives.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from data_pipeline.config import PipelineConfig
from data_pipeline.schema import FetchResult
from data_pipeline.storage.metadata_db import init_db, record_fetch, record_source_version
from data_pipeline.storage.parquet_store import write_raw


# Key NASA Earthdata datasets relevant to pyWorldX
DATASETS = {
    "giss_temp": {
        "name": "GISTEMP Surface Temperature Analysis",
        "url": "https://data.giss.nasa.gov/gistemp/",
        "format": "CSV",
        "coverage": "1880-present, global monthly temp anomaly",
        "note": "Already available via nasa_giss connector",
    },
    "merra2": {
        "name": "MERRA-2 Reanalysis",
        "url": "https://disc.gsfc.nasa.gov/datasets?project=MERRA-2",
        "format": "NetCDF/HDF",
        "coverage": "1980-present, global atmospheric variables",
        "note": "Requires NASA Earthdata Login + netCDF4",
    },
    "ceres_ebaf": {
        "name": "CERES EBAF Surface Radiative Fluxes",
        "url": "https://ceres.larc.nasa.gov/data/",
        "format": "NetCDF",
        "coverage": "2000-present, surface energy balance",
        "note": "Requires NASA Earthdata Login + netCDF4",
    },
}


def fetch_nasa_earthdata(
    config: PipelineConfig,
    dataset: str = "merra2",
    local_file: Optional[Path] = None,
) -> FetchResult:
    """Fetch NASA Earthdata (manual download helper).

    Args:
        config: Pipeline configuration.
        dataset: Dataset key from DATASETS dict.
        local_file: Path to manually downloaded file.

    Returns:
        FetchResult with status and metadata.
    """
    dataset_info = DATASETS.get(dataset)
    if not dataset_info:
        return FetchResult(
            source_id=f"nasa_earthdata_{dataset}", status="error",
            error_message=f"Unknown dataset: {dataset}",
        )

    source_id = f"nasa_earthdata_{dataset}"

    if local_file is None:
        local_file = config.raw_dir / f"nasa_earthdata_{dataset}.nc"

    if not local_file.exists():
        return FetchResult(
            source_id=source_id, status="skipped",
            error_message=(
                f"File not found: {local_file}. "
                f"Download {dataset_info['name']} from {dataset_info['url']} "
                f"Format: {dataset_info['format']}. "
                f"Coverage: {dataset_info['coverage']}. "
                f"Requires free NASA Earthdata Login registration."
            ),
        )

    t0 = time.time()

    # For now, store as metadata row since NetCDF parsing requires netCDF4
    df = pd.DataFrame({
        "source_id": [source_id],
        "source_variable": [dataset],
        "url": [dataset_info["url"]],
        "format": [dataset_info["format"]],
        "coverage": [dataset_info["coverage"]],
        "file_size_mb": [local_file.stat().st_size / 1e6],
        "fetched_at": [datetime.now(timezone.utc).isoformat()],
    })

    records = len(df)
    write_raw(df, source_id, config.raw_dir)

    init_db(config.metadata_db)
    record_source_version(
        config.metadata_db, "nasa_earthdata", dataset,
        checksum="", records=records,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        url=dataset_info["url"], fmt=dataset_info["format"],
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
    """Fetch all NASA Earthdata datasets."""
    results = []
    for dataset in DATASETS:
        result = fetch_nasa_earthdata(config, dataset)
        results.append(result)
    return results
