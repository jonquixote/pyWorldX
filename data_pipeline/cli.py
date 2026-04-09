"""pyWorldX Data Pipeline — CLI (Typer)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
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


@app.command()
def run(
    source: Optional[list[str]] = typer.Option(
        None, "--source", "-s",
        help="Specific source(s) to process.",
    ),
    tier: Optional[list[str]] = typer.Option(
        None, "--tier", "-t",
        help="Priority tier: S, A, B, C.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force re-fetch even if cache is fresh.",
    ),
    skip_collect: bool = typer.Option(
        False, "--skip-collect",
        help="Skip collection, only transform/align/export existing raw data.",
    ),
):
    """Full pipeline: collect → transform → align → export → report."""
    from datetime import datetime, timezone

    config = PipelineConfig()
    init_db(config.metadata_db)

    typer.echo("=" * 60)
    typer.echo("pyWorldX Data Pipeline — Full Run")
    typer.echo(f"Started: {datetime.now(timezone.utc).isoformat()}")
    typer.echo("=" * 60)

    # ── Step 1: Collect ─────────────────────────────────────────
    if not skip_collect:
        typer.echo("\n[1/5] Collecting data...")
        sources_to_run = _resolve_sources(source, tier)
        collect_results = []
        for src in sources_to_run:
            typer.echo(f"  Fetching: {src}...")
            result = _fetch_source(src, config, force=force)
            collect_results.append(result)
            status_icon = "✅" if result.status == "success" else "❌"
            msg = f"    {status_icon} {result.source_id}: {result.status}"
            if result.records_fetched:
                msg += f" — {result.records_fetched:,} records"
            if result.error_message:
                msg += f" — {result.error_message}"
            typer.echo(msg)

        collected_ids = [r.source_id for r in collect_results if r.status == "success"]
        if not collected_ids:
            typer.echo("\nNo data collected. Nothing to transform.")
            return
        typer.echo(f"\n  Collected {len(collected_ids)} sources.")
    else:
        # Use existing raw data
        collected_ids = list_sources(config.raw_dir)
        if source:
            collected_ids = [s for s in collected_ids if any(s.startswith(p) for p in source)]
        typer.echo(f"\n[1/5] Skipping collection. Using {len(collected_ids)} existing raw sources.")

    # ── Step 2: Transform & Align ──────────────────────────────
    typer.echo("\n[2/5] Transforming and aligning...")
    from data_pipeline.transforms.chain import run_all_transforms

    aligned = run_all_transforms(
        raw_dir=config.raw_dir,
        aligned_dir=config.aligned_dir,
        db_path=config.metadata_db,
        source_ids=collected_ids,
    )

    total_entities = sum(len(paths) for paths in aligned.values())
    for src_id, paths in aligned.items():
        typer.echo(f"  ✅ {src_id} → {len(paths)} entities: {[p.stem for p in paths]}")

    if not aligned:
        typer.echo("  No transforms produced output. Check ontology mappings.")
        return
    typer.echo(f"\n  Aligned {total_entities} entities from {len(aligned)} sources.")

    # ── Step 3: Quality Report ──────────────────────────────────
    typer.echo("\n[3/5] Generating quality report...")
    from data_pipeline.quality.report import generate_report

    report = generate_report(
        config,
        output_path=config.raw_dir.parent / "quality_report.md",
    )
    typer.echo(f"  ✅ Quality report written.")

    # ── Step 4: Export Calibration CSVs ──────────────────────────
    typer.echo("\n[4/5] Exporting calibration CSVs...")
    from data_pipeline.export.calibration_csv import export_all_calibration

    csv_paths = export_all_calibration(
        config.aligned_dir,
        config.raw_dir.parent / "calibration",
    )
    typer.echo(f"  ✅ Exported {len(csv_paths)} calibration CSVs.")

    # ── Step 5: Data Manifest ────────────────────────────────────
    typer.echo("\n[5/5] Generating data manifest...")
    from data_pipeline.export.manifest import generate_manifest

    manifest = generate_manifest(
        db_path=config.metadata_db,
        raw_dir=config.raw_dir,
        aligned_dir=config.aligned_dir,
        output_path=config.raw_dir.parent / "data_manifest.json",
    )
    typer.echo(f"  ✅ Manifest: {len(manifest.get('sources', {}))} sources, "
               f"{len(manifest.get('aligned_entities', []))} entities.")

    # ── Summary ──────────────────────────────────────────────────
    typer.echo("\n" + "=" * 60)
    typer.echo("Pipeline Complete")
    typer.echo(f"Finished: {datetime.now(timezone.utc).isoformat()}")
    typer.echo(f"Sources collected: {len(collected_ids)}")
    typer.echo(f"Entities aligned: {total_entities}")
    typer.echo(f"Calibration CSVs: {len(csv_paths)}")
    typer.echo("=" * 60)


@app.command()
def init_conditions(
    year: int = typer.Option(1900, "--year", "-y", help="Target year for initial conditions."),
):
    """Extract sector initial conditions from aligned data."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    typer.echo("=" * 60)
    typer.echo(f"Initial Conditions — Target Year: {year}")
    typer.echo("=" * 60)

    from data_pipeline.alignment.initial_conditions import (
        extract_initial_conditions,
        extract_sector_initial_conditions,
        report_initial_conditions,
    )

    # Extract and report
    report = report_initial_conditions(config.aligned_dir, year)
    typer.echo(report)

    # Show by-sector summary
    by_sector = extract_sector_initial_conditions(config.aligned_dir, year)
    typer.echo("\nBy Sector:")
    for sector, stocks in by_sector.items():
        typer.echo(f"  {sector}:")
        for stock, value in stocks.items():
            typer.echo(f"    {stock}: {value:.2f}")


