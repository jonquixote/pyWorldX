"""Data connector protocol and result types (Section 8).

Defines the DataConnector protocol and ConnectorResult for all
empirical data sources. Connectors provide fetch() with caching,
vintage tracking, and proxy method declarations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@dataclass
class ConnectorResult:
    """Result from a data connector fetch.

    Attributes:
        series: the fetched time series data
        unit: unit of the series values
        source: human-readable source name
        source_series_id: machine-readable series identifier
        retrieved_at: ISO timestamp of retrieval
        vintage: data vintage / release date (if applicable)
        proxy_method: description if this is a proxy, not direct measurement
        transform_log: ordered list of transformations applied
    """

    series: "pd.Series[Any]"
    unit: str
    source: str
    source_series_id: str
    retrieved_at: str
    vintage: str | None = None
    proxy_method: str | None = None
    transform_log: list[str] = field(default_factory=list)


@runtime_checkable
class DataConnector(Protocol):
    """Protocol for empirical data connectors (Section 8.1).

    Each connector provides access to a specific data source
    (World Bank, FAOSTAT, etc.) with caching and versioning.
    """

    name: str
    source_url: str

    def fetch(
        self,
        variable_name: str,
        vintage: str | None = None,
    ) -> ConnectorResult:
        """Fetch a time series for the given variable.

        Args:
            variable_name: canonical or source-specific variable name
            vintage: specific data vintage to retrieve (None = latest)

        Returns:
            ConnectorResult with the series and metadata
        """
        ...

    def available_variables(self) -> list[str]:
        """List all variables available from this connector."""
        ...
