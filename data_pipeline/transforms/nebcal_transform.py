"""Nebel 2023 calibration series reconstruction.

Transform step 9 of the pipeline. Reconstructs the GDP-deflated
industrial output, food, services, and pollution proxy series used
in Nebel et al. (2023) to derive the Section 13.1 NRMSD bounds.

Runtime dependency: Requires World Bank GDP deflator in the raw store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from data_pipeline.storage.parquet_store import read_raw
from data_pipeline.transforms.deflation import deflate_world_bank_values


def reconstruct_industrial_output(
    raw_dir: Path,
    world_bank_gdp: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Reconstruct GDP-deflated industrial output series.

    Uses World Bank GDP data as a proxy for industrial output,
    deflated to constant 2017 USD.

    Args:
        raw_dir: Path to the raw Parquet store.
        world_bank_gdp: Optional pre-loaded GDP DataFrame.

    Returns:
        DataFrame with columns: year, country_code, industrial_output_real.
    """
    if world_bank_gdp is None:
        world_bank_gdp = read_raw(
            "world_bank_NY.GDP.MKTP.CD",
            raw_dir=raw_dir,
        )
        if world_bank_gdp is None:
            raise FileNotFoundError(
                "World Bank GDP not found in raw store."
            )

    # Deflate to constant prices
    df = deflate_world_bank_values(
        df=world_bank_gdp,
        raw_dir=raw_dir,
        value_col="value",
        year_col="date",
        country_col="countryiso3code",
        base_year=2017,
    )

    df = df.rename(columns={
        "date": "year",
        "countryiso3code": "country_code",
        "value_real": "industrial_output_real",
    })

    df["source_id"] = "nebel_2023_reconstructed"
    df["entity"] = "industrial_output"

    return df[["year", "country_code", "industrial_output_real", "source_id", "entity"]]


def reconstruct_food_production(
    raw_dir: Path,
    faostat_fbs: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Reconstruct food production series from FAO Food Balance Sheets.

    Args:
        raw_dir: Path to the raw Parquet store.
        faostat_fbs: Optional pre-loaded FAO FBS DataFrame.

    Returns:
        DataFrame with columns: year, country_code, food_production.
    """
    # This is a placeholder — actual implementation depends on
    # the structure of the FAO FBS data.
    raise NotImplementedError(
        "Food production reconstruction requires FAO FBS data. "
        "Implement once FAOSTAT connector is available."
    )


def reconstruct_pollution_proxy(
    raw_dir: Path,
    co2_sources: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Reconstruct pollution proxy from CO2 emissions data.

    Combines GCP, EDGAR, and CEDS data to create a persistent
    pollution index aligned with World3-03.

    Args:
        raw_dir: Path to the raw Parquet store.
        co2_sources: List of CO2 source IDs to blend.

    Returns:
        DataFrame with columns: year, country_code, pollution_index.
    """
    # Priority: GCP (1750-2023) → EDGAR (1970+) → CEDS (1750+ for non-CO2)
    sources = co2_sources or ["gcp_fossil_co2"]

    frames = []
    for source_id in sources:
        df = read_raw(source_id, raw_dir=raw_dir)
        if df is not None:
            df["source_id"] = source_id
            frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"No CO2 data found in raw store. Sources tried: {sources}"
        )

    combined = pd.concat(frames, ignore_index=True)

    # Normalize to pollution index (base year = CrossValidationConfig.train_start = 1.0)
    from pyworldx.calibration.metrics import CrossValidationConfig
    _base_year = CrossValidationConfig.train_start
    world_total = combined.groupby("year")["co2_mt"].sum().reset_index()
    world_base = world_total.loc[world_total["year"] == _base_year, "co2_mt"]

    if len(world_base) > 0 and world_base.iloc[0] > 0:
        world_total["pollution_index"] = world_total["co2_mt"] / world_base.iloc[0]
    else:
        world_total["pollution_index"] = world_total["co2_mt"] / world_total["co2_mt"].iloc[0]

    world_total["source_id"] = "nebel_2023_reconstructed"
    world_total["entity"] = "pollution_index"
    world_total["country_code"] = "WLD"

    return world_total[["year", "country_code", "pollution_index", "source_id", "entity"]]


def reconstruct_service_output(
    raw_dir: Path,
) -> pd.DataFrame:
    """Reconstruct service output series.

    Uses the residual of GDP minus industrial output as a proxy
    for service output, deflated to constant prices.

    Args:
        raw_dir: Path to the raw Parquet store.

    Returns:
        DataFrame with columns: year, country_code, service_output_real.
    """
    raise NotImplementedError(
        "Service output reconstruction requires GDP + industrial output "
        "data. Implement once all sources are available."
    )
