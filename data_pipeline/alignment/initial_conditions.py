"""Initial conditions extractor — extract sector stock values from aligned data.

Takes aligned Parquet data at a target year and returns a dict of
{stock_name: value} for use as sector initial conditions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from data_pipeline.storage.parquet_store import read_aligned


# Mapping from ontology entity to sector stock name + default values
SECTOR_STOCK_MAP: dict[str, dict[str, Any]] = {
    "population.total": {
        "sector": "population",
        "stock_name": "POP",
        "unit": "persons",
        "default_value": 1.65e9,  # 1900 world population
        "scale_factor": 1.0,  # Already in persons
    },
    "emissions.co2_fossil": {
        "sector": "pollution",
        "stock_name": "PPOL",
        "unit": "kt_CO2",
        "default_value": 25000.0,  # 1900 estimate in kt
        "scale_factor": 1.0,
    },
    "emissions.land_use_co2": {
        "sector": "pollution",
        "stock_name": "PPOL_land_use",
        "unit": "Mt_CO2",
        "default_value": 1500.0,  # 1900 estimate
        "scale_factor": 1.0,
    },
    "atmospheric.co2": {
        "sector": "pollution",
        "stock_name": "PPOL_atmospheric",
        "unit": "ppm",
        "default_value": 295.0,  # 1900 CO2 ppm
        "scale_factor": 1.0,
    },
    "food.supply.kcal_per_capita": {
        "sector": "agriculture",
        "stock_name": "food_supply_per_capita",
        "unit": "kcal/capita/day",
        "default_value": 2400.0,  # 1900 estimate
        "scale_factor": 1.0,
    },
    "temperature.anomaly": {
        "sector": "pollution",
        "stock_name": "temp_anomaly",
        "unit": "degC",
        "default_value": 0.0,  # Baseline
        "scale_factor": 1.0,
    },
    # ── Industrial Capital (IC) ───────────────────────────────
    "industry.manufacturing_value_added": {
        "sector": "industry",
        "stock_name": "IC",
        "unit": "constant_2015_USD",
        "default_value": 2.0e11,  # 1900 estimate in 2015 USD
        "scale_factor": 1.0,
    },
    "industry.value_added": {
        "sector": "industry",
        "stock_name": "IC",
        "unit": "constant_2015_USD",
        "default_value": 2.0e11,  # 1900 estimate in 2015 USD
        "scale_factor": 1.0,
    },
    "capital.industrial_stock": {
        "sector": "industry",
        "stock_name": "IC",
        "unit": "constant_2015_USD",
        "default_value": 2.0e11,  # 1900 estimate
        "scale_factor": 1.0,
    },
    # ── Service Capital (SC) — proxy from GDP service sector ──
    "gdp.per_capita": {
        "sector": "service",
        "stock_name": "SC",
        "unit": "constant_2015_USD_per_capita",
        "default_value": 500.0,  # 1900 estimate
        "scale_factor": 1.0,
    },
    "gdp.maddison": {
        "sector": "service",
        "stock_name": "SC",
        "unit": "constant_1990_GK_dollar",
        "default_value": 500.0,  # 1900 estimate
        "scale_factor": 1.0,
    },
    "gdp.current_usd": {
        "sector": "service",
        "stock_name": "SC",
        "unit": "current_USD",
        "default_value": 1.0e12,  # 1900 estimate
        "scale_factor": 1.0,
    },
    # ── Non-Renewable Resources (NR) — proxy from cumulative extraction ──
    "resources.nonrenewable_stock": {
        "sector": "resources",
        "stock_name": "NR",
        "unit": "resource_units",
        "default_value": 1.0e12,  # 1900 estimate in resource units
        "scale_factor": 1.0,
    },
    # ── Arable Land (AL) — proxy from cropland data ──────────
    "land.arable_hectares": {
        "sector": "agriculture",
        "stock_name": "AL",
        "unit": "hectares",
        "default_value": 1.0e9,  # 1900 estimate ~1 billion hectares
        "scale_factor": 1.0,
    },
    "land.cropland_hectares": {
        "sector": "agriculture",
        "stock_name": "AL",
        "unit": "hectares",
        "default_value": 1.0e9,  # 1900 estimate
        "scale_factor": 1.0,
    },
}


def extract_initial_conditions(
    aligned_dir: Path,
    target_year: int = 1900,
    sector_stock_map: Optional[dict[str, dict]] = None,
) -> dict[str, dict[str, Any]]:
    """Extract sector stock initial conditions from aligned data.
    
    Reads aligned Parquet files for each mapped entity, finds the value
    closest to the target year, and returns a dict suitable for sector
    initialization.
    
    Args:
        aligned_dir: Path to the aligned Parquet store.
        target_year: Target year for initial conditions.
        sector_stock_map: Optional override for SECTOR_STOCK_MAP.
    
    Returns:
        Dict mapping entity name to:
            - sector: Sector name
            - stock_name: Stock variable name
            - value: Extracted or default value
            - unit: Unit string
            - source: Source of the value ("aligned" or "default")
            - year: Actual year the value was extracted from
    """
    if sector_stock_map is None:
        sector_stock_map = SECTOR_STOCK_MAP
    
    results = {}
    
    for entity, stock_info in sector_stock_map.items():
        # Read aligned data
        safe_name = entity.replace(".", "_")
        df = read_aligned(safe_name, aligned_dir)
        
        if df is None or df.empty or "year" not in df.columns:
            # Use default value
            results[entity] = {
                "sector": stock_info["sector"],
                "stock_name": stock_info["stock_name"],
                "value": stock_info["default_value"],
                "unit": stock_info["unit"],
                "source": "default",
                "year": target_year,
            }
            continue
        
        # Find closest year to target
        df = df.copy()
        df["year_diff"] = (df["year"] - target_year).abs()
        closest = df.loc[df["year_diff"].idxmin()]
        
        # Extract value
        value_col = "value" if "value" in df.columns else df.columns[-1]
        raw_value = closest.get(value_col, stock_info["default_value"])
        
        # Apply scale factor
        scaled_value = float(raw_value) * stock_info["scale_factor"]
        
        results[entity] = {
            "sector": stock_info["sector"],
            "stock_name": stock_info["stock_name"],
            "value": scaled_value,
            "unit": stock_info["unit"],
            "source": "aligned",
            "year": int(closest["year"]),
        }
    
    return results


def extract_sector_initial_conditions(
    aligned_dir: Path,
    target_year: int = 1900,
) -> dict[str, dict[str, float]]:
    """Extract initial conditions grouped by sector.
    
    Returns a dict mapping sector name to {stock_name: value}
    suitable for direct use in sector init_stocks().
    """
    raw = extract_initial_conditions(aligned_dir, target_year)
    
    by_sector: dict[str, dict[str, float]] = {}
    for entity, info in raw.items():
        sector = info["sector"]
        if sector not in by_sector:
            by_sector[sector] = {}
        by_sector[sector][info["stock_name"]] = info["value"]
    
    return by_sector


def report_initial_conditions(
    aligned_dir: Path,
    target_year: int = 1900,
) -> str:
    """Generate a human-readable report of initial conditions."""
    results = extract_initial_conditions(aligned_dir, target_year)
    
    lines = [
        f"# Initial Conditions Report — Target Year: {target_year}",
        f"# Generated from aligned data store",
        "",
    ]
    
    for entity, info in results.items():
        source_marker = "✅" if info["source"] == "aligned" else "⚠️"
        lines.append(
            f"{source_marker} {entity}"
        )
        lines.append(f"    Sector: {info['sector']}")
        lines.append(f"    Stock:  {info['stock_name']} = {info['value']:.2f} {info['unit']}")
        lines.append(f"    Source: {info['source']} (year {info['year']})")
        lines.append("")
    
    return "\n".join(lines)
