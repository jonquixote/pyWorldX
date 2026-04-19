"""Unit tests for BPStatisticalReviewConnector — T2-2."""

from __future__ import annotations

import pytest
import pandas as pd
from unittest.mock import patch


def test_bp_connector_exists():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector is not None


def test_bp_connector_schema():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    with patch.object(c, "_raw_fetch") as mock:
        mock.return_value = pd.DataFrame({
            "year": list(range(1965, 2024)),
            "proved_reserves_ej": [500.0 + i * 5 for i in range(59)],
        })
        df = c.fetch()
    assert "year" in df.columns
    assert "proved_reserves_ej" in df.columns
    assert df["year"].min() <= 1970
    assert df["year"].max() >= 2020


def test_bp_connector_no_gap_over_three_years():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    with patch.object(c, "_raw_fetch") as mock:
        years = list(range(1965, 2024))
        mock.return_value = pd.DataFrame({
            "year": years,
            "proved_reserves_ej": [500.0] * len(years),
        })
        df = c.fetch()
    year_set = set(df["year"])
    for y in range(1965, 2021):
        gap = sum(1 for d in range(4) if (y + d) not in year_set)
        assert gap < 4, f"Gap >3 years starting at {y}"


def test_bp_connector_tagged_layer_1():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector.layer == 1, (
        "BP proved reserves is an observed proxy (Layer 1), not a structural reference (Layer 0)."
    )


def test_world3_nr_reference_not_in_engine_map():
    from pyworldx.data.bridge import ENTITY_TO_ENGINE_MAP, WORLD3_NAMESPACE
    assert "world3_reference_nonrenewable_resources" not in ENTITY_TO_ENGINE_MAP
    assert "world3.nr_fraction" in WORLD3_NAMESPACE


def test_bp_connector_entity_is_nonrenewable_proved_reserves():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector.entity == "nonrenewable_resources_proved_reserves"


def test_bp_connector_unit_is_ej():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector.unit == "EJ"


def test_bp_connector_has_source_url():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert hasattr(BPStatisticalReviewConnector, "source_url"), (
        "BPStatisticalReviewConnector must declare source_url as a named attribute."
    )
    assert BPStatisticalReviewConnector.source_url.startswith("http"), (
        "source_url must be a valid URL."
    )


def test_bp_raw_fetch_is_injectable():
    """_raw_fetch must be a method that can be patched in tests."""
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    assert hasattr(c, "_raw_fetch"), (
        "_raw_fetch must be a method on the connector instance, injectable for testing."
    )
