"""Tests for data connectors — base protocol and CSV connector."""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from pyworldx.data.connectors.base import ConnectorResult, DataConnector
from pyworldx.data.connectors.csv_connector import CSVConnector


class TestConnectorResult:
    def test_fields(self) -> None:
        series: pd.Series[float] = pd.Series([1.0, 2.0], index=[2000, 2001], name="x")
        result = ConnectorResult(
            series=series,
            unit="persons",
            source="test",
            source_series_id="x",
            retrieved_at="2024-01-01T00:00:00Z",
        )
        assert result.unit == "persons"
        assert result.vintage is None
        assert result.proxy_method is None
        assert result.transform_log == []

    def test_optional_fields(self) -> None:
        series: pd.Series[float] = pd.Series([1.0], index=[2000], name="y")
        result = ConnectorResult(
            series=series,
            unit="kg",
            source="test",
            source_series_id="y",
            retrieved_at="2024-01-01T00:00:00Z",
            vintage="2024-Q1",
            proxy_method="interpolated",
            transform_log=["scaled", "smoothed"],
        )
        assert result.vintage == "2024-Q1"
        assert result.proxy_method == "interpolated"
        assert result.transform_log == ["scaled", "smoothed"]


class TestDataConnectorProtocol:
    def test_csv_connector_is_data_connector(self) -> None:
        connector = CSVConnector(name="test", source_url=".")
        assert isinstance(connector, DataConnector)


class TestCSVConnector:
    @pytest.fixture()
    def csv_dir(self, tmp_path: object) -> str:
        """Create a temp directory with a test CSV file."""
        d = tempfile.mkdtemp()
        df = pd.DataFrame({"year": [2000, 2001, 2002], "value": [1.0, 2.0, 3.0]})
        df.to_csv(os.path.join(d, "test_var.csv"), index=False)
        return d

    def test_fetch_returns_connector_result(self, csv_dir: str) -> None:
        connector = CSVConnector(
            name="test",
            source_url=csv_dir,
            file_map={"test_var": "test_var.csv"},
            unit_map={"test_var": "persons"},
        )
        result = connector.fetch("test_var")
        assert isinstance(result, ConnectorResult)
        assert result.unit == "persons"
        assert len(result.series) == 3

    def test_fetch_caches(self, csv_dir: str) -> None:
        connector = CSVConnector(
            name="test",
            source_url=csv_dir,
            file_map={"test_var": "test_var.csv"},
        )
        r1 = connector.fetch("test_var")
        r2 = connector.fetch("test_var")
        assert r1 is r2

    def test_fetch_unknown_raises(self) -> None:
        connector = CSVConnector(name="test", source_url=".")
        with pytest.raises(FileNotFoundError, match="No file mapping"):
            connector.fetch("nonexistent")

    def test_available_variables(self, csv_dir: str) -> None:
        connector = CSVConnector(
            name="test",
            source_url=csv_dir,
            file_map={"a": "a.csv", "b": "b.csv"},
        )
        assert set(connector.available_variables()) == {"a", "b"}

    def test_stubs_removed(self) -> None:
        """Verify that the 9 dead stub connector modules no longer exist."""
        import pyworldx.data.connectors as pkg

        pkg_dir = os.path.dirname(pkg.__file__)
        stubs = [
            "world_bank.py",
            "fred.py",
            "faostat.py",
            "noaa_co2.py",
            "our_world_in_data.py",
            "un_pop.py",
            "undp_hdr.py",
            "unido.py",
            "footprint_network.py",
        ]
        for stub in stubs:
            assert not os.path.exists(os.path.join(pkg_dir, stub)), f"{stub} still exists"
