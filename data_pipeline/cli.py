"""pyWorldX Data Pipeline — CLI (Typer)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.cache import clear_cache, cache_status
from data_pipeline.storage.metadata_db import init_db, list_all_sources
from data_pipeline.storage.parquet_store import list_sources, list_entities

app = typer.Typer(
    name="data_pipeline",
    help="pyWorldX data collection, transformation, and export pipeline.",
    add_completion=False,
)


@app.command()
def collect(
    source: Optional[list[str]] = typer.Option(
        None, "--source", "-s",
        help="Specific source(s) to collect (e.g. world_bank, noaa, gcp).",
    ),
    tier: Optional[list[str]] = typer.Option(
        None, "--tier", "-t",
        help="Priority tier: S, A, B, C.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force re-fetch even if cache is fresh.",
    ),
):
    """Fetch data from configured sources."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    sources_to_run = _resolve_sources(source, tier)

    results = []
    for src in sources_to_run:
        typer.echo(f"Fetching: {src}...")
        result = _fetch_source(src, config, force=force)
        results.append(result)
        status_icon = "✅" if result.status == "success" else "❌"
        msg = f"  {status_icon} {result.source_id}: {result.status}"
        if result.cache_hit:
            msg += " (cached)"
        if result.records_fetched:
            msg += f" — {result.records_fetched:,} records"
        if result.error_message:
            msg += f" — {result.error_message}"
        typer.echo(msg)

    # Summary
    success = sum(1 for r in results if r.status == "success")
    typer.echo(f"\nDone: {success}/{len(results)} sources fetched successfully.")


@app.command()
def status():
    """Show cached vs needed sources."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    sources = list_all_sources(config.metadata_db)
    if not sources:
        typer.echo("No sources fetched yet. Run 'collect' first.")
        return

    typer.echo(f"{'Source':<20} {'Version':<15} {'Records':>10} {'Age (hrs)':>10}")
    typer.echo("-" * 60)
    for s in sources:
        age_hrs = _age_hours(s.get("fetched_at"))
        typer.echo(
            f"{s['source_id']:<20} {s.get('version', 'N/A'):<15} "
            f"{s.get('records_fetched', 0):>10,} {age_hrs:>10.1f}"
        )


@app.command()
def clear(
    source: Optional[str] = typer.Option(
        None, "--source", "-s",
        help="Clear cache for a specific source (or 'all').",
    ),
):
    """Clear cached data."""
    config = PipelineConfig()
    src = None if source == "all" else source
    removed = clear_cache(config.cache_dir, src)
    typer.echo(f"Cleared {removed} cache file(s).")


@app.command()
def ls_raw():
    """List sources in the raw Parquet store."""
    config = PipelineConfig()
    sources = list_sources(config.raw_dir)
    if not sources:
        typer.echo("No raw data fetched yet.")
        return
    for s in sources:
        typer.echo(f"  {s}")


@app.command()
def ls_aligned():
    """List entities in the aligned Parquet store."""
    config = PipelineConfig()
    entities = list_entities(config.aligned_dir)
    if not entities:
        typer.echo("No aligned data generated yet.")
        return
    for e in entities:
        typer.echo(f"  {e}")


def _resolve_sources(
    sources: Optional[list[str]],
    tiers: Optional[list[str]],
) -> list[str]:
    """Determine which sources to run."""
    if sources:
        return sources
    # Default: start with the 3 Phase 1 quick wins
    return ["world_bank", "noaa", "gcp"]


def _fetch_source(
    source_id: str,
    config: PipelineConfig,
    force: bool = False,
):
    """Dispatch to the appropriate connector."""
    from data_pipeline.schema import FetchResult

    if source_id == "world_bank":
        from data_pipeline.connectors.world_bank import fetch_all
        results = fetch_all(config)
        return results[0] if results else FetchResult(
            source_id="world_bank", status="error",
            error_message="No indicators fetched",
        )
    elif source_id.startswith("world_bank_"):
        indicator = source_id.replace("world_bank_", "")
        from data_pipeline.connectors.world_bank import INDICATORS, fetch_indicator
        code = INDICATORS.get(indicator, indicator)
        return fetch_indicator(code, config)
    elif source_id.startswith("noaa"):
        from data_pipeline.connectors.noaa import fetch_noaa_co2
        freq = "monthly" if "monthly" in source_id else "annual"
        return fetch_noaa_co2(config, frequency=freq)
    elif source_id == "gcp" or source_id.startswith("gcp_"):
        from data_pipeline.connectors.gcp import fetch_gcp
        return fetch_gcp(config)
    else:
        return FetchResult(
            source_id=source_id, status="error",
            error_message=f"Unknown source: {source_id}",
        )


def _age_hours(fetched_at: Optional[str]) -> float:
    """Calculate hours since fetch."""
    if not fetched_at:
        return -1.0
    try:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(fetched_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return delta.total_seconds() / 3600
    except (ValueError, TypeError):
        return -1.0


if __name__ == "__main__":
    app()
