"""pyWorldX Data Pipeline — Parquet storage layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import duckdb


def write_raw(
    df: pd.DataFrame,
    source_id: str,
    raw_dir: Path,
) -> Path:
    """Write a DataFrame to the raw Parquet store.

    Args:
        df: DataFrame with at least the raw store columns.
        source_id: Source identifier (used in filename).
        raw_dir: Directory for raw Parquet files.

    Returns:
        Path to the written Parquet file.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{source_id}.parquet"
    df.to_parquet(path, index=False, engine="pyarrow")
    return path


def read_raw(source_id: str, raw_dir: Path) -> pd.DataFrame | None:
    """Read a DataFrame from the raw Parquet store.

    Returns None if the file doesn't exist.
    """
    path = raw_dir / f"{source_id}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def write_aligned(
    df: pd.DataFrame,
    entity: str,
    aligned_dir: Path,
) -> Path:
    """Write a DataFrame to the aligned Parquet store.

    If the entity file already exists, merges with existing data
    (deduplicating on source_id + year).

    Args:
        df: DataFrame with aligned store columns.
        entity: pyWorldX ontology entity name.
        aligned_dir: Directory for aligned Parquet files.

    Returns:
        Path to the written Parquet file.
    """
    aligned_dir.mkdir(parents=True, exist_ok=True)
    # Sanitize entity name for filename
    safe_name = entity.replace(".", "_")
    path = aligned_dir / f"{safe_name}.parquet"

    # Merge with existing data if file exists
    if path.exists():
        try:
            existing = pd.read_parquet(path)
            combined = pd.concat([existing, df], ignore_index=True)
            # Deduplicate on source_id + year (keep latest by source_id)
            if "source_id" in combined.columns and "year" in combined.columns:
                combined = combined.drop_duplicates(
                    subset=["source_id", "year"],
                    keep="last",
                )
            df = combined
        except Exception:
            pass  # If merge fails, just overwrite

    df.to_parquet(path, index=False, engine="pyarrow")
    return path


def read_aligned(entity: str, aligned_dir: Path) -> pd.DataFrame | None:
    """Read a DataFrame from the aligned Parquet store.

    Returns None if the file doesn't exist.
    """
    safe_name = entity.replace(".", "_")
    path = aligned_dir / f"{safe_name}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def list_sources(raw_dir: Path) -> list[str]:
    """List all source IDs in the raw store."""
    if not raw_dir.exists():
        return []
    return [p.stem for p in raw_dir.glob("*.parquet")]


def list_entities(aligned_dir: Path) -> list[str]:
    """List all entity names in the aligned store."""
    if not aligned_dir.exists():
        return []
    return [p.stem.replace("_", ".") for p in aligned_dir.glob("*.parquet")]


def query_across_sources(
    query: str,
    raw_dir: Path,
    aligned_dir: Path,
) -> pd.DataFrame:
    """Run a DuckDB SQL query across raw and aligned stores.

    Args:
        query: SQL query referencing raw_* and aligned_* tables.
        raw_dir: Directory for raw Parquet files.
        aligned_dir: Directory for aligned Parquet files.

    Returns:
        Query result as DataFrame.
    """
    con = duckdb.connect()
    # Register all Parquet files as tables
    if raw_dir.exists():
        for p in raw_dir.glob("*.parquet"):
            table_name = f"raw_{p.stem}"
            con.register(table_name, con.read_parquet(str(p)))
    if aligned_dir.exists():
        for p in aligned_dir.glob("*.parquet"):
            table_name = f"aligned_{p.stem}"
            con.register(table_name, con.read_parquet(str(p)))
    result = con.execute(query).fetchdf()
    con.close()
    return result
