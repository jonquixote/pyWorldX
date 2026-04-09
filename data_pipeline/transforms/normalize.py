"""Connector normalization layer — transforms raw connector output into standard format.

Each connector produces raw data in its own format. This layer provides
normalization functions that convert each format to a standard DataFrame
with columns: [year, value, country_code (optional), unit (optional), source_id].

The normalized data can then be processed by the transform chain.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd


# Registry of normalizer functions by source_id prefix
NORMALIZER_REGISTRY: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {}


def register_normalizer(prefix: str):
    """Decorator to register a normalizer function for a source_id prefix."""
    def decorator(func: Callable[[pd.DataFrame], pd.DataFrame]) -> Callable:
        NORMALIZER_REGISTRY[prefix] = func
        return func
    return decorator


def normalize_source(df: pd.DataFrame, source_id: str) -> pd.DataFrame:
    """Normalize raw data from a connector to standard format.
    
    Args:
        df: Raw DataFrame from connector.
        source_id: Source identifier (e.g. "world_bank_SP.POP.TOTL").
    
    Returns:
        Normalized DataFrame with standard columns:
        [year, value, country_code (optional), unit (optional), source_id]
    """
    # Find matching normalizer by prefix
    for prefix, normalizer in NORMALIZER_REGISTRY.items():
        if source_id.startswith(prefix):
            return normalizer(df)
    
    # No normalizer found — return as-is with warning columns
    return df


# ── World Bank Normalizer ──────────────────────────────────────────────

@register_normalizer("world_bank_")
def normalize_world_bank(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize World Bank API output.
    
    Raw format has dict columns for indicator/country, and nested values.
    """
    result = pd.DataFrame()
    
    # Extract date
    result["year"] = pd.to_numeric(df.get("date", df.get("Date")), errors="coerce")
    
    # Extract value
    result["value"] = pd.to_numeric(df.get("value", df.get("Value")), errors="coerce")
    
    # Extract country code
    if "countryiso3code" in df.columns:
        result["country_code"] = df["countryiso3code"]
    elif "Country Code" in df.columns:
        result["country_code"] = df["Country Code"]
    
    # Extract unit
    result["unit"] = df.get("unit", df.get("Unit", "unknown"))
    result["source_id"] = df.get("source_id", df.get("Source ID", ""))
    
    # Drop rows with missing year or value
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── PRIMAP-hist Normalizer ─────────────────────────────────────────────

