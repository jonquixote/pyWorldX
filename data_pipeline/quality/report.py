"""Quality report generator — Markdown output."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from data_pipeline.config import PipelineConfig
from data_pipeline.quality.coverage import compute_coverage
from data_pipeline.quality.freshness import compute_freshness
from data_pipeline.storage.parquet_store import list_sources, list_entities


def generate_report(
    config: PipelineConfig,
    output_path: Optional[Path] = None,
) -> str:
    """Generate a Markdown quality report.

    Args:
        config: Pipeline configuration.
        output_path: Optional path to write the report.

    Returns:
        Markdown string.
    """
    lines = []
    lines.append("# Data Quality Report — pyWorldX Calibration Dataset\n")
    lines.append(f"Generated: {pd.Timestamp.now(tz='UTC').isoformat()}\n")

    # Coverage
    lines.append("## Coverage\n")
    coverage = compute_coverage(
        config.raw_dir,
        config.calibration_start,
        config.calibration_end,
    )
    if not coverage.empty:
        lines.append(
            "| Source | Years | Coverage % | Primary Source |"
        )
        lines.append("|--------|-------|------------|----------------|")
        for _, row in coverage.iterrows():
            lines.append(
                f"| {row['source_id']} "
                f"| {row['year_min']}-{row['year_max']} "
                f"| {row['coverage_pct']:.1f}% "
                f"| {row['source_id']} |"
            )
    lines.append("")

    # Freshness
    lines.append("## Freshness\n")
    freshness = compute_freshness(config.metadata_db)
    if not freshness.empty:
        lines.append(
            "| Source | Version | Last Fetched | Age (days) |"
        )
        lines.append("|--------|---------|-------------|------------|")
        for _, row in freshness.iterrows():
            age = row["age_days"] if row["age_days"] is not None else "N/A"
            lines.append(
                f"| {row['source_id']} "
                f"| {row['version']} "
                f"| {row['fetched_at'][:10] if row['fetched_at'] else 'N/A'} "
                f"| {age} |"
            )
    lines.append("")

    # Raw store
    lines.append("## Raw Store\n")
    sources = list_sources(config.raw_dir)
    lines.append(f"Sources fetched: {len(sources)}\n")
    for s in sorted(sources):
        lines.append(f"- {s}")
    lines.append("")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"Calibration period: {config.calibration_start}–{config.calibration_end}")
    lines.append(f"Sources: {len(sources)}")
    lines.append("")

    report = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)

    return report
