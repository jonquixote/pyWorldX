"""Our World in Data data connector (Section 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from pyworldx.data.connectors.base import ConnectorResult


class OWIDConnector:
    """Connector for Our World in Data data."""

    SOURCE = "Our World in Data"

    AVAILABLE_VARIABLES: dict[str, dict[str, str]] = {
        "primary_energy": {
            "unit": "TWh",
            "series_id": "OWID_ENERGY_PRIMARY",
            "description": "Primary energy consumption in terawatt-hours",
        },
        "fossil_fuel_consumption": {
            "unit": "TWh",
            "series_id": "OWID_FOSSIL_FUEL",
            "description": "Fossil fuel consumption in terawatt-hours",
        },
        "cumulative_co2": {
            "unit": "tonnes",
            "series_id": "OWID_CO2_CUMULATIVE",
            "description": "Cumulative CO2 emissions in tonnes",
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
