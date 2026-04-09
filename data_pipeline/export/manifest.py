"""Data manifest — JSON recording of what was collected, when, from where."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from data_pipeline.storage.metadata_db import list_all_sources
from data_pipeline.storage.parquet_store import list_sources, list_entities


def generate_manifest(
    db_path: Path,
    raw_dir: Path,
    aligned_dir: Path,
    output_path: Optional[Path] = None,
    pipeline_version: str = "0.1.0",
    entity_metadata: Optional[dict] = None,
) -> dict:
    """Generate a data manifest JSON.

    Args:
        db_path: Path to the metadata SQLite database.
        raw_dir: Path to the raw Parquet store.
        aligned_dir: Path to the aligned Parquet store.
        output_path: Optional path to write the manifest JSON.
        pipeline_version: Pipeline version string.
        entity_metadata: Optional dict with entity-level metadata
            (sources_used, year_range, blend_method, gap_years, proxy_methods).

    Returns:
        Manifest dict.
    """
    sources = list_all_sources(db_path)
    raw_source_ids = list_sources(raw_dir)
    aligned_entities = list_entities(aligned_dir)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_version": pipeline_version,
        "sources": {},
        "raw_store": raw_source_ids,
        "aligned_entities": aligned_entities,
    }

    # Source details
    for s in sources:
        manifest["sources"][s["source_id"]] = {
            "version": s.get("version", "N/A"),
            "fetched_at": s.get("fetched_at", "N/A"),
            "checksum_sha256": s.get("checksum_sha256", "N/A"),
            "records_fetched": s.get("records_fetched", 0),
            "url": s.get("url", "N/A"),
            "format": s.get("format", "N/A"),
        }

    # Entity metadata
    if entity_metadata:
        manifest["aligned_entities_detail"] = entity_metadata

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

    return manifest
