"""World Bank Open Data data connector (Section 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from pyworldx.data.connectors.base import ConnectorResult


class WorldBankConnector:
    """Connector for World Bank Open Data data."""

    SOURCE = "World Bank Open Data"

    AVAILABLE_VARIABLES: dict[str, dict[str, str]] = {
        "GDP": {
            "unit": "current_USD",
            "series_id": "NY.GDP.MKTP.CD",
            "description": "Gross domestic product at current US dollars",
        },
        "population": {
            "unit": "persons",
            "series_id": "SP.POP.TOTL",
            "description": "Total population count",
        },
        "GNI_per_capita": {
            "unit": "current_USD",
            "series_id": "NY.GNP.PCAP.CD",
            "description": "Gross national income per capita at current US dollars",
        },
    }

    def fetch(
        self,
        variable: str,
        start_year: int = 1960,
        end_year: int = 2023,
    ) -> ConnectorResult:
        """Fetch data for a variable (stub — returns empty series with metadata)."""
        if variable not in self.AVAILABLE_VARIABLES:
            raise KeyError(
                f"Variable '{variable}' not available from {self.SOURCE}. "
                f"Available: {list(self.AVAILABLE_VARIABLES.keys())}"
            )
        meta = self.AVAILABLE_VARIABLES[variable]
        idx = pd.RangeIndex(start_year, end_year + 1)
        return ConnectorResult(
            series=pd.Series(dtype=float, index=idx, name=variable),
            unit=meta["unit"],
            source=self.SOURCE,
            source_series_id=meta["series_id"],
            retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
            vintage=None,
            proxy_method=None,
            transform_log=[],
        )

    def available_variables(self) -> list[str]:
        """Return list of available variable names."""
        return list(self.AVAILABLE_VARIABLES.keys())
