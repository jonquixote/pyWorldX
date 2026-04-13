"""ConnectorResult export — generates pyworldx.data ConnectorResult objects.

Generates `ConnectorResult` objects (spec §8.1) from aligned pipeline data,
ready to wire into pyWorldX's data connector infrastructure.

Includes a unit bridge that converts pipeline real-world units (e.g., Mt_CO2,
persons) to World3 abstract units (e.g., pollution_units, capital_units).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from data_pipeline.storage.parquet_store import read_aligned


# ── Unit Bridge ───────────────────────────────────────────────────

# Maps pipeline units to World3 abstract unit families and scale factors.
# Each entry: pipeline_unit -> (world3_unit_family, scale_factor)
UNIT_BRIDGE: dict[str, tuple[str, float]] = {
    # Population
    "persons": ("people", 1.0),
    "millions_persons": ("people", 1e6),
    "billions_persons": ("people", 1e9),

    # Emissions / Pollution
    "Mt_CO2": ("pollution_units", 1.0),
    "kt_CO2": ("pollution_units", 0.001),
    "Mt_CO2e": ("pollution_units", 1.0),
    "kt": ("pollution_units", 0.001),
    "ppm": ("pollution_units", 1.0),  # CO2 concentration as pollution proxy
    "degC_anomaly": ("pollution_units", 1.0),  # Temp anomaly as pollution proxy
    "degC": ("pollution_units", 1.0),

    # Economic / Capital
    "constant_2015_USD": ("capital_units", 1.0),
    "constant_2017_USD": ("capital_units", 1.0),
    "constant_1990_GK_dollar": ("capital_units", 1.0),
    "current_USD": ("capital_units", 1.0),
    "constant_2015_USD_per_capita": ("capital_units", 1.0),
    "index_2015_100": ("capital_units", 1.0),

    # Resources
    "resource_units": ("resource_units", 1.0),
    "tonnes": ("resource_units", 1.0),
    "kt_mineral": ("resource_units", 0.001),

    # Land / Agriculture
    "hectares": ("hectares", 1.0),
    "km2": ("hectares", 100.0),
    "kcal_per_capita_per_day": ("food_units", 1.0),
    "kcal/capita/day": ("food_units", 1.0),

    # Energy
    "EJ": ("energy_units", 1.0),
    "Btu_various": ("energy_units", 1.0),
    "TWh": ("energy_units", 3.6),  # 1 TWh = 3.6 EJ

    # Ecological Footprint
    "global_hectares": ("hectares", 1.0),
    "gha_per_capita": ("hectares", 1.0),

    # Health
    "dalys_per_100k": ("health_index", 1.0),
    "deaths_per_1000": ("health_index", 1.0),
    "years": ("health_index", 1.0),

    # GDP / Economic indicators
    "index": ("capital_units", 1.0),
    "percent": ("capital_units", 0.01),

    # Fallback
    "unknown": ("dimensionless", 1.0),
}


def convert_pipeline_unit_to_world3(pipeline_unit: str) -> tuple[str, float]:
    """Convert a pipeline unit to a World3 abstract unit.

    Args:
        pipeline_unit: Unit string from the pipeline (e.g., "Mt_CO2").

    Returns:
        Tuple of (world3_unit, scale_factor).
    """
    if pipeline_unit in UNIT_BRIDGE:
        return UNIT_BRIDGE[pipeline_unit]

    # Try partial match
    for p_unit, (w3_unit, factor) in UNIT_BRIDGE.items():
        if p_unit.lower() in pipeline_unit.lower() or pipeline_unit.lower() in p_unit.lower():
            return (w3_unit, factor)

    # Default fallback
    return ("dimensionless", 1.0)


def convert_series_to_world3_units(
    series: pd.Series,
    pipeline_unit: str,
) -> tuple[pd.Series, str]:
    """Convert a pandas Series from pipeline to World3 units.

    Args:
        series: The data series to convert.
        pipeline_unit: Original pipeline unit string.

    Returns:
        Tuple of (converted_series, world3_unit_string).
    """
    world3_unit, scale_factor = convert_pipeline_unit_to_world3(pipeline_unit)
    converted = series * scale_factor
    return converted, world3_unit


# ── PipelineConnectorResult ───────────────────────────────────────

@dataclass
class PipelineConnectorResult:
    """Lightweight ConnectorResult compatible with pyWorldX.

    Mirrors the pyworldx.data.connectors.base.ConnectorResult dataclass
    so the pipeline can produce compatible results without importing
    the main pyWorldX package.
    """
    series: "pd.Series[Any]"
    unit: str
    source: str
    source_series_id: str
    retrieved_at: str
    vintage: str | None = None
    proxy_method: str | None = None
    transform_log: list[str] = field(default_factory=list)


def generate_connector_result(
    entity: str,
    aligned_dir: Path,
    country: str = "WLD",
    start_year: int = 1900,
    end_year: int = 2020,
    proxy_method: Optional[str] = None,
    transform_log: Optional[list[str]] = None,
    convert_units: bool = True,
) -> Optional[PipelineConnectorResult]:
    """Generate a PipelineConnectorResult for a pyWorldX ontology entity.

    Reads aligned Parquet data, filters by country and year range,
    and returns a PipelineConnectorResult with proper World3 units.

    Args:
        entity: pyWorldX ontology entity name (e.g. "population.total").
        aligned_dir: Path to the aligned Parquet store.
        country: Country code to extract (default "WLD" for world).
        start_year: First year to include.
        end_year: Last year to include.
        proxy_method: Description of proxy method if derived (spec §8.1).
        transform_log: List of transforms applied.
        convert_units: If True, convert pipeline units to World3 abstract units.

    Returns:
        PipelineConnectorResult or None if entity not found.
    """
    # Read aligned data
    df = read_aligned(entity, aligned_dir=aligned_dir)
    if df is None:
        return None

    # Filter by country
    if "country_code" in df.columns:
        df = df[df["country_code"] == country]  # type: ignore[assignment]

    # Filter by year
    year_col = "year" if "year" in df.columns else "date"
    if year_col in df.columns:
        df = df[df[year_col].between(start_year, end_year)]  # type: ignore[assignment]

    if df.empty:
        return None

    # Build series
    if "value" in df.columns:
        value_col = "value"
    elif "value_per_capita" in df.columns:
        value_col = "value_per_capita"
    else:
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) == 0:
            return None
        value_col = str(numeric_cols[0])

    series = df.set_index(year_col)[value_col].sort_index()
    series.index.name = None

    # Determine unit
    pipeline_unit = "unknown"
    if "unit" in df.columns:
        unit_vals = df["unit"].dropna()
        if len(unit_vals) > 0:
            pipeline_unit = str(unit_vals.iloc[0])

    # Convert to World3 units if requested
    if convert_units:
        series, world3_unit = convert_series_to_world3_units(series, pipeline_unit)
    else:
        world3_unit = pipeline_unit

    # Build transform log
    log = transform_log or ["pipeline_aligned"]
    if convert_units and world3_unit != pipeline_unit:
        log.append(f"unit_bridge:{pipeline_unit}_to_{world3_unit}")

    return PipelineConnectorResult(
        series=series,
        unit=world3_unit,
        source=f"pyworldx_data_pipeline_{entity}",
        source_series_id=f"pyworldx_{entity}_{country}_{start_year}_{end_year}",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        vintage="2024",
        proxy_method=proxy_method,
        transform_log=log,
    )


def generate_all_connector_results(
    aligned_dir: Path,
    country: str = "WLD",
    start_year: int = 1900,
    end_year: int = 2020,
    convert_units: bool = True,
) -> dict[str, PipelineConnectorResult]:
    """Generate PipelineConnectorResult for all aligned entities.

    Args:
        aligned_dir: Path to the aligned Parquet store.
        country: Country code to extract.
        start_year: First year to include.
        end_year: Last year to include.
        convert_units: If True, convert to World3 abstract units.

    Returns:
        Dict mapping entity name to PipelineConnectorResult.
    """
    results: dict[str, PipelineConnectorResult] = {}
    for parquet_file in sorted(aligned_dir.glob("*.parquet")):
        entity = parquet_file.stem.replace("_", ".")
        result = generate_connector_result(
            entity=entity,
            aligned_dir=aligned_dir,
            country=country,
            start_year=start_year,
            end_year=end_year,
            convert_units=convert_units,
        )
        if result is not None:
            results[entity] = result

    return results
