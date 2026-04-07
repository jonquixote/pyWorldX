"""UNDP Human Development Reports data connector (Section 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from pyworldx.data.connectors.base import ConnectorResult


class UNDPHDRConnector:
    """Connector for UNDP Human Development Reports data."""

    SOURCE = "UNDP Human Development Reports"

    AVAILABLE_VARIABLES: dict[str, dict[str, str]] = {
        "hdi": {
            "unit": "index",
            "series_id": "UNDP_HDI",
            "description": "Human Development Index",
        },
        "life_expectancy_index": {
            "unit": "index",
            "series_id": "UNDP_LEI",
            "description": "Life expectancy index component of HDI",
        },
        "education_index": {
            "unit": "index",
            "series_id": "UNDP_EI",
            "description": "Education index component of HDI",
        },
        "gni_index": {
            "unit": "index",
            "series_id": "UNDP_GNI_INDEX",
            "description": "Gross national income index component of HDI",
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
