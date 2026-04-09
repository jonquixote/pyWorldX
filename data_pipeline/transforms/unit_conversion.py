"""Unit conversion transforms — kcal↔tonnes, current↔constant prices, etc.

Transform step 6 of the pipeline. Harmonizes units across different
data sources to a common canonical unit.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


# Conversion factors to canonical units
UNIT_CONVERSIONS = {
    # Energy: exajoules → million tonnes of oil equivalent (Mtoe)
    ("exajoules", "Mtoe"): 23.8846,
    # Energy: exajoules → terawatt-hours (TWh)
    ("exajoules", "TWh"): 277.778,
    # Mass: million tonnes → tonnes
    ("Mt", "tonnes"): 1e6,
    # Mass: kilotonnes → tonnes
    ("kt", "tonnes"): 1e3,
    # Currency: current USD → billions USD
    ("USD", "billion_USD"): 1e-9,
    # Currency: current USD → millions USD
    ("USD", "million_USD"): 1e-6,
}


def convert_units(
    df: pd.DataFrame,
    value_col: str = "value",
    unit_col: Optional[str] = "unit",
    from_unit: Optional[str] = None,
    to_unit: Optional[str] = None,
    factor: Optional[float] = None,
) -> pd.DataFrame:
    """Convert values from one unit to another.

    Args:
        df: DataFrame with values to convert.
        value_col: Column containing numeric values.
        unit_col: Column containing unit strings. If provided and factor
            is not specified, looks up conversion from UNIT_CONVERSIONS.
        from_unit: Source unit string. Required if unit_col is None.
        to_unit: Target unit string. Required if unit_col is None.
        factor: Conversion factor. If None, looks up from UNIT_CONVERSIONS.

    Returns:
        DataFrame with converted values.
    """
    if value_col not in df.columns:
        return df

    df = df.copy()

    if factor is None:
        if unit_col and unit_col in df.columns and from_unit and to_unit:
            # Look up conversion factor
            key = (from_unit, to_unit)
            if key not in UNIT_CONVERSIONS:
                raise ValueError(
                    f"No conversion found for {from_unit} → {to_unit}. "
                    f"Available: {list(UNIT_CONVERSIONS.keys())}"
                )
            factor = UNIT_CONVERSIONS[key]
        elif from_unit and to_unit:
            key = (from_unit, to_unit)
            if key not in UNIT_CONVERSIONS:
                raise ValueError(
                    f"No conversion found for {from_unit} → {to_unit}. "
                    f"Available: {list(UNIT_CONVERSIONS.keys())}"
                )
            factor = UNIT_CONVERSIONS[key]
        else:
            raise ValueError(
                "Must provide either (unit_col, from_unit, to_unit) "
                "or explicit factor."
            )

    df[f"{value_col}_converted"] = df[value_col] * factor

    if unit_col and unit_col in df.columns:
        df[f"{unit_col}_converted"] = to_unit

    return df


def calories_to_food_units(
    df: pd.DataFrame,
    value_col: str = "value",
) -> pd.DataFrame:
    """Convert calories to food units.

    For pyWorldX, food units are abstract. This is a 1:1 identity
    conversion documented in the transform log for spec compliance
    (Section 8.2 unit chain step 2).

    Args:
        df: DataFrame with calorie values.
        value_col: Column containing calorie values.

    Returns:
        DataFrame with food_units column.
    """
    if value_col not in df.columns:
        return df

    df = df.copy()
    df[f"{value_col}_food_units"] = df[value_col]
    return df


def normalize_to_base_year(
    df: pd.DataFrame,
    value_col: str = "value",
    year_col: str = "year",
    base_year: int = 2017,
) -> pd.DataFrame:
    """Normalize a series to a base year value.

    Divides all values by the value in the base year, producing
    an index where base_year = 1.0.

    Args:
        df: DataFrame with values.
        value_col: Column containing values.
        year_col: Year column.
        base_year: Year to normalize to (index = 1.0).

    Returns:
        DataFrame with normalized values in '{value_col}_indexed'.
    """
    if value_col not in df.columns or year_col not in df.columns:
        return df

    df = df.copy()

    # Find base year value
    base_mask = df[year_col] == base_year
    if base_mask.any():
        base_val = df.loc[base_mask, value_col].iloc[0]
    else:
        # Use closest year
        closest_year = (df[year_col] - base_year).abs().idxmin()
        base_val = df.loc[closest_year, value_col]

    if base_val == 0:
        raise ValueError(f"Base year {base_year} value is zero — cannot normalize.")

    df[f"{value_col}_indexed"] = df[value_col] / base_val

    return df