@register_normalizer("primap_hist")
def normalize_primap(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize PRIMAP-hist wide format to long format.
    
    Raw format has years as column names (1750, 1751, ...).
    """
    # Identify year columns (numeric column names)
    year_cols = [c for c in df.columns if str(c).isdigit() or (str(c).startswith("-") and str(c)[1:].isdigit())]
    
    if not year_cols:
        return df
    
    # Rename any conflicting 'value' column before melt
    rename_map = {}
    if "value" in df.columns:
        rename_map["value"] = "_primap_value_temp"
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # Melt to long format
    id_cols = [c for c in df.columns if c not in year_cols]
    result = df.melt(
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="year",
        value_name="_primap_melt_value",
    )
    
    result["year"] = pd.to_numeric(result["year"], errors="coerce")
    result["value"] = pd.to_numeric(result["_primap_melt_value"], errors="coerce")
    result = result.drop(columns=[c for c in result.columns if c.startswith("_primap")], errors="ignore")
    
    # Set standard columns
    if "area_(iso3)" in result.columns:
        result["country_code"] = result["area_(iso3)"]
    
    if "unit" in result.columns:
        result["unit"] = result["unit"]
    
    # Filter to World aggregate — PRIMAP uses "EARTH" for World
    world_codes = ["World", "WLD", "EARTH", "GLO"]
    if "country_code" in result.columns:
        world_mask = result["country_code"].isin(world_codes)
        if world_mask.any():
            result = result[world_mask].copy()
    
    # Aggregate by year (sum across IPCC categories)
    if "year" in result.columns and "value" in result.columns:
        result = result.groupby("year", as_index=False).agg(
            value=("value", "sum"),
        )
        # Add back standard columns
        result["unit"] = "kt_CO2"
        result["country_code"] = "EARTH"
        result["source_id"] = "primap_hist"
        result["quality_flag"] = "OK"
    
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── CEDS Normalizer ────────────────────────────────────────────────────

@register_normalizer("ceds_")
def normalize_ceds(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize CEDS wide format to long format.
    
    Raw format has years as column names (x1750, x1751, ...).
    """
    # Identify year columns (xYYYY pattern)
    year_cols = [c for c in df.columns if str(c).startswith("x") and str(c)[1:].isdigit()]
    
    if not year_cols:
        return df
    
    # Rename any conflicting 'value' column before melt
    rename_map = {}
    if "value" in df.columns:
        rename_map["value"] = "_ceds_value_temp"
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # Melt to long format
    id_cols = [c for c in df.columns if c not in year_cols]
    result = df.melt(
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="year",
        value_name="_ceds_melt_value",
    )
    
    # Clean year column (remove 'x' prefix)
    result["year"] = result["year"].str.replace("x", "").astype(int)
    result["value"] = pd.to_numeric(result["_ceds_melt_value"], errors="coerce")
    result = result.drop(columns=[c for c in result.columns if c.startswith("_ceds")], errors="ignore")
    
    # Set standard columns
    if "units" in result.columns:
        result["unit"] = result["units"]
    
    # CEDS is already a world aggregate dataset
    result["country_code"] = "World"
    
    # Aggregate by year (sum across sectors/fuels)
    if "year" in result.columns and "value" in result.columns:
        result = result.groupby("year", as_index=False).agg(
            value=("value", "sum"),
        )
        # Add back standard columns
        result["unit"] = "kt"
        result["country_code"] = "World"
        result["source_id"] = "ceds_so2"
        result["quality_flag"] = "OK"
    
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── UNDP HDR Normalizer ────────────────────────────────────────────────

@register_normalizer("undp_hdr")
def normalize_undp(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize UNDP HDR wide format to long format.
    
    Raw format has HDI values as hdi_YYYY columns.
    """
    # Identify HDI year columns (hdi_YYYY pattern)
    hdi_cols = [c for c in df.columns if str(c).startswith("hdi_") and str(c)[4:].isdigit()]
    
    if not hdi_cols:
        return df
    
    # Rename any conflicting 'value' column before melt
    rename_map = {}
    if "value" in df.columns:
        rename_map["value"] = "_hdi_value_temp"
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # Melt to long format
    id_cols = [c for c in df.columns if c not in hdi_cols]
    result = df.melt(
        id_vars=id_cols,
        value_vars=hdi_cols,
        var_name="year",
        value_name="hdi_val",
    )
    
    # Clean year column (remove 'hdi_' prefix)
    result["year"] = result["year"].str.replace("hdi_", "").astype(int)
    result["value"] = pd.to_numeric(result["hdi_val"], errors="coerce")
    
    # Clean up temp columns
    result = result.drop(columns=[c for c in result.columns if c.startswith("_hdi_")], errors="ignore")
    
    # Set standard columns
    if "iso3" in result.columns:
        result["country_code"] = result["iso3"]
    
    result["unit"] = "index"
    
    # Filter to World if available
    if "country_code" in result.columns:
        world_codes = ["WLD", "World", "999"]
        world_mask = result["country_code"].isin(world_codes)
        if world_mask.any():
            result = result[world_mask].copy()
        else:
            # Aggregate all countries
            result = result.groupby("year", as_index=False)["value"].mean()
            result["country_code"] = "World"
    
    result = result.dropna(subset=["year", "value"])

    return result


# ── EIA Normalizer ──────────────────────────────────────────────────

@register_normalizer("eia_")
def normalize_eia(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize EIA API output.
    
    EIA data has 'period' as year string and 'value' as string.
    Aggregates to annual total across all series.
    """
    result = pd.DataFrame()
    
    # Extract year from period
    if "period" in df.columns:
        result["year"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    elif "date" in df.columns:
        result["year"] = pd.to_datetime(df["date"]).dt.year
    
    # Convert value from string to numeric
    if "value" in df.columns:
        result["value"] = pd.to_numeric(df["value"], errors="coerce")
    
    result["unit"] = df.get("unit", df.get("Unit", "unknown"))
    result["country_code"] = "USA"
    result["source_id"] = df.get("source_id", df.get("Source ID", ""))
    result["quality_flag"] = "OK"
    
    # Aggregate to annual total
    if "year" in result.columns and "value" in result.columns:
        result = result.groupby("year", as_index=False).agg(
            value=("value", "sum"),
            unit=("unit", "first"),
            country_code=("country_code", "first"),
            source_id=("source_id", "first"),
            quality_flag=("quality_flag", "first"),
        )
    
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── IMF WEO Normalizer ───────────────────────────────────────────

@register_normalizer("imf_")
def normalize_imf_weo(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize IMF WEO Excel data.
    
    WEO data is in complex Excel format with header rows.
    For now, pass through as metadata.
    """
    result = df.copy()
    # WEO data is complex Excel — metadata only for now
    if "year" not in result.columns and "Date" in result.columns:
        result["year"] = pd.to_numeric(result["Date"], errors="coerce")
    return result


# ── Nebel 2023 Normalizer ────────────────────────────────────────

@register_normalizer("nebel_")
def normalize_nebel_2023(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Nebel 2023 supplementary data.
    
    Currently metadata-only (docx file).
    """
    return df.copy()


# ── USGS Normalizer ──────────────────────────────────────────────

@register_normalizer("usgs_")
def normalize_usgs(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize USGS Mineral Commodity Summaries.
    
    Currently a metadata-only connector (publication page URL).
    """
    result = df.copy()
    if "year" not in result.columns and "fetched_at" in result.columns:
        result["year"] = pd.to_datetime(result["fetched_at"]).dt.year
    return result


# ── Climate TRACE Normalizer ───────────────────────────────────────────

@register_normalizer("climate_trace")
def normalize_climate_trace(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Climate TRACE monthly format to annual.
    
    Raw format has monthly columns (jan._2026_total, prev._month, etc.).
    We extract annual totals and yoy change.
    """
    # Find year columns (YYYY_total pattern)
    year_cols = [c for c in df.columns if "_ytd" in c.lower()]
    
    if not year_cols:
        # Try to find any year-like columns
        year_cols = [c for c in df.columns if any(str(c).startswith(str(y)) for y in range(2015, 2030))]
    
    if not year_cols:
        return df
    
    # Rename any conflicting 'value' column before melt
    rename_map = {}
    if "value" in df.columns:
        rename_map["value"] = "_ct_value_temp"
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # Melt to long format
    id_cols = [c for c in df.columns if c not in year_cols]
    result = df.melt(
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="year",
        value_name="_ct_melt_value",
    )
    
    # Extract year from column name
    result["year"] = result["year"].str.extract(r"(\d{4})").astype(int)
    result["value"] = pd.to_numeric(result["_ct_melt_value"], errors="coerce")
    result = result.drop(columns=[c for c in result.columns if c.startswith("_ct")], errors="ignore")
    
    result["unit"] = "Mt_CO2e"
    result["country_code"] = "Global"
    
    # Aggregate by year (sum across sectors)
    if "year" in result.columns and "value" in result.columns:
        result = result.groupby("year", as_index=False).agg(
            value=("value", "sum"),
        )
        # Add back standard columns
        result["unit"] = "Mt_CO2e"
        result["country_code"] = "Global"
        result["source_id"] = "climate_trace"
        result["quality_flag"] = "OK"
    
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── FRED Normalizer ────────────────────────────────────────────────────

@register_normalizer("fred_")
def normalize_fred(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FRED API output.
    
    Raw format has 'date' as string and 'value' as string.
    Aggregates to annual mean if there are multiple observations per year.
    """
    result = pd.DataFrame()
    
    # Extract year from date
    if "date" in df.columns:
        result["year"] = pd.to_datetime(df["date"]).dt.year
    elif "DATE" in df.columns:
        result["year"] = pd.to_datetime(df["DATE"]).dt.year
    elif "year" in df.columns:
        result["year"] = pd.to_numeric(df["year"], errors="coerce")
    
    # Extract value
    if "value" in df.columns:
        result["value"] = pd.to_numeric(df["value"], errors="coerce")
    elif "VALUE" in df.columns:
        result["value"] = pd.to_numeric(df["VALUE"], errors="coerce")
    
    result["unit"] = df.get("unit", df.get("UNIT", df.get("units", "unknown")))
    result["source_id"] = df.get("source_id", df.get("Source ID", ""))
    result["country_code"] = "USA"
    result["quality_flag"] = "OK"
    
    # Aggregate to annual mean if there are duplicates
    if "year" in result.columns and "value" in result.columns:
        result = result.groupby("year", as_index=False).agg(
            value=("value", "mean"),
            unit=("unit", "first"),
            source_id=("source_id", "first"),
            country_code=("country_code", "first"),
            quality_flag=("quality_flag", "first"),
        )
    
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── GCP Normalizer ─────────────────────────────────────────────────────

@register_normalizer("gcp_")
def normalize_gcp(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize GCP data (already in standard format, just ensure columns)."""
    result = df.copy()
    
    if "year" not in result.columns and "Year" in result.columns:
        result["year"] = result["Year"]
    
    if "co2_mt" in result.columns and "value" not in result.columns:
        result["value"] = result["co2_mt"]
    
    if "country" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["country"]
    
    return result


# ── NOAA Normalizer ────────────────────────────────────────────────────

@register_normalizer("noaa_")
def normalize_noaa(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize NOAA CO2 data (already standard, ensure columns)."""
    result = df.copy()
    
    if "year" not in result.columns and "Year" in result.columns:
        result["year"] = result["Year"]
    
    if "co2_ppm" in result.columns and "value" not in result.columns:
        result["value"] = result["co2_ppm"]
    
    result["unit"] = "ppm"
    result["country_code"] = "Global"
    
    return result


# ── NASA GISS Normalizer ───────────────────────────────────────────────

@register_normalizer("nasa_giss")
def normalize_nasa_giss(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize NASA GISS data (already standard)."""
    result = df.copy()
    
    if "year" not in result.columns and "Year" in result.columns:
        result["year"] = result["Year"]
    
    if "anomaly_c" in result.columns and "value" not in result.columns:
        result["value"] = result["anomaly_c"]
    
    result["unit"] = "degC_anomaly"
    result["country_code"] = "Global"
    
    return result


# ── FAOSTAT Normalizer ─────────────────────────────────────────────────

@register_normalizer("faostat_")
def normalize_faostat(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FAOSTAT data (already standard from new API)."""
    result = df.copy()
    
    if "year" not in result.columns and "Year" in result.columns:
        result["year"] = result["Year"]
    
    if "value" not in result.columns and "Value" in result.columns:
        result["value"] = pd.to_numeric(result["Value"], errors="coerce")
    
    if "area_code" in result.columns:
        result["country_code"] = result["area_code"]
    elif "Area Code" in result.columns:
        result["country_code"] = result["Area Code"]

    return result


# ── Carbon Atlas Normalizer ────────────────────────────────────────────────

@register_normalizer("global_carbon_atlas")
def normalize_carbon_atlas(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Carbon Atlas data (now numeric from GCP)."""
    result = df.copy()

    if "year" not in result.columns and "Year" in result.columns:
        result["year"] = result["Year"]

    if "total" in result.columns and "value" not in result.columns:
        result["value"] = pd.to_numeric(result["total"], errors="coerce")

    if "country" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["country"]

    result["unit"] = "Mt_CO2"

    # Drop rows with null values first
    result = result.dropna(subset=["year", "value"])

    # Filter to World aggregate
    world_codes = ["World", "Global", "WLD"]
    if "country_code" in result.columns:
        world_mask = result["country_code"].isin(world_codes)
        if not world_mask.any():
            # Sum all countries by year
            result = result.groupby("year", as_index=False).agg(
                value=("value", "sum"),
            )
            result["country_code"] = "World"
            result["unit"] = "Mt_CO2"
        else:
            result = result[world_mask].copy()

    return result


# ── FRED Normalizer (generic) ────────────────────────────────────────────

@register_normalizer("fred_FEDFUNDS")
def normalize_fred_fedfunds(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FRED Federal Funds Rate."""
    result = pd.DataFrame()
    if "date" in df.columns:
        result["year"] = pd.to_datetime(df["date"]).dt.year
    elif "DATE" in df.columns:
        result["year"] = pd.to_datetime(df["DATE"]).dt.year
    if "value" in df.columns:
        result["value"] = pd.to_numeric(df["value"], errors="coerce")
    result["unit"] = "percent"
    result["country_code"] = "USA"
    result["source_id"] = "fred_FEDFUNDS"
    result["quality_flag"] = "OK"
    return result.dropna(subset=["year", "value"])


@register_normalizer("fred_MICH")
def normalize_fred_mich(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FRED Consumer Sentiment."""
    result = pd.DataFrame()
    if "date" in df.columns:
        result["year"] = pd.to_datetime(df["date"]).dt.year
    elif "DATE" in df.columns:
        result["year"] = pd.to_datetime(df["DATE"]).dt.year
    if "value" in df.columns:
        result["value"] = pd.to_numeric(df["value"], errors="coerce")
    result["unit"] = "index"
    result["country_code"] = "USA"
    result["source_id"] = "fred_MICH"
    result["quality_flag"] = "OK"
    return result.dropna(subset=["year", "value"])


# ── UN Comtrade Normalizer ──────────────────────────────────────────────

@register_normalizer("comtrade_")
@register_normalizer("un_comtrade")
def normalize_comtrade(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize UN Comtrade data."""
    result = df.copy()
    if "year" not in result.columns and "Year" in result.columns:
        result["year"] = result["Year"]
    if "value" not in result.columns and "Value" in result.columns:
        result["value"] = pd.to_numeric(result["Value"], errors="coerce")
    if "country_code" not in result.columns:
        if "Country Code" in result.columns:
            result["country_code"] = result["Country Code"]
        elif "iso_alpha3" in result.columns:
            result["country_code"] = result["iso_alpha3"]
    return result


# ── OECD Normalizer ──────────────────────────────────────────────

# OECD REF_AREA code mapping (from SNA_TABLE4 defaults)
OECD_COUNTRY_CODES = {
    "0": "AUS", "1": "AUT", "2": "BEL", "3": "CAN", "4": "CHL", "5": "COL",
    "6": "CRI", "7": "CZE", "8": "DNK", "9": "EST", "10": "FIN", "11": "FRA",
    "12": "DEU", "13": "GRC", "14": "HUN", "15": "ISL", "16": "IRL", "17": "ISR",
    "18": "ITA", "19": "JPN", "20": "KOR", "21": "LVA", "22": "LTU", "23": "LUX",
    "24": "MEX", "25": "NLD", "26": "NZL", "27": "NOR", "28": "POL", "29": "PRT",
    "30": "SVK", "31": "SVN", "32": "ESP", "33": "SWE", "34": "CHE", "35": "TUR",
    "36": "GBR", "37": "USA",
}

# TIME_PERIOD: base year is 1949, index 0 = 1949
OECD_TIME_BASE = 1949


@register_normalizer("oecd_")
def normalize_oecd(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OECD SDMX-JSON output.
    
    SDMX-JSON uses numeric indices for dimensions.
    REF_AREA codes map to ISO3, TIME_PERIOD is offset from 1949.
    """
    result = df.copy()
    
    # Map REF_AREA indices to ISO3 codes
    if "REF_AREA" in result.columns:
        result["country_code"] = result["REF_AREA"].map(OECD_COUNTRY_CODES).fillna(result["REF_AREA"])
    
    # Map TIME_PERIOD indices to actual years
    if "TIME_PERIOD" in result.columns:
        result["year"] = pd.to_numeric(result["TIME_PERIOD"], errors="coerce")
        if result["year"].notna().any():
            result["year"] = (result["year"] + OECD_TIME_BASE).astype("Int64")
    
    # Rename OBS_VALUE to value
    if "OBS_VALUE" in result.columns and "value" not in result.columns:
        result["value"] = pd.to_numeric(result["OBS_VALUE"], errors="coerce")
    
    result = result.dropna(subset=["year", "value"])
    
    return result


# ── OWID Normalizer ──────────────────────────────────────────────

@register_normalizer("owid_")
def normalize_owid(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OWID search results or parquet data.
    
    Search results are metadata only.
    Parquet data has columns: [country, year, {column_name}].
    """
    result = df.copy()
    
    # Check if this is actual data (has year column)
    if "year" in result.columns:
        result["year"] = pd.to_numeric(result["year"], errors="coerce")
        if "value" not in result.columns:
            # Try to find the data column (might be named differently)
            for col in result.columns:
                if col not in ["year", "country", "country_code", "entity", "source_id", 
                               "source_variable", "indicator_id", "original_column",
                               "quality_flag"]:
                    result["value"] = pd.to_numeric(result[col], errors="coerce")
                    break
        
        if "country" in result.columns and "country_code" not in result.columns:
            result["country_code"] = result["country"]
        
        result = result.dropna(subset=["year", "value"])

    return result


# ── IHME GBD Normalizer ──────────────────────────────────────────────

@register_normalizer("ihme_gbd_")
def normalize_ihme_gbd(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize IHME GBD data from OWID API."""
    result = df.copy()
    if "entity" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["entity"]
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── HMD Normalizer ──────────────────────────────────────────────

@register_normalizer("hmd_")
def normalize_hmd(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize HMD data from OWID API."""
    result = df.copy()
    if "entity" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["entity"]
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── EDGAR Normalizer ──────────────────────────────────────────

@register_normalizer("edgar_")
def normalize_edgar(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize EDGAR GHG emissions data."""
    result = df.copy()
    col_map = {}
    for col in result.columns:
        lower = col.lower().replace(" ", "_")
        if "country" in lower or "iso" in lower or "area" in lower:
            col_map[col] = "country_code"
        elif "year" in lower or "time" in lower:
            col_map[col] = "year"
        elif "emission" in lower or "value" in lower or "co2" in lower:
            col_map[col] = "value"
    if col_map:
        result = result.rename(columns=col_map)
    if "year" in result.columns:
        result["year"] = pd.to_numeric(result["year"], errors="coerce")
    if "value" in result.columns:
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── Gapminder Normalizer ──────────────────────────────────────

@register_normalizer("gapminder_")
def normalize_gapminder(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Gapminder data from World Bank API."""
    result = df.copy()
    if "date" in result.columns and "year" not in result.columns:
        result["year"] = pd.to_numeric(result["date"], errors="coerce").astype("Int64")
    if "countryiso3code" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["countryiso3code"]
    if "value" in result.columns:
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── UNIDO Normalizer ──────────────────────────────────────────────

@register_normalizer("unido_")
def normalize_unido(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize UNIDO data from World Bank API."""
    result = df.copy()
    if "date" in result.columns and "year" not in result.columns:
        result["year"] = pd.to_numeric(result["date"], errors="coerce").astype("Int64")
    if "countryiso3code" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["countryiso3code"]
    if "value" in result.columns:
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── Footprint Network Normalizer ──────────────────────────────────

@register_normalizer("footprint_network")
def normalize_footprint_network(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Footprint Network data from OWID API."""
    result = df.copy()
    if "entity" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["entity"]
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── Service Per Capita Normalizer ──────────────────────────────────

@register_normalizer("gdp_per_capita_service_proxy")
def normalize_service_per_capita_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize service per capita proxy data.
    
    Uses GDP per capita as a proxy for service output per capita.
    """
    result = df.copy()
    if "entity" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["entity"]
    if "date" in result.columns and "year" not in result.columns:
        result["year"] = pd.to_numeric(result["date"], errors="coerce").astype("Int64")
    if "countryiso3code" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["countryiso3code"]
    if "value" in result.columns:
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
    if "year" in result.columns and "value" in result.columns:
        result = result.dropna(subset=["year", "value"])
    return result


# ── USGS Nonrenewable Proxy Normalizer ──────────────────────────────

@register_normalizer("usgs_nonrenewable_proxy")
def normalize_usgs_nonrenewable_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize USGS nonrenewable resource proxy data.
    
    Uses cumulative CO2 emissions as a proxy for resource depletion.
    """
    result = df.copy()
    if "country" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["country"]
    if "year" in result.columns and "value" in result.columns:
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
        result = result.dropna(subset=["year", "value"])
    return result


# ── OWID Daily Caloric Supply Normalizer ─────────────────────────────

@register_normalizer("owid_daily_caloric_supply")
def normalize_owid_daily_caloric_supply(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OWID daily caloric supply data.
    
    OWID provides FAO-sourced daily caloric supply per capita (1274-2023).
    This fills the gap for FAOSTAT data (2010-2023) to cover 1970-2009.
    
    OWID uses numeric entity IDs. Entity 15 = World.
    """
    result = df.copy()
    
    # Map OWID entity IDs to country codes
    # Entity 15 is World in the OWID catalog
    if "entity" in result.columns:
        entity_map = {15: "World"}
        result["country_code"] = result["entity"].map(entity_map)
        # For unmapped entities, keep the entity ID as string
        result["country_code"] = result["country_code"].fillna(result["entity"].astype(str))
    
    if "year" in result.columns and "value" in result.columns:
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
        result = result.dropna(subset=["year", "value"])
    return result


# ── PWT Normalizer ──────────────────────────────────────────────

@register_normalizer("pwt")
def normalize_pwt(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Penn World Table 11.0 data.
    
    PWT columns include: countrycode, year, rnna (capital stock at
    constant 2017 national prices), rgdpo (real GDP), pop (population).
    """
    result = df.copy()
    
    # Standardize country code column
    if "countrycode" in result.columns and "country_code" not in result.columns:
        result["country_code"] = result["countrycode"]
    
    # Ensure year is numeric
    if "year" in result.columns:
        result["year"] = pd.to_numeric(result["year"], errors="coerce")
    
    # Ensure rnna (capital stock) is numeric
    if "rnna" in result.columns:
        result["rnna"] = pd.to_numeric(result["rnna"], errors="coerce")
    
    # Set source metadata if not present
    if "source_id" not in result.columns:
        result["source_id"] = "pwt"
    if "source_variable" not in result.columns:
        result["source_variable"] = "pwt110"
    
    return result
