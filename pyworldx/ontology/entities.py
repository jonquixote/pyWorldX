"""Canonical ontology entities (Section 7.2).

Defines the standard pyWorldX variable namespace.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Dimension(Enum):
    """Physical dimension families."""

    PEOPLE = "people"
    CAPITAL = "capital"
    RESOURCE = "resource"
    POLLUTION = "pollution"
    FOOD = "food"
    LAND = "land"
    TIME = "time"
    WELFARE = "welfare"
    ENERGY = "energy"
    INDUSTRIAL = "industrial"
    SERVICE = "service"
    DIMENSIONLESS = "dimensionless"


class AggregationSemantic(Enum):
    """How a variable aggregates across regions (future-proofing)."""

    SUM = "sum"
    MEAN = "mean"
    WEIGHTED_MEAN = "weighted_mean"
    NOT_AGGREGABLE = "not_aggregable"


@dataclass(frozen=True)
class OntologyEntity:
    """A canonical ontology variable definition."""

    name: str
    dimension: Dimension
    unit_family: str
    role: str  # "stock", "flow", "auxiliary", "parameter"
    description: str
    aggregation: AggregationSemantic = AggregationSemantic.SUM
    typical_source: str = ""
    approximation_notes: str = ""


# ── Canonical entity registry ───────────────────────────────────────

CANONICAL_ENTITIES: dict[str, OntologyEntity] = {
    "population.total": OntologyEntity(
        name="population.total",
        dimension=Dimension.PEOPLE,
        unit_family="people",
        role="stock",
        description="Total global population",
        aggregation=AggregationSemantic.SUM,
        typical_source="UN Population Division",
    ),
    "food.per_capita": OntologyEntity(
        name="food.per_capita",
        dimension=Dimension.FOOD,
        unit_family="food_units",
        role="auxiliary",
        description="Food production per capita",
        aggregation=AggregationSemantic.WEIGHTED_MEAN,
        typical_source="FAOSTAT",
    ),
    "capital.industrial_stock": OntologyEntity(
        name="capital.industrial_stock",
        dimension=Dimension.CAPITAL,
        unit_family="capital_units",
        role="stock",
        description="Total industrial capital stock",
    ),
    "capital.service_stock": OntologyEntity(
        name="capital.service_stock",
        dimension=Dimension.CAPITAL,
        unit_family="capital_units",
        role="stock",
        description="Total service capital stock",
    ),
    "resources.nonrenewable_stock": OntologyEntity(
        name="resources.nonrenewable_stock",
        dimension=Dimension.RESOURCE,
        unit_family="resource_units",
        role="stock",
        description="Remaining nonrenewable resource stock",
        typical_source="USGS/BP",
        approximation_notes="Proxy: cumulative extraction reconstruction",
    ),
    "pollution.persistent_load": OntologyEntity(
        name="pollution.persistent_load",
        dimension=Dimension.POLLUTION,
        unit_family="pollution_units",
        role="stock",
        description="Persistent pollution accumulated load",
        typical_source="NOAA/GCP",
    ),
    "welfare.index": OntologyEntity(
        name="welfare.index",
        dimension=Dimension.WELFARE,
        unit_family="dimensionless",
        role="auxiliary",
        description="Human welfare index (HDI proxy)",
        aggregation=AggregationSemantic.WEIGHTED_MEAN,
        typical_source="UNDP HDR",
    ),
    "welfare.ecological_footprint": OntologyEntity(
        name="welfare.ecological_footprint",
        dimension=Dimension.WELFARE,
        unit_family="dimensionless",
        role="auxiliary",
        description="Ecological footprint index",
        aggregation=AggregationSemantic.WEIGHTED_MEAN,
        typical_source="Global Footprint Network",
    ),
    "capital.industrial_output": OntologyEntity(
        name="capital.industrial_output",
        dimension=Dimension.INDUSTRIAL,
        unit_family="industrial_output_units",
        role="auxiliary",
        description="Industrial output (production flow)",
    ),
    "capital.service_output": OntologyEntity(
        name="capital.service_output",
        dimension=Dimension.SERVICE,
        unit_family="industrial_output_units",
        role="auxiliary",
        description="Service output (production flow)",
    ),
    "agriculture.arable_land": OntologyEntity(
        name="agriculture.arable_land",
        dimension=Dimension.LAND,
        unit_family="hectares",
        role="stock",
        description="Total arable land",
        typical_source="FAOSTAT",
    ),
    "pollution.index": OntologyEntity(
        name="pollution.index",
        dimension=Dimension.DIMENSIONLESS,
        unit_family="dimensionless",
        role="auxiliary",
        description="Normalized persistent pollution index",
    ),
    "resources.extraction_rate": OntologyEntity(
        name="resources.extraction_rate",
        dimension=Dimension.RESOURCE,
        unit_family="resource_units",
        role="flow",
        description="Non-renewable resource extraction rate",
    ),
    "population.birth_rate": OntologyEntity(
        name="population.birth_rate",
        dimension=Dimension.DIMENSIONLESS,
        unit_family="per_year",
        role="auxiliary",
        description="Crude birth rate",
    ),
    "population.death_rate": OntologyEntity(
        name="population.death_rate",
        dimension=Dimension.DIMENSIONLESS,
        unit_family="per_year",
        role="auxiliary",
        description="Crude death rate",
    ),
    "population.life_expectancy": OntologyEntity(
        name="population.life_expectancy",
        dimension=Dimension.TIME,
        unit_family="years",
        role="auxiliary",
        description="Life expectancy at birth",
    ),
}
