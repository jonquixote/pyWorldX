"""Unit conversion transforms (Section 8.5 step 3)."""

from __future__ import annotations

import pandas as pd


def convert_series_units(
    series: "pd.Series[float]",
    from_unit: str,
    to_unit: str,
    factor: float,
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Convert a data series from one unit to another."""
    result = series * factor
    if transform_log is not None:
        transform_log.append(
            f"unit_convert: {from_unit} -> {to_unit} (factor={factor})"
        )
    return result


def calories_to_food_units(
    series: "pd.Series[float]",
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Convert kcal/person/day to World3 food units."""
    factor = 1.0  # identity for abstract units
    result = series * factor
    if transform_log is not None:
        transform_log.append(
            "calories_to_food_units: kcal/person/day -> food_units"
        )
    return result


def normalize_to_base_year(
    series: "pd.Series[float]",
    base_year: int,
    transform_log: list[str] | None = None,
) -> "pd.Series[float]":
    """Normalize series to a base year value (index = 1.0 at base_year)."""
    if base_year not in series.index:
        raise ValueError(f"Base year {base_year} not in series index")
    base_val = series.loc[base_year]
    if abs(base_val) < 1e-15:
        raise ValueError("Base year value is zero, cannot normalize")
    result = series / base_val
    if transform_log is not None:
        transform_log.append(
            f"normalize_to_base_year: base={base_year}, value={base_val}"
        )
    return result
