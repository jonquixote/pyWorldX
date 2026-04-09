"""Tests for the transform chain executor."""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.alignment.map import EntityMapping
from data_pipeline.transforms.chain import (
    TRANSFORM_REGISTRY,
    transform_aggregate_world,
    transform_filter_rows,
    transform_interpolate_annual,
    transform_unit_conversion,
)


@pytest.fixture
def gcp_data():
    """GCP-style data: country, year, co2_mt columns."""
    return pd.DataFrame({
        "country": ["Afghanistan", "Afghanistan", "Albania", "Albania", "World", "World"],
        "year": [2020, 2021, 2020, 2021, 2020, 2021],
        "co2_mt": [10.0, 12.0, 5.0, 6.0, 34000.0, 35000.0],
        "source_id": ["gcp"] * 6,
    })


@pytest.fixture
def wide_data():
    """Wide format data with year columns."""
    return pd.DataFrame({
        "country": ["World", "USA", "China"],
        "x2020": [100.0, 30.0, 40.0],
        "x2021": [110.0, 35.0, 45.0],
        "x2022": [120.0, 38.0, 50.0],
    })


@pytest.fixture
def sparse_data():
    """Data with gaps in year column."""
    return pd.DataFrame({
        "country": ["World"] * 5,
        "year": [2010, 2011, 2013, 2015, 2016],
        "value": [100.0, 110.0, 130.0, 150.0, 160.0],
    })


# ── aggregate_world tests ──────────────────────────────────────────────

class TestAggregateWorld:
    def test_filters_existing_world_row(self, gcp_data):
        """If 'World' row exists, filter to it."""
        mapping = EntityMapping(
            entity="test",
            country_col="country",
            world_country_code="World",
            world_area_name="World",
            country_filter="world",
        )
        result = transform_aggregate_world(gcp_data, mapping)
        assert len(result) == 2
        assert set(result["country"]) == {"World"}

    def test_sums_all_countries_no_world_row(self, gcp_data):
        """If no 'World' row, sum all countries by year."""
        no_world = gcp_data[gcp_data["country"] != "World"].copy()
        mapping = EntityMapping(
            entity="test",
            country_col="country",
            year_col="year",
            value_col="co2_mt",
            world_country_code="World",
            world_area_name="World",
            country_filter="world",
        )
        result = transform_aggregate_world(no_world, mapping)
        assert len(result) == 2
        assert result[result["year"] == 2020]["co2_mt"].values[0] == 15.0
        assert result[result["year"] == 2021]["co2_mt"].values[0] == 18.0


# ── filter_rows tests ──────────────────────────────────────────────────

class TestFilterRows:
    def test_single_filter(self):
        df = pd.DataFrame({
            "item": ["A", "B", "A", "C"],
            "value": [1, 2, 3, 4],
        })
        mapping = EntityMapping(entity="test")
        result = transform_filter_rows(df, mapping, column="item", value="A")
        assert len(result) == 2
        assert all(result["item"] == "A")

    def test_missing_column_passthrough(self):
        df = pd.DataFrame({"value": [1, 2, 3]})
        mapping = EntityMapping(entity="test")
        result = transform_filter_rows(df, mapping, column="missing", value="A")
        assert len(result) == 3


# ── interpolate_annual tests ──────────────────────────────────────────

class TestInterpolateAnnual:
    def test_fills_gaps(self, sparse_data):
        """Interpolation should fill missing years."""
        mapping = EntityMapping(
            entity="test",
            year_col="year",
            value_col="value",
        )
        result = transform_interpolate_annual(sparse_data, mapping)
        years = sorted(result["year"].unique())
        assert years == [2010, 2011, 2012, 2013, 2014, 2015, 2016]
        # Check interpolation
        assert result[result["year"] == 2012]["value"].values[0] == 120.0
        assert result[result["year"] == 2014]["value"].values[0] == 140.0


# ── unit_conversion tests ──────────────────────────────────────────────

class TestUnitConversion:
    def test_applies_factor(self):
        df = pd.DataFrame({"year": [2020, 2021], "value": [100.0, 200.0]})
        mapping = EntityMapping(entity="test", value_col="value")
        result = transform_unit_conversion(df, mapping, factor=0.001)
        assert result["value"].tolist() == [0.1, 0.2]

    def test_missing_value_column_passthrough(self):
        df = pd.DataFrame({"year": [2020], "other": [100.0]})
        mapping = EntityMapping(entity="test", value_col="value")
        result = transform_unit_conversion(df, mapping, factor=2.0)
        assert len(result) == 1


# ── Registry tests ─────────────────────────────────────────────────────

class TestTransformRegistry:
    def test_all_transforms_registered(self):
        """All known transform names should be in the registry."""
        known = [
            "interpolate_annual",
            "aggregate_world",
            "unit_conversion",
            "filter_rows",
            "imf_weo_parse",
            "nebel_2023_parse",
        ]
        for name in known:
            assert name in TRANSFORM_REGISTRY, f"{name} not in registry"