@app.command()
def nrmsd(
    model_dir: Optional[Path] = typer.Option(
        None, "--model", "-m",
        help="Directory containing model output CSVs.",
    ),
    reference_dir: Optional[Path] = typer.Option(
        None, "--reference", "-r",
        help="Directory containing reference CSVs.",
    ),
):
    """Compute NRMSD between model output and reference data."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    if model_dir is None:
        model_dir = config.raw_dir.parent / "calibration"
    if reference_dir is None:
        reference_dir = config.raw_dir.parent / "reference"
    
    typer.echo("=" * 60)
    typer.echo("NRMSD Calibration Report")
    typer.echo("=" * 60)
    
    from data_pipeline.calibration.nrmsd import compare_calibrated_series
    import glob as glob_module
    
    model_files = sorted(glob_module.glob(str(model_dir / "*.csv")))
    ref_files = {
        Path(f).name: f for f in glob_module.glob(str(reference_dir / "*.csv"))
    }
    
    if not model_files:
        typer.echo("No model CSVs found.")
        return
    if not ref_files:
        typer.echo("No reference CSVs found.")
        return
    
    results = []
    for model_file in model_files:
        filename = Path(model_file).name
        if filename in ref_files:
            result = compare_calibrated_series(
                Path(model_file), Path(ref_files[filename])
            )
            results.append((filename, result))
    
    if not results:
        typer.echo("No overlapping files between model and reference.")
        return
    
    typer.echo(f"\n{'Variable':<40} {'NRMSD (direct)':>15} {'NRMSD (change)':>15} {'Years':>8}")
    typer.echo("-" * 80)
    for name, r in results:
        direct = f"{r['nrmsd_direct']:.4f}" if np.isfinite(r['nrmsd_direct']) else "N/A"
        change = f"{r['nrmsd_change_rate']:.4f}" if np.isfinite(r['nrmsd_change_rate']) else "N/A"
        years = str(r['overlap_years'])
        typer.echo(f"{name:<40} {direct:>15} {change:>15} {years:>8}")


@app.command()
def transform(
    source: list[str] = typer.Argument(..., help="Source(s) to transform."),
):
    """Run transform chain on specific raw sources."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    from data_pipeline.transforms.chain import run_transform_chain

    typer.echo(f"Transforming {len(source)} source(s)...")
    for src in source:
        typer.echo(f"  Transforming: {src}...")
        paths = run_transform_chain(
            src,
            raw_dir=config.raw_dir,
            aligned_dir=config.aligned_dir,
            db_path=config.metadata_db,
        )
        if paths:
            for p in paths:
                typer.echo(f"    ✅ → {p.name}")
        else:
            typer.echo(f"    ❌ No output (check mappings or data)")


