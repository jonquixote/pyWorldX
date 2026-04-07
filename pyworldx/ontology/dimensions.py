"""Ontology dimension and unit family definitions (Section 7.1).

Supports the two-layer boundary checking:
1. Sector boundary — runtime unit-checked through Quantity
2. Ontology boundary — semantic dimension, stock/flow role, aggregation
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UnitFamily:
    """A unit family with base unit and known conversions."""

    name: str
    base_unit: str
    description: str
    conversions: dict[str, float] = field(default_factory=dict)


# Standard unit families for pyWorldX
UNIT_FAMILIES: dict[str, UnitFamily] = {
    "people": UnitFamily(
        name="people",
        base_unit="persons",
        description="Population count",
        conversions={"persons": 1.0, "millions": 1e6, "billions": 1e9},
    ),
    "capital_units": UnitFamily(
        name="capital_units",
        base_unit="capital_units",
        description="Abstract capital units (World3 convention)",
        conversions={"capital_units": 1.0},
    ),
    "resource_units": UnitFamily(
        name="resource_units",
        base_unit="resource_units",
        description="Abstract resource units (World3 convention)",
        conversions={"resource_units": 1.0},
    ),
    "pollution_units": UnitFamily(
        name="pollution_units",
        base_unit="pollution_units",
        description="Abstract pollution units (World3 convention)",
        conversions={"pollution_units": 1.0},
    ),
    "food_units": UnitFamily(
        name="food_units",
        base_unit="food_units",
        description="Food production units",
        conversions={"food_units": 1.0, "kcal_per_day": 1.0},
    ),
    "industrial_output_units": UnitFamily(
        name="industrial_output_units",
        base_unit="industrial_output_units",
        description="Industrial/service output units",
        conversions={"industrial_output_units": 1.0},
    ),
    "years": UnitFamily(
        name="years",
        base_unit="years",
        description="Time in years",
        conversions={"years": 1.0, "months": 1.0 / 12.0},
    ),
    "per_year": UnitFamily(
        name="per_year",
        base_unit="per_year",
        description="Rate per year",
        conversions={"per_year": 1.0},
    ),
    "hectares": UnitFamily(
        name="hectares",
        base_unit="hectares",
        description="Land area",
        conversions={"hectares": 1.0, "km2": 100.0},
    ),
    "dimensionless": UnitFamily(
        name="dimensionless",
        base_unit="dimensionless",
        description="Dimensionless quantity",
        conversions={"dimensionless": 1.0, "fraction": 1.0, "percent": 0.01},
    ),
    "EUR_2015": UnitFamily(
        name="EUR_2015",
        base_unit="EUR_2015",
        description="Constant 2015 euros (WILIAM base)",
        conversions={"EUR_2015": 1.0},
    ),
}


def convert_units(
    value: float, from_unit: str, to_unit: str, family_name: str
) -> float:
    """Convert a value between units in the same family."""
    family = UNIT_FAMILIES.get(family_name)
    if family is None:
        raise ValueError(f"Unknown unit family: {family_name}")
    if from_unit not in family.conversions:
        raise ValueError(
            f"Unknown unit '{from_unit}' in family '{family_name}'"
        )
    if to_unit not in family.conversions:
        raise ValueError(
            f"Unknown unit '{to_unit}' in family '{family_name}'"
        )
    base_value = value * family.conversions[from_unit]
    return base_value / family.conversions[to_unit]
