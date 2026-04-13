"""Ontology alignment mapper — maps raw sources to pyWorldX ontology entities.

Each raw source (identified by source_id in the raw Parquet store) maps to
one or more ontology entities. The mapper defines:
- Target ontology entity name
- Column name mappings (country, year, value)
- Which transforms to apply
- Unit information
- Country filtering (World only, specific countries, or all)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TransformSpec:
    """Specification for a single transform to apply."""
    name: str
    kwargs: dict = field(default_factory=dict)


@dataclass
class EntityMapping:
    """Mapping from a raw source to an ontology entity."""
    # Target ontology entity name
    entity: str
    
    # Column name mappings
    country_col: Optional[str] = None
    year_col: Optional[str] = "year"
    value_col: str = "value"
    unit_col: Optional[str] = "unit"
    
    # Transform pipeline to apply (in order)
    transforms: list[TransformSpec] = field(default_factory=list)
    
    # Unit of the final aligned value
    unit: Optional[str] = None
    
    # Country filtering: "world" for World aggregate only, 
    # "all" for all countries, or list of specific country codes
    country_filter: str | list[str] = "world"
    world_country_code: str = "5000"  # FAO World code; overridden per-source if needed
    
    # World area name in the source data
    world_area_name: str = "World"
    
    # Quality flags to add
    quality_flag: str = "OK"


# World area codes per source
WORLD_AREA_CODES = {
    "world_bank": "WLD",
    "gcp": "World",
    "primap_hist": "World",
    "noaa": None,  # Single global series
    "nasa_giss": None,  # Single global series
    "eia": None,  # US only
    "undp": None,  # No country column in HDR
    "faostat": "5000",
    "ceds": "World",
    "carbon_atlas": "Global",
    "climate_trace": "Global Total",
    "fred": None,  # Single series
    "imf": None,
    "oecd": "Total",
}


# Ontology mappings for all working connectors
# Organized by source_id prefix → list of entity mappings
ONTOLOGY_MAP: dict[str, list[EntityMapping]] = {
    # ── World Bank ─────────────────────────────────────────────
    "world_bank_SP.POP.TOTL": [
        EntityMapping(
            entity="population.total",
            country_col="country_code",
            year_col="year",
            value_col="value",
            unit="persons",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    "world_bank_NY.GDP.MKTP.CD": [
        EntityMapping(
            entity="gdp.current_usd",
            country_col="country_code",
            year_col="year",
            value_col="value",
            unit="current_USD",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    "world_bank_NY.GDP.DEFL.KD.ZG": [
        EntityMapping(
            entity="gdp.deflator",
            country_col="country_code",
            year_col="year",
            value_col="value",
            unit="index_2015_100",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    "world_bank_NY.GNP.PCAP.CD": [
        EntityMapping(
            entity="gni.per_capita",
            country_col="country_code",
            year_col="year",
            value_col="value",
            unit="current_USD",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    
    # ── GCP Fossil CO₂ ──────────────────────────────────────────
    "gcp_fossil_co2": [
        EntityMapping(
            entity="emissions.co2_fossil",
            country_col="country_code",
            year_col="year",
            value_col="value",
            unit="Mt_CO2",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],

    # ── NOAA CO₂ ────────────────────────────────────────────────
    "noaa_co2_annual": [
        EntityMapping(
            entity="atmospheric.co2",
            year_col="year",
            value_col="value",
            unit="ppm",
            transforms=[],
            country_filter=None,  # Single global series
        ),
    ],
    
    # ── NASA GISS ───────────────────────────────────────────────
    "nasa_giss": [
        EntityMapping(
            entity="temperature.anomaly",
            year_col="year",
            value_col="value",
            unit="degC_anomaly",
            transforms=[],
            country_filter=None,  # Single global series
        ),
    ],
    
    # ── PRIMAP-hist ─────────────────────────────────────────────
    "primap_hist": [
        EntityMapping(
            entity="emissions.co2_fossil",
            country_col="country",
            year_col="year",
            value_col="value",
            unit="kt_CO2",
            transforms=[
                TransformSpec("unit_conversion", {"from_unit": "kt", "to_unit": "Mt", "factor": 0.001}),
                TransformSpec("aggregate_world", {
                    "country_col": "country",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.ch4",
            country_col="country",
            year_col="year",
            value_col="value",
            unit="kt_CH4",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],
    
    # ── FAOSTAT Food Balance Sheets ────────────────────────────
    "faostat_food_balance": [
        EntityMapping(
            entity="food.supply.kcal_per_capita",
            year_col="year",
            value_col="value",
            unit_col="unit",
            unit="kcal_per_capita_per_day",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Grand Total",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Food supply (kcal/capita/day)",
                }),
            ],
            country_filter="world",
            world_country_code="5000",
            world_area_name="World",
        ),
        EntityMapping(
            entity="population.total",
            year_col="year",
            value_col="value",
            unit_col="unit",
            unit="1000_persons",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Population",
                }),
            ],
            country_filter="world",
            world_country_code="5000",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT Historical (FBSH 1961-2013) ────────────────────
    "faostat_food_balance_historical": [
        EntityMapping(
            entity="food.supply.kcal_per_capita",
            year_col="year",
            value_col="value",
            unit="kcal_per_capita_per_day",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Food supply (kcal/capita/day)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="population.total",
            year_col="year",
            value_col="value",
            unit="1000_persons",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Total Population - Both sexes",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT OA Population ──────────────────────────────────
    "faostat_oa_population": [
        EntityMapping(
            entity="population.total",
            year_col="year",
            value_col="value",
            unit="1000_persons",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Total Population - Both sexes",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT RL Land Use ────────────────────────────────────
    "faostat_rl_land_use": [
        EntityMapping(
            entity="land.arable_hectares",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Arable land",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="land.cropland_hectares",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Cropland",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="land.agricultural_land",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agricultural land",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT MK Macro ───────────────────────────────────────
    "faostat_mk_macro": [
        EntityMapping(
            entity="gdp.value_added_agriculture",
            year_col="year",
            value_col="value",
            unit="current_USD",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Value Added (Agriculture, Forestry and Fishing)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="gdp.value_added_manufacturing",
            year_col="year",
            value_col="value",
            unit="current_USD",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Value Added (Total Manufacturing)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],

    # ── FAOSTAT TCL Trade ─────────────────────────────────────────
    "faostat_tcl_trade": [
        EntityMapping(
            entity="trade.agricultural_exports",
            year_col="year",
            value_col="value",
            unit="tonnes",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Export quantity",
                }),
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Grand Total",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="trade.agricultural_imports",
            year_col="year",
            value_col="value",
            unit="tonnes",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Import quantity",
                }),
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Grand Total",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT CP Consumer Prices ────────────────────────────────
    "faostat_cp_consumer_prices": [
        EntityMapping(
            entity="cpi.food",
            year_col="year",
            value_col="value",
            unit="index_2015_100",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Consumer Prices, Food Indices (2015 = 100), median",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT FS Food Security ──────────────────────────────────
    "faostat_fs_food_security": [
        EntityMapping(
            entity="food.security.prevalence_undernourishment",
            year_col="year",
            value_col="value",
            unit="percent",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Prevalence of undernourishment (PoU) (%) - 3-year average",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="food.security.severe_food_insecurity",
            year_col="year",
            value_col="value",
            unit="percent",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Prevalence of severe food insecurity (%)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT PD Deflators ──────────────────────────────────────
    "faostat_pd_deflators": [
        EntityMapping(
            entity="deflator.agricultural_production",
            year_col="year",
            value_col="value",
            unit="index_2015_100",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agricultural production price index (2015 = 100)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT RL Full Land Use (1961-2023) ──────────────────────
    "faostat_rl_full": [
        EntityMapping(
            entity="land.arable_hectares",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Arable land",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="land.cropland_hectares",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Cropland",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="land.agricultural_land",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agricultural land",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="land.permanent_meadows_pastures",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Permanent meadows and pastures",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="land.forest_land",
            year_col="year",
            value_col="value",
            unit="1000_ha",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Forest land",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT EM Agrifood Emissions ─────────────────────────────
    "faostat_em_emissions": [
        EntityMapping(
            entity="emissions.agrifood_total",
            year_col="year",
            value_col="value",
            unit="percent",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agrifood systems",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Emissions Share (CO2eq) (AR5)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.agrifood_per_capita",
            year_col="year",
            value_col="value",
            unit="tonnes_CO2eq_per_capita",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agrifood systems",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Emissions per capita",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT GT Emissions Totals ───────────────────────────────
    "faostat_gt_totals": [
        EntityMapping(
            entity="emissions.agrifood_n2o_direct",
            year_col="year",
            value_col="value",
            unit="kt_CO2eq",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agrifood systems",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Direct emissions (N2O)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.agrifood_n2o_indirect",
            year_col="year",
            value_col="value",
            unit="kt_CO2eq",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Agrifood systems",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Indirect emissions (N2O)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.agrifood_enteric_fermentation",
            year_col="year",
            value_col="value",
            unit="kt_CO2eq",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Enteric Fermentation",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Emissions (CO2eq) (AR5)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.agrifood_manure",
            year_col="year",
            value_col="value",
            unit="kt_CO2eq",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Manure Management",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Emissions (CO2eq) (AR5)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.agrifood_rice",
            year_col="year",
            value_col="value",
            unit="kt_CO2eq",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Rice Cultivation",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Emissions (CO2eq) (AR5)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT GN Energy Use in Agriculture ──────────────────────
    "faostat_gn_energy": [
        EntityMapping(
            entity="energy.use_agriculture",
            year_col="year",
            value_col="value",
            unit="TJ",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Petroleum products",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Energy use in agriculture",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
        EntityMapping(
            entity="emissions.agriculture_co2",
            year_col="year",
            value_col="value",
            unit="kt_CO2",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "item",
                    "value": "Petroleum products",
                }),
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Emissions (CO2)",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT CB Non-Food ───────────────────────────────────────
    "faostat_cb_nonfood": [
        EntityMapping(
            entity="trade.nonfood_production",
            year_col="year",
            value_col="value",
            unit="tonnes",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Production",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    # ── FAOSTAT CBH Non-Food Historical ───────────────────────────
    "faostat_cbh_nonfood": [
        EntityMapping(
            entity="trade.nonfood_production_historical",
            year_col="year",
            value_col="value",
            unit="tonnes",
            transforms=[
                TransformSpec("filter_rows", {
                    "column": "element",
                    "value": "Production",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],

    # ── UNDP HDR ────────────────────────────────────────────────
    "undp_hdr": [
        EntityMapping(
            entity="welfare.hdi",
            year_col="year",
            value_col="value",
            unit="index",
            transforms=[],
            country_filter=None,  # Already aggregated to World by normalizer
        ),
    ],
    
    # ── Climate TRACE ───────────────────────────────────────────
    "climate_trace": [
        EntityMapping(
            entity="emissions.ghg_total",
            year_col="year",
            value_col="value",
            unit="Mt_CO2e",
            transforms=[],
            country_filter=None,  # Already Global by normalizer
        ),
    ],
    
    # ── CEDS ───────────────────────────────────────────────────
    "ceds_so2": [
        EntityMapping(
            entity="emissions.so2",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],

    # ── EIA ────────────────────────────────────────────────────
    "eia_total_energy": [
        EntityMapping(
            entity="energy.consumption",
            year_col="year",
            value_col="value",
            unit="Btu_various",
            transforms=[],
            country_filter=None,  # US only, already normalized
        ),
    ],
    
    # ── Carbon Atlas ───────────────────────────────────────────
    "global_carbon_atlas": [
        EntityMapping(
            entity="emissions.land_use_co2",
            country_col="country_code",
            year_col="year",
            value_col="value",
            unit="Mt_CO2",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],
    # ── CEDS ───────────────────────────────────────────────────
    "ceds_nox": [
        EntityMapping(
            entity="emissions.nox",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ceds_bc": [
        EntityMapping(
            entity="emissions.bc",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ceds_oc": [
        EntityMapping(
            entity="emissions.oc",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ceds_co": [
        EntityMapping(
            entity="emissions.co",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ceds_nh3": [
        EntityMapping(
            entity="emissions.nh3",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ceds_nmvoc": [
        EntityMapping(
            entity="emissions.nmvoc",
            year_col="year",
            value_col="value",
            unit="kt",
            transforms=[],
            country_filter=None,
        ),
    ],
    
    # ── FRED ───────────────────────────────────────────────────
    "fred_GDPDEF": [
        EntityMapping(
            entity="gdp.deflator",
            year_col="year",
            value_col="value",
            unit="index",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter=None,  # Single US series
        ),
    ],
    "fred_CPIAUCSL": [
        EntityMapping(
            entity="cpi",
            year_col="year",
            value_col="value",
            unit="index_1982_84_100",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter=None,
        ),
    ],
    "fred_GDP": [
        EntityMapping(
            entity="gdp.current_usd",
            year_col="year",
            value_col="value",
            unit="current_USD",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter=None,
        ),
    ],
    "fred_GDPC1": [
        EntityMapping(
            entity="gdp.real",
            year_col="year",
            value_col="value",
            unit="chained_2017_USD",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter=None,
        ),
    ],
    "fred_FEDFUNDS": [
        EntityMapping(
            entity="financial.fed_funds_rate",
            year_col="year",
            value_col="value",
            unit="percent",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter=None,
        ),
    ],
    "fred_MICH": [
        EntityMapping(
            entity="economic.consumer_sentiment",
            year_col="year",
            value_col="value",
            unit="index",
            transforms=[
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter=None,
        ),
    ],
    
    # ── USGS ─────────────────────────────────────────────────────
    "usgs_mcs": [
        EntityMapping(
            entity="resources.nonrenewable_stock",
            year_col="year",
            value_col="value",
            unit="metadata",
            transforms=[],
            country_filter=None,
        ),
    ],
    "usgs_nonrenewable_proxy": [
        EntityMapping(
            entity="resources.nonrenewable_stock",
            year_col="year",
            value_col="value",
            unit="resource_units",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],
    
    # ── IMF WEO ──────────────────────────────────────────────────
    "imf_weo": [
        EntityMapping(
            entity="imf.weo_raw",
            year_col=None,  # Excel sheets, complex structure
            value_col=None,
            unit="various",
            transforms=[
                TransformSpec("imf_weo_parse"),
            ],
            country_filter=None,
        ),
    ],
    
    # ── OECD ─────────────────────────────────────────────────────
    "oecd_sna_table4": [
        EntityMapping(
            entity="gdp.current_usd",
            year_col="year",
            value_col="value",
            unit="USD_millions",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "WLD",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    
    # ── Nebel 2023 ───────────────────────────────────────────────
    "nebel_2023_supplement": [
        EntityMapping(
            entity="nebel_2023.raw",
            year_col=None,
            value_col=None,
            unit="metadata",
            transforms=[
                TransformSpec("nebel_2023_parse"),
            ],
            country_filter=None,
        ),
    ],

    # ── PWT 11.0 — Penn World Table ─────────────────────────────
    # rnna: Capital stock at constant 2017 national prices
    # 185 countries, 1950-2023 (aggregated to world total, then interpolated)
    "pwt": [
        EntityMapping(
            entity="capital.industrial_stock",
            year_col="year",
            value_col="rnna",
            country_col="countrycode",
            unit="constant_2017_national_prices",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "countrycode",
                    "world_value": "World",
                }),
                TransformSpec("interpolate_annual", {"method": "linear"}),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],

    # ── OWID ─────────────────────────────────────────────────────
    "owid_search_primary_energy": [
        EntityMapping(
            entity="energy.primary_consumption",
            year_col="year",
            value_col="value",
            unit="TWh",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],
    "owid_search_fossil_co2": [
        EntityMapping(
            entity="emissions.co2_fossil",
            year_col="year",
            value_col="value",
            unit="Mt_CO2",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],
    "owid_search_co2_per_capita": [
        EntityMapping(
            entity="emissions.co2_per_capita",
            year_col="year",
            value_col="value",
            unit="t_CO2_per_capita",
            transforms=[],
            country_filter=None,
        ),
    ],
    "owid_search_gdp_maddison": [
        EntityMapping(
            entity="gdp.maddison",
            year_col="year",
            value_col="value",
            unit="international_dollar",
            transforms=[],
            country_filter=None,
        ),
    ],
    "owid_search_population": [
        EntityMapping(
            entity="population.total",
            year_col="year",
            value_col="value",
            unit="persons",
            transforms=[],
            country_filter=None,
        ),
    ],
    "owid_search_life_expectancy": [
        EntityMapping(
            entity="demographics.life_expectancy",
            year_col="year",
            value_col="value",
            unit="years",
            transforms=[],
            country_filter=None,
        ),
    ],

    # ── OWID Direct Indicators ────────────────────────────────────
    # FAO daily caloric supply (1274-2023) — fills FAOSTAT 1970-2009 gap
    "owid_daily_caloric_supply": [
        EntityMapping(
            entity="food.supply.kcal_per_capita",
            year_col="year",
            value_col="value",
            unit="kcal_per_capita_per_day",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],

    # ── EDGAR ─────────────────────────────────────────────────────
    "edgar_co2": [
        EntityMapping(
            entity="emissions.co2_fossil",
            year_col="year",
            value_col="value",
            unit="Mt_CO2",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],
    
    # ── IHME GBD ──────────────────────────────────────────────────
    "ihme_gbd_dalys": [
        EntityMapping(
            entity="health.dalys",
            year_col="year",
            value_col="value",
            unit="dalys_per_100k",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ihme_gbd_child_mortality": [
        EntityMapping(
            entity="health.child_mortality",
            year_col="year",
            value_col="value",
            unit="deaths_per_1000",
            transforms=[],
            country_filter=None,
        ),
    ],
    "ihme_gbd_life_expectancy": [
        EntityMapping(
            entity="health.life_expectancy",
            year_col="year",
            value_col="value",
            unit="years",
            transforms=[],
            country_filter=None,
        ),
    ],
    
    # ── HMD ──────────────────────────────────────────────────────
    "hmd_life_expectancy": [
        EntityMapping(
            entity="demographics.life_expectancy",
            year_col="year",
            value_col="value",
            unit="years",
            transforms=[],
            country_filter=None,
        ),
    ],
    
    # ── Gapminder ────────────────────────────────────────────────
    "gapminder_population": [
        EntityMapping(
            entity="population.total",
            year_col="year",
            value_col="value",
            unit="persons",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "WLD",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],
    "gapminder_gdp_per_capita": [
        EntityMapping(
            entity="gdp.per_capita",
            year_col="year",
            value_col="value",
            unit="constant_2015_USD",
            transforms=[],
            country_filter=None,
        ),
    ],
    "gapminder_life_expectancy": [
        EntityMapping(
            entity="demographics.life_expectancy",
            year_col="year",
            value_col="value",
            unit="years",
            transforms=[],
            country_filter=None,
        ),
    ],
    
    # ── UNIDO ─────────────────────────────────────────────────────
    "unido_manufacturing_value_added": [
        EntityMapping(
            entity="industry.manufacturing_value_added",
            year_col="year",
            value_col="value",
            unit="constant_2015_USD",
            transforms=[],
            country_filter=None,
        ),
    ],
    "unido_industry_value_added": [
        EntityMapping(
            entity="industry.value_added",
            year_col="year",
            value_col="value",
            unit="constant_2015_USD",
            transforms=[],
            country_filter=None,
        ),
    ],

    # ── Footprint Network ─────────────────────────────────────────
    "footprint_network": [
        EntityMapping(
            entity="welfare.ecological_footprint",
            year_col="year",
            value_col="value",
            unit="global_hectares",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "World",
                }),
            ],
            country_filter="world",
            world_country_code="World",
            world_area_name="World",
        ),
    ],

    # ── World Bank Services — Service Output Per Capita ──────────
    # NV.SRV.TOTL.KD: Services, value added (constant 2015 US$)
    # Divided by population to get per-capita service output
    "world_bank_NV.SRV.TOTL.KD": [
        EntityMapping(
            entity="output.service_per_capita",
            year_col="year",
            value_col="value",
            unit="constant_2015_USD_per_capita",
            transforms=[
                TransformSpec("aggregate_world", {
                    "country_col": "country_code",
                    "world_value": "WLD",
                }),
                TransformSpec("derive_per_capita", {
                    "population_source_id": "world_bank_SP.POP.TOTL",
                }),
            ],
            country_filter="world",
            world_country_code="WLD",
            world_area_name="World",
        ),
    ],

    # ── World3-03 Reference Trajectories ─────────────────────────
    # Canonical Standard Run reference data (embedded, not fetched).
    # Used for Layer 1 structural validation.
    "world3_reference_population": [
        EntityMapping(
            entity="population.total",
            year_col="year",
            value_col="value",
            unit="persons",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_industrial_output": [
        EntityMapping(
            entity="gdp.current_usd",
            year_col="year",
            value_col="value",
            unit="industrial_output_units",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_food_per_capita": [
        EntityMapping(
            entity="food.supply.kcal_per_capita",
            year_col="year",
            value_col="value",
            unit="veg_equiv_kg_per_person_yr",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_nr_fraction_remaining": [
        EntityMapping(
            entity="resources.nonrenewable_stock",
            year_col="year",
            value_col="value",
            unit="dimensionless",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_pollution_index": [
        EntityMapping(
            entity="atmospheric.co2",
            year_col="year",
            value_col="value",
            unit="dimensionless",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_life_expectancy": [
        EntityMapping(
            entity="welfare.life_expectancy",
            year_col="year",
            value_col="value",
            unit="years",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_human_welfare_index": [
        EntityMapping(
            entity="hdi.human_development_index",
            year_col="year",
            value_col="value",
            unit="dimensionless",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],
    "world3_reference_ecological_footprint": [
        EntityMapping(
            entity="welfare.ecological_footprint",
            year_col="year",
            value_col="value",
            unit="dimensionless",
            transforms=[],
            country_filter=None,
            quality_flag="REFERENCE",
        ),
    ],

    # ── USGS resource proxies (Layer 3 cross-validation) ──────────────
    "usgs_resource_extraction_index": [
        EntityMapping(
            entity="resources.extraction_index",
            year_col="year",
            value_col="value",
            unit="index_1996_eq_100",
            transforms=[],
            country_filter=None,
            quality_flag="PROXY",
        ),
    ],
    "usgs_reserve_depletion_ratio": [
        EntityMapping(
            entity="resources.depletion_ratio",
            year_col="year",
            value_col="value",
            unit="dimensionless",
            transforms=[],
            country_filter=None,
            quality_flag="PROXY",
        ),
    ],
}


def get_mappings(source_id: str) -> list[EntityMapping]:
    """Get ontology mappings for a raw source ID.
    
    Args:
        source_id: Source identifier (e.g. "world_bank_SP.POP.TOTL").
    
    Returns:
        List of EntityMapping objects for this source.
        Returns empty list if no mappings exist.
    """
    # Exact match first
    if source_id in ONTOLOGY_MAP:
        return ONTOLOGY_MAP[source_id]
    
    # Prefix match
    for prefix, mappings in ONTOLOGY_MAP.items():
        if source_id.startswith(prefix):
            return mappings
    
    return []


def get_all_entities() -> list[str]:
    """Get all unique ontology entity names from the map."""
    entities = set()
    for mappings in ONTOLOGY_MAP.values():
        for m in mappings:
            entities.add(m.entity)
    return sorted(entities)


def get_source_ids_for_entity(entity: str) -> list[str]:
    """Get all source IDs that map to a given entity."""
    source_ids = []
    for source_id, mappings in ONTOLOGY_MAP.items():
        for m in mappings:
            if m.entity == entity:
                source_ids.append(source_id)
    return source_ids