@app.command()
def validate():
    """Run quality checks on aligned data."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    typer.echo("=" * 60)
    typer.echo("Data Quality Validation")
    typer.echo("=" * 60)

    from data_pipeline.quality.coverage import compute_coverage
    from data_pipeline.quality.freshness import compute_freshness
    from data_pipeline.quality.consistency import check_flow_consistency

    # Coverage check
    typer.echo("\n[1/3] Coverage Check")
    coverage_df = compute_coverage(config.raw_dir)
    if not coverage_df.empty:
        for _, row in coverage_df.iterrows():
            entity = row.get("source_id", "?")
            score = row.get("year_coverage_pct", 0) / 100 if "year_coverage_pct" in row else 0
            icon = "✅" if score > 0.8 else "⚠️" if score > 0.5 else "❌"
            typer.echo(f"  {icon} {entity}: {score:.1%}")

    # Freshness check
    typer.echo("\n[2/3] Freshness Check")
    freshness_df = compute_freshness(config.metadata_db)
    if not freshness_df.empty:
        for _, row in freshness_df.iterrows():
            source = row.get("source_id", "?")
            age_days = row.get("age_hours", 0) / 24 if "age_hours" in row else 0
            icon = "✅" if age_days < 365 else "⚠️" if age_days < 730 else "❌"
            typer.echo(f"  {icon} {source}: {age_days:.0f} days old")

    # Consistency check
    typer.echo("\n[3/3] Flow Consistency")
    # Compare GCP vs PRIMAP CO2
    import pandas as pd
    
    gcp_path = config.raw_dir / "gcp_fossil_co2.parquet"
    primap_path = config.raw_dir / "primap_hist.parquet"
    
    if gcp_path.exists() and primap_path.exists():
        gcp = pd.read_parquet(gcp_path)
        primap = pd.read_parquet(primap_path)
        
        # Get world data from GCP
        if "country" in gcp.columns:
            gcp_world = gcp[gcp["country"] == "World"].copy()
        else:
            gcp_world = gcp
        
        # Get EARTH data from PRIMAP (already aggregated in normalize)
        if "area_(iso3)" in primap.columns:
            primap_earth = primap[primap["area_(iso3)"] == "EARTH"].copy()
        else:
            primap_earth = primap
        
        if not gcp_world.empty and not primap_earth.empty and len(gcp_world) >= 3:
            # Simple correlation using numpy
            x = gcp_world["co2_mt"].values.astype(float)
            y = primap_earth.iloc[:, -1].values.astype(float)
            # Trim to common length
            min_len = min(len(x), len(y))
            x, y = x[:min_len], y[:min_len]
            # Pearson r
            r = np.corrcoef(x, y)[0, 1]
            typer.echo(f"  ✅ GCP vs PRIMAP CO₂: r={r:.4f} ({min_len} overlapping years)")
        else:
            typer.echo("  ⚠️ Insufficient overlapping data")
    else:
        typer.echo("  ⚠️ GCP or PRIMAP data not available")


@app.command()
def cross_check():
    """Compare overlapping sources for data consistency."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    typer.echo("=" * 60)
    typer.echo("Cross-Source Consistency Check")
    typer.echo("=" * 60)

    import pandas as pd
    from data_pipeline.calibration.nrmsd import nrmsd_direct

    def _load_aligned_entity(entity: str, source_id: str) -> pd.DataFrame | None:
        """Load aligned data filtered by source."""
        safe_name = entity.replace(".", "_")
        path = config.aligned_dir / f"{safe_name}.parquet"
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        if "source_id" in df.columns:
            return df[df["source_id"] == source_id].copy()
        return df

    # Define known overlapping entities
    overlaps = [
        ("emissions.co2_fossil", "gcp_fossil_co2", "primap_hist", "CO₂ fossil emissions"),
    ]

    for entity, source_a, source_b, label in overlaps:
        typer.echo(f"\n{label}:")

        df_a = _load_aligned_entity(entity, source_a)
        df_b = _load_aligned_entity(entity, source_b)

        if df_a is None or df_b is None or df_a.empty or df_b.empty:
            typer.echo(f"  ⚠️ One or both sources not available")
            continue

        # Merge on year
        merged = df_a.merge(df_b, on="year", suffixes=("_a", "_b"), how="inner")
        if len(merged) < 2:
            typer.echo(f"  ⚠️ Only {len(merged)} overlapping years")
            continue

        val_a = merged["value_a"].values
        val_b = merged["value_b"].values

        # Compute NRMSD
        nrmsd = nrmsd_direct(val_a, val_b)
        typer.echo(f"  Overlapping years: {len(merged)} ({merged['year'].min()}-{merged['year'].max()})")
        typer.echo(f"  NRMSD (direct): {nrmsd:.4f}")

        # Correlation using numpy
        if len(merged) >= 3:
            r = np.corrcoef(val_a, val_b)[0, 1]
            typer.echo(f"  Pearson r: {r:.4f}")

        # Mean absolute % difference
        mad_pct = np.mean(np.abs(val_a - val_b) / np.abs(val_a)) * 100
        typer.echo(f"  Mean absolute % difference: {mad_pct:.1f}%")

        icon = "✅" if nrmsd < 0.1 else "⚠️" if nrmsd < 0.3 else "❌"
        typer.echo(f"  Verdict: {icon} {'Good match' if nrmsd < 0.1 else 'Moderate' if nrmsd < 0.3 else 'Poor'} match")


