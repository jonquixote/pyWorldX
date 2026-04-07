"""NOAA Global Monitoring Laboratory / Global Carbon Project data connector (Section 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from pyworldx.data.connectors.base import ConnectorResult


class NOAACO2Connector:
    """Connector for NOAA Global Monitoring Laboratory / Global Carbon Project data."""

    SOURCE = "NOAA Global Monitoring Laboratory / Global Carbon Project"

    AVAILABLE_VARIABLES: dict[str, dict[str, str]] = {
        "atmospheric_co2": {
            "unit": "ppm",
            "series_id": "NOAA_CO2_MM",
            "description": "Atmospheric CO2 monthly mean concentration in parts per million",
        },
        "co2_growth_rate": {
            "unit": "ppm/yr",
            "series_id": "GCP_CO2_GROWTH",
            "description": "Annual CO2 growth rate in parts per million per year",
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
