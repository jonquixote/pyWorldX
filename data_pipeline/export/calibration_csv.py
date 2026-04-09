"""Calibration CSV export — NRMSD-ready CSVs aligned to spec targets.

Generates one CSV per spec §13.1 calibration variable, formatted
for direct consumption by pyWorldX's nrmsd_direct metric.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd


def export_calibration_csv(
    df: pd.DataFrame,
    entity: str,
    output_path: Path,
    unit: str = "",
    sources: Optional[str] = None,
    proxy_method: Optional[str] = None,
    year_col: str = "year",
    value_col: str = "value",
) -> Path:
    """Export a DataFrame as an NRMSD calibration CSV.

    Args:
        df: DataFrame with aligned, clean data.
        entity: pyWorldX ontology entity name.
        output_path: Path to write the CSV.
        unit: Canonical unit string.
        sources: Comma-separated list of source IDs used.
        proxy_method: Description of proxy method if derived.
        year_col: Year column name.
        value_col: Value column name.

    Returns:
        Path to the written CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Skip empty DataFrames
    if df.empty:
        return output_path

    # Select columns that actually exist
    export_cols = []
    for col in [year_col, value_col]:
        if col in df.columns:
            export_cols.append(col)
    
    if not export_cols:
        return output_path
    
    if "country_code" in df.columns:
        export_cols.append("country_code")
    if "quality_flag" in df.columns:
        export_cols.append("quality_flag")

    export_df = df[export_cols].copy()
    # Convert year to regular int for sorting (handle nullable Int64)
    if year_col in export_df.columns and export_df[year_col].dtype.name == "Int64":
        export_df[year_col] = export_df[year_col].astype(float)
    
    export_df = export_df.dropna(subset=[year_col, value_col])
    if export_df.empty:
        return output_path
    export_df = export_df.sort_values([year_col]).reset_index(drop=True)

    # Write with header comment
    header_lines = [
        f"# pyWorldX NRMSD Calibration Series",
        f"# Entity: {entity}",
        f"# Unit: {unit}",
        f"# Sources: {sources or 'unknown'}",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}",
    ]
    if proxy_method:
        header_lines.append(f"# Proxy method: {proxy_method}")

    header_text = "\n".join(header_lines) + "\n"

    with open(output_path, "w") as f:
        f.write(header_text)

    export_df.to_csv(output_path, mode="a", index=False)

    return output_path


def export_all_calibration(
    aligned_dir: Path,
    output_dir: Path,
    entity_map: Optional[dict[str, dict]] = None,
) -> list[Path]:
    """Export all aligned entities as calibration CSVs.

    Args:
        aligned_dir: Path to the aligned Parquet store.
        output_dir: Path to write calibration CSVs.
        entity_map: Optional dict mapping entity names to metadata
            (unit, sources, proxy_method).

    Returns:
        List of written CSV paths.
    """
    import glob as glob_module

    paths = []
    for parquet_file_path in sorted(glob_module.glob(str(aligned_dir / "*.parquet"))):
        parquet_file = Path(parquet_file_path)
        df = pd.read_parquet(parquet_file)
        entity = parquet_file.stem.replace("_", ".")

        meta = entity_map.get(entity, {}) if entity_map else {}

        output_path = output_dir / f"{entity}.csv"
        path = export_calibration_csv(
            df=df,
            entity=entity,
            output_path=output_path,
            unit=meta.get("unit", ""),
            sources=meta.get("sources"),
            proxy_method=meta.get("proxy_method"),
        )
        paths.append(path)

    return paths