@app.command()
def diff(
    source_a: str = typer.Argument(..., help="First source/entity."),
    source_b: str = typer.Argument(..., help="Second source/entity."),
):
    """Compare two aligned datasets."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    typer.echo("=" * 60)
    typer.echo(f"Data Diff: {source_a} vs {source_b}")
    typer.echo("=" * 60)

    import pandas as pd

    df_a = pd.read_parquet(config.aligned_dir / f"{source_a}.parquet")
    df_b = pd.read_parquet(config.aligned_dir / f"{source_b}.parquet")

    typer.echo(f"\nSource A ({source_a}):")
    typer.echo(f"  Shape: {df_a.shape}")
    typer.echo(f"  Year range: {df_a['year'].min()}-{df_a['year'].max()}")
    typer.echo(f"  Value range: {df_a['value'].min():.2f}-{df_a['value'].max():.2f}")

    typer.echo(f"\nSource B ({source_b}):")
    typer.echo(f"  Shape: {df_b.shape}")
    typer.echo(f"  Year range: {df_b['year'].min()}-{df_b['year'].max()}")
    typer.echo(f"  Value range: {df_b['value'].min():.2f}-{df_b['value'].max():.2f}")

    # Merge
    merged = df_a.merge(df_b, on="year", suffixes=("_a", "_b"), how="outer", indicator=True)
    typer.echo(f"\nOverlap:")
    typer.echo(f"  Common years: {len(merged[merged['_merge'] == 'both'])}")
    typer.echo(f"  Only in A: {len(merged[merged['_merge'] == 'left_only'])}")
    typer.echo(f"  Only in B: {len(merged[merged['_merge'] == 'right_only'])}")

    if len(merged[merged['_merge'] == 'both']) >= 2:
        overlap = merged[merged['_merge'] == 'both']
        from data_pipeline.calibration.nrmsd import nrmsd_direct
        nrmsd = nrmsd_direct(overlap['value_a'].values, overlap['value_b'].values)
        typer.echo(f"  NRMSD: {nrmsd:.4f}")


@app.command()
def fetch_owid():
    """Fetch all 6 OWID indicators for pyWorldX."""
    config = PipelineConfig()
    init_db(config.metadata_db)

    typer.echo("=" * 60)
    typer.echo("Fetching OWID Indicators")
    typer.echo("=" * 60)

    from data_pipeline.connectors.owid import KEY_SEARCHES, fetch_owid_search

    for key in KEY_SEARCHES:
        typer.echo(f"  Fetching: {key}...")
        result = fetch_owid_search(config, search_key=key)
        icon = "✅" if result.status == "success" else "❌"
        msg = f"    {icon} {result.source_id}: {result.status}"
        if result.records_fetched:
            msg += f" — {result.records_fetched:,} records"
        if result.error_message:
            msg += f" — {result.error_message}"
        typer.echo(msg)

    typer.echo("\nDone.")


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
    elif source_id == "un_population":
        from data_pipeline.connectors.un_population import fetch_all
        results = fetch_all(config)
        return results[0] if results else FetchResult(
            source_id="un_population", status="error",
            error_message="No indicators fetched",
        )
    elif source_id == "primap":
        from data_pipeline.connectors.primap import fetch_primap
        return fetch_primap(config, gas="CO2")
    elif source_id == "ceds_all":
        from data_pipeline.connectors.ceds import fetch_all
        results = fetch_all(config)
        success_count = sum(1 for r in results if r.status == "success")
        total_records = sum(r.records_fetched or 0 for r in results)
        return FetchResult(
            source_id="ceds_all", status="success" if success_count > 0 else "error",
            records_fetched=total_records,
            error_message=f"{success_count}/{len(results)} pollutants fetched" if success_count < len(results) else None,
        )
    elif source_id.startswith("ceds"):
        pollutant = source_id.replace("ceds_", "").upper() or "SO2"
        from data_pipeline.connectors.ceds import fetch_ceds_pollutant
        return fetch_ceds_pollutant(config, pollutant=pollutant)
    elif source_id == "usgs":
        from data_pipeline.connectors.usgs import fetch_usgs
        return fetch_usgs(config)
    elif source_id.startswith("nasa_earthdata"):
        dataset = source_id.replace("nasa_earthdata_", "") or "merra2"
        from data_pipeline.connectors.nasa_earthdata import fetch_nasa_earthdata
        return fetch_nasa_earthdata(config, dataset=dataset)
    elif source_id == "gapminder":
        from data_pipeline.connectors.gapminder import fetch_gapminder
        return fetch_gapminder(config)
    elif source_id == "owid_daily_caloric_supply":
        from data_pipeline.connectors.owid import fetch_owid_indicator
        return fetch_owid_indicator(config, indicator_key="daily_caloric_supply")
    elif source_id.startswith("owid"):
        key = source_id.replace("owid_", "") if source_id != "owid" else "primary_energy"
        from data_pipeline.connectors.owid import fetch_owid_search
        return fetch_owid_search(config, search_key=key)
    elif source_id == "nebel_2023":
        from data_pipeline.connectors.nebel_2023 import fetch_nebel_supplement
        return fetch_nebel_supplement(config)
    elif source_id == "fred":
        from data_pipeline.connectors.fred import fetch_all
        results = fetch_all(config)
        return results[0] if results else FetchResult(
            source_id="fred", status="error",
            error_message="No series fetched",
        )
    elif source_id == "eia":
        from data_pipeline.connectors.eia import fetch_all
        results = fetch_all(config)
        return results[0] if results else FetchResult(
            source_id="eia", status="error",
            error_message="No data fetched",
        )
    elif source_id == "edgar":
        from data_pipeline.connectors.edgar import fetch_edgar
        return fetch_edgar(config, gas="co2")
    elif source_id.startswith("edgar_"):
        gas = source_id.replace("edgar_", "")
        from data_pipeline.connectors.edgar import fetch_edgar
        return fetch_edgar(config, gas=gas)
    elif source_id == "ihme_gbd":
        from data_pipeline.connectors.ihme_gbd import fetch_ihme_gbd
        return fetch_ihme_gbd(config, indicator="dalys")
    elif source_id.startswith("ihme_gbd_"):
        indicator = source_id.replace("ihme_gbd_", "")
        from data_pipeline.connectors.ihme_gbd import fetch_ihme_gbd
        return fetch_ihme_gbd(config, indicator=indicator)
    elif source_id == "hmd":
        from data_pipeline.connectors.hmd import fetch_hmd
        return fetch_hmd(config, indicator="life_expectancy")
    elif source_id == "global_carbon_atlas":
        from data_pipeline.connectors.carbon_atlas import fetch_carbon_atlas
        return fetch_carbon_atlas(config)
    elif source_id.startswith("carbon_atlas"):
        from data_pipeline.connectors.carbon_atlas import fetch_carbon_atlas
        return fetch_carbon_atlas(config)
    elif source_id == "pwt":
        from data_pipeline.connectors.pwt import fetch_pwt
        return fetch_pwt(config)
    elif source_id == "ei_review":
        from data_pipeline.connectors.ei_review import fetch_ei_review
        return fetch_ei_review(config)
    elif source_id == "undp":
        from data_pipeline.connectors.undp import fetch_undp_hdr
        return fetch_undp_hdr(config)
    elif source_id == "nasa_giss":
        from data_pipeline.connectors.nasa_giss import fetch_nasa_giss
        return fetch_nasa_giss(config)
    elif source_id == "berkeley_earth":
        from data_pipeline.connectors.berkeley_earth import fetch_berkeley_earth
        return fetch_berkeley_earth(config)
    elif source_id == "climate_trace":
        from data_pipeline.connectors.climate_trace import fetch_climate_trace
        return fetch_climate_trace(config)
    elif source_id == "climate_watch":
        from data_pipeline.connectors.climate_watch import fetch_climate_watch
        return fetch_climate_watch(config)
    elif source_id == "carbon_atlas":
        from data_pipeline.connectors.carbon_atlas import fetch_carbon_atlas
        return fetch_carbon_atlas(config)
    elif source_id == "maddison":
        from data_pipeline.connectors.maddison import fetch_maddison
        return fetch_maddison(config)
    elif source_id == "hyde":
        from data_pipeline.connectors.hyde import fetch_hyde
        return fetch_hyde(config)
    elif source_id == "faostat":
        from data_pipeline.connectors.faostat import fetch_all
        results = fetch_all(config)
        return results[0] if results else FetchResult(
            source_id="faostat", status="error",
            error_message="No FAOSTAT data fetched",
        )
    elif source_id == "imf_weo":
        from data_pipeline.connectors.imf_weo import fetch_imf_weo
        return fetch_imf_weo(config)
    elif source_id == "oecd":
        from data_pipeline.connectors.oecd import fetch_oecd
        return fetch_oecd(config)
    elif source_id.startswith("comtrade"):
        code = source_id.replace("comtrade_", "") or "ALL"
        from data_pipeline.connectors.un_comtrade import fetch_comtrade
        return fetch_comtrade(config, commodity_code=code)
    elif source_id in ("unido", "footprint_network", "ihme_gbd", "hmd"):
        from data_pipeline.connectors import (
            unido, footprint_network, ihme_gbd, hmd,
        )
        dispatch = {
            "unido": unido.fetch_unido,
            "footprint_network": footprint_network.fetch_footprint_network,
            "ihme_gbd": ihme_gbd.fetch_ihme_gbd,
            "hmd": hmd.fetch_hmd,
        }
        return dispatch[source_id](config)
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
