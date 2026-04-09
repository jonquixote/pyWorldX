"""Transform chain executor — runs raw data through the full transform sequence.

Takes a raw source ID, reads its Parquet file, applies transforms in order,
and writes aligned Parquet to the aligned store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from data_pipeline.alignment.map import EntityMapping, get_mappings
from data_pipeline.storage.metadata_db import init_db, record_transform
from data_pipeline.storage.parquet_store import read_raw, write_aligned


# Registry of available transform functions
TRANSFORM_REGISTRY: dict[str, Callable] = {}


def register_transform(name: str):
    """Decorator to register a transform function."""
    def decorator(func: Callable) -> Callable:
        TRANSFORM_REGISTRY[name] = func
        return func
    return decorator


# ── Transform Functions ────────────────────────────────────────────

@register_transform("interpolate_annual")
def transform_interpolate_annual(
    df: pd.DataFrame,
    mapping: EntityMapping,
    **kwargs: Any,
) -> pd.DataFrame:
    """Interpolate to annual frequency."""
    year_col = mapping.year_col or "year"
    value_col = mapping.value_col or "value"
    
    if year_col not in df.columns or value_col not in df.columns:
        return df
    
    method = kwargs.get("method", "linear")
    group_cols = []
    if mapping.country_col and mapping.country_col in df.columns:
        group_cols.append(mapping.country_col)
    
    # Simple interpolation per group
    result_frames = []
    if group_cols:
        for _, group in df.groupby(group_cols):
            group = group.sort_values(year_col).copy()
            min_year = int(group[year_col].min())
            max_year = int(group[year_col].max())
            annual_idx = pd.RangeIndex(min_year, max_year + 1, name=year_col)
            group = group.set_index(year_col).reindex(annual_idx)
            group[value_col] = group[value_col].interpolate(method=method)
            group = group.reset_index()
            result_frames.append(group)
    else:
        df = df.sort_values(year_col).copy()
        min_year = int(df[year_col].min())
        max_year = int(df[year_col].max())
        annual_idx = pd.RangeIndex(min_year, max_year + 1, name=year_col)
        df = df.set_index(year_col).reindex(annual_idx)
        df[value_col] = df[value_col].interpolate(method=method)
        df = df.reset_index()
        result_frames.append(df)
    
    return pd.concat(result_frames, ignore_index=True)


@register_transform("aggregate_world")
def transform_aggregate_world(
    df: pd.DataFrame,
    mapping: EntityMapping,
    **kwargs: Any,
) -> pd.DataFrame:
    """Filter to world aggregate or sum all countries."""
    country_col = mapping.country_col
    year_col = mapping.year_col or "year"
    value_col = mapping.value_col or "value"
    
    if mapping.country_filter == "world":
        world_code = kwargs.get("world_value", mapping.world_country_code)
        world_name = kwargs.get("world_name", mapping.world_area_name)
        
        if country_col and country_col in df.columns and world_code:
            # Check if world aggregate row exists
            world_mask = df[country_col] == world_code
            if world_mask.any():
                return df[world_mask].copy()
            
            # No world row — sum all countries by year
            if year_col in df.columns and value_col in df.columns:
                world_total = df.groupby(year_col, as_index=False)[value_col].sum()
                # Add country column
                world_total[country_col] = world_name
                # Keep other non-grouped columns from first row
                for col in df.columns:
                    if col not in world_total.columns and col not in [year_col, country_col]:
                        world_total[col] = df[col].iloc[0] if len(df) > 0 else None
                # Reorder columns to match original
                col_order = [c for c in df.columns if c in world_total.columns]
                world_total = world_total[col_order]
                return world_total
    
    return df


@register_transform("unit_conversion")
def transform_unit_conversion(
    df: pd.DataFrame,
    mapping: EntityMapping,
    **kwargs: Any,
) -> pd.DataFrame:
    """Convert units by a factor."""
    value_col = mapping.value_col or "value"
    
    if value_col not in df.columns:
        return df
    
    factor = kwargs.get("factor", 1.0)
    if factor != 1.0:
        df = df.copy()
        df[value_col] = df[value_col] * factor
    
    return df


@register_transform("filter_rows")
def transform_filter_rows(
    df: pd.DataFrame,
    mapping: EntityMapping,
    **kwargs: Any,
) -> pd.DataFrame:
    """Filter rows by column value."""
    column = kwargs.get("column")
    value = kwargs.get("value")
    
    if column and column in df.columns and value is not None:
        return df[df[column] == value].copy()
    
    return df


@register_transform("imf_weo_parse")
def transform_imf_weo_parse(
    df: pd.DataFrame,
    mapping: EntityMapping,
    **kwargs: Any,
) -> pd.DataFrame:
    """Parse IMF WEO Excel sheets (placeholder — complex structure)."""
    # IMF WEO data is in raw Excel format with header rows
    # For now, return as-is — full parsing needs domain knowledge
    return df


@register_transform("nebel_2023_parse")
def transform_nebel_2023_parse(
    df: pd.DataFrame,
    mapping: EntityMapping,
    **kwargs: Any,
) -> pd.DataFrame:
    """Parse Nebel 2023 supplementary document (placeholder)."""
    # This is a metadata row — return as-is for now
    return df


@register_transform("derive_per_capita")
def transform_derive_per_capita(
    df: pd.DataFrame,
    mapping: EntityMapping,
    raw_dir: Optional[Path] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Derive per-capita values by dividing value by population.

    Reads the World Bank population total series and divides the
    incoming value column by population, emitting a per-capita column.

    Args:
        df: DataFrame with value column to convert.
        mapping: Entity mapping (provides year_col, value_col).
        raw_dir: Path to raw Parquet store (for reading population data).
        kwargs: Optional population_source_id (default "world_bank_SP.POP.TOTL").

    Returns:
        DataFrame with value column replaced by per-capita values.
    """
    year_col = mapping.year_col or "year"
    value_col = mapping.value_col or "value"

    if year_col not in df.columns or value_col not in df.columns:
        return df

    # Get population data
    pop_source = kwargs.get("population_source_id", "world_bank_SP.POP.TOTL")
    if raw_dir is None:
        return df  # Can't derive without raw_dir

    from data_pipeline.storage.parquet_store import read_raw
    pop_df = read_raw(pop_source, raw_dir)

    if pop_df is None or pop_df.empty:
        return df  # Can't derive without population data

    # Normalize population columns
    pop_year_col = "date" if "date" in pop_df.columns else "year"
    pop_value_col = "value"

    if pop_year_col not in pop_df.columns or pop_value_col not in pop_df.columns:
        return df

    # Aggregate population to world level
    if "country_code" in pop_df.columns:
        pop_df = pop_df.groupby(pop_year_col, as_index=False)[pop_value_col].sum()
        pop_df.rename(columns={pop_value_col: "population"}, inplace=True)

    # Ensure both have numeric year columns
    df = df.copy()
    df[year_col] = pd.to_numeric(df[year_col], errors="coerce")
    pop_df[pop_year_col] = pd.to_numeric(pop_df[pop_year_col], errors="coerce")

    # Merge on year
    merged = df.merge(
        pop_df[[pop_year_col, "population"]],
        left_on=year_col,
        right_on=pop_year_col,
        how="left",
    )

    # Derive per-capita: value / population
    # Guard against zero/NaN population
    valid = merged["population"].notna() & (merged["population"] > 0)
    merged.loc[valid, value_col] = merged.loc[valid, value_col] / merged.loc[valid, "population"]

    # Drop population columns, keep original structure
    merged.drop(columns=["population", pop_year_col], inplace=True, errors="ignore")

    return merged


