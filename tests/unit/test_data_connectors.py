"""Tests for data connectors."""

from __future__ import annotations

import pytest

from pyworldx.data.connectors.base import ConnectorResult
from pyworldx.data.connectors.faostat import FAOSTATConnector
from pyworldx.data.connectors.footprint_network import FootprintNetworkConnector
from pyworldx.data.connectors.fred import FREDConnector
from pyworldx.data.connectors.noaa_co2 import NOAACO2Connector
from pyworldx.data.connectors.our_world_in_data import OWIDConnector
from pyworldx.data.connectors.un_pop import UNPopConnector
from pyworldx.data.connectors.undp_hdr import UNDPHDRConnector
from pyworldx.data.connectors.unido import UNIDOConnector
from pyworldx.data.connectors.world_bank import WorldBankConnector


# All 9 connectors and one of their known variables
CONNECTOR_SPECS: list[tuple[type, str]] = [
    (WorldBankConnector, "GDP"),
    (UNPopConnector, "total_population"),
    (FAOSTATConnector, "food_supply_kcal"),
    (NOAACO2Connector, "atmospheric_co2"),
    (OWIDConnector, "primary_energy"),
    (UNIDOConnector, "manufacturing_value_added"),
    (UNDPHDRConnector, "hdi"),
    (FootprintNetworkConnector, "ecological_footprint"),
    (FREDConnector, "gdp_deflator"),
]


class TestAllConnectorsExist:
    def test_nine_connectors(self) -> None:
        assert len(CONNECTOR_SPECS) == 9


class TestConnectorInstantiation:
    @pytest.mark.parametrize("cls,_var", CONNECTOR_SPECS)
    def test_can_instantiate(self, cls: type, _var: str) -> None:
        connector = cls()
        assert connector is not None


class TestAvailableVariables:
    @pytest.mark.parametrize("cls,_var", CONNECTOR_SPECS)
    def test_returns_non_empty(self, cls: type, _var: str) -> None:
        connector = cls()
        variables = connector.available_variables()
        assert isinstance(variables, list)
        assert len(variables) > 0


class TestFetchKnownVariable:
    @pytest.mark.parametrize("cls,var", CONNECTOR_SPECS)
    def test_fetch_returns_connector_result(self, cls: type, var: str) -> None:
        connector = cls()
        result = connector.fetch(var)
        assert isinstance(result, ConnectorResult)
        assert result.source is not None
        assert result.source_series_id is not None
        assert result.retrieved_at is not None

    @pytest.mark.parametrize("cls,var", CONNECTOR_SPECS)
    def test_fetch_has_unit(self, cls: type, var: str) -> None:
        connector = cls()
        result = connector.fetch(var)
        assert isinstance(result.unit, str) and result.unit


class TestFetchUnknownVariable:
    @pytest.mark.parametrize("cls,_var", CONNECTOR_SPECS)
    def test_raises_on_unknown(self, cls: type, _var: str) -> None:
        connector = cls()
        with pytest.raises(KeyError):
            connector.fetch("totally_nonexistent_variable_xyz")