# ── Transform Chain Executor ───────────────────────────────────────

def run_transform_chain(
    source_id: str,
    raw_dir: Path,
    aligned_dir: Path,
    db_path: Path,
) -> list[Path]:
    """Run a raw source through its transform chain.
    
    Reads raw Parquet from raw_dir, applies transforms for each
    entity mapping, and writes aligned Parquet to aligned_dir.
    
    Args:
        source_id: Source identifier (e.g. "world_bank_SP.POP.TOTL").
        raw_dir: Path to raw Parquet store.
        aligned_dir: Path to aligned Parquet store.
        db_path: Path to SQLite metadata database.
    
    Returns:
        List of paths to written aligned Parquet files.
    """
    import time
    from datetime import datetime, timezone
    
    # Get ontology mappings for this source
    mappings = get_mappings(source_id)
    if not mappings:
        return []
    
    # Read raw data
    df = read_raw(source_id, raw_dir)
    if df is None or df.empty:
        return []

    # Normalize raw connector output to standard format
    from data_pipeline.transforms.normalize import normalize_source
    df = normalize_source(df, source_id)

    # Check if at least one mapping has columns present in the data
    has_valid_mapping = False
    for mapping in mappings:
        yc = mapping.year_col or "year"
        vc = mapping.value_col or "value"
        if yc in df.columns and vc in df.columns:
            has_valid_mapping = True
            break

    if not has_valid_mapping or df.empty:
        return []

    init_db(db_path)
    written_paths = []
    
    for mapping in mappings:
        entity = mapping.entity
        transform_names = [t.name for t in mapping.transforms]
        transform_kwargs = [{**t.kwargs} for t in mapping.transforms]
        
        t0 = time.time()
        
        # Apply transforms in order
        result_df = df.copy()
        for i, (t_name, t_kwargs) in enumerate(zip(transform_names, transform_kwargs)):
            transform_fn = TRANSFORM_REGISTRY.get(t_name)
            if transform_fn is None:
                continue
            try:
                # Inject raw_dir for transforms that need it
                if "raw_dir" in t_kwargs or transform_fn.__code__.co_varnames[3:4] == ("raw_dir",):
                    t_kwargs["raw_dir"] = raw_dir
                result_df = transform_fn(result_df, mapping, **t_kwargs)
            except Exception as e:
                # Record failure and skip this entity
                time.time() - t0
                record_transform(
                    db_path,
                    transform_name=f"{t_name}:{entity}",
                    status="error",
                    input_sources=source_id,
                    output_entities=entity,
                    error_message=str(e),
                )
                break
        else:
            # All transforms succeeded — write aligned data
            if result_df is not None and not result_df.empty:
                # Standardize aligned columns
                aligned_df = _standardize_aligned(result_df, mapping, source_id)
                
                # Write to aligned store
                if aligned_df is not None and not aligned_df.empty:
                    safe_name = entity.replace(".", "_")
                    path = write_aligned(aligned_df, safe_name, aligned_dir)
                    written_paths.append(path)
                    
                    # Record success
                    time.time() - t0
                    record_transform(
                        db_path,
                        transform_name=f"chain:{source_id}",
                        status="success",
                        input_sources=source_id,
                        output_entities=entity,
                        records_written=len(aligned_df),
                        started_at=datetime.now(timezone.utc).isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
    
    return written_paths


def run_all_transforms(
    raw_dir: Path,
    aligned_dir: Path,
    db_path: Path,
    source_ids: list[str] | None = None,
) -> dict[str, list[Path]]:
    """Run transform chains for all (or specified) raw sources.
    
    Args:
        raw_dir: Path to raw Parquet store.
        aligned_dir: Path to aligned Parquet store.
        db_path: Path to SQLite metadata database.
        source_ids: Optional list of source IDs to process. 
            If None, processes all sources in raw store.
    
    Returns:
        Dict mapping source_id → list of written aligned Parquet paths.
    """
    from data_pipeline.storage.parquet_store import list_sources
    
    if source_ids is None:
        source_ids = list_sources(raw_dir)
    
    results = {}
    for source_id in source_ids:
        paths = run_transform_chain(source_id, raw_dir, aligned_dir, db_path)
        if paths:
            results[source_id] = paths
    
    return results


def _standardize_aligned(
    df: pd.DataFrame,
    mapping: EntityMapping,
    source_id: str,
) -> pd.DataFrame:
    """Standardize aligned DataFrame columns."""
    value_col = mapping.value_col or "value"
    year_col = mapping.year_col or "year"
    
    # Check required columns exist
    if year_col and year_col not in df.columns:
        return pd.DataFrame()  # Skip this entity
    if value_col and value_col not in df.columns:
        return pd.DataFrame()  # Skip this entity
    
    aligned = pd.DataFrame()
    
    # Entity name
    aligned["entity"] = mapping.entity
    
    # Year column
    if year_col and year_col in df.columns:
        aligned["year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    else:
        aligned["year"] = pd.NA
    
    # Value column
    if value_col and value_col in df.columns:
        aligned["value"] = pd.to_numeric(df[value_col], errors="coerce")
    else:
        aligned["value"] = pd.NA
    
    # Unit
    if mapping.unit:
        aligned["unit"] = mapping.unit
    elif mapping.unit_col and mapping.unit_col in df.columns:
        aligned["unit"] = df[mapping.unit_col]
    
    # Source tracking
    aligned["source_id"] = source_id
    
    # Quality flag
    aligned["quality_flag"] = mapping.quality_flag
    
    # Country if applicable
    if mapping.country_col and mapping.country_col in df.columns:
        aligned["country_code"] = df[mapping.country_col]
    
    # Drop rows with missing year or value
    if "year" in aligned.columns and "value" in aligned.columns:
        aligned = aligned.dropna(subset=["year", "value"])
    
    return aligned
