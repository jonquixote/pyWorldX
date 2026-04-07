"""FAO FAOSTAT data connector (Section 8.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from pyworldx.data.connectors.base import ConnectorResult


class FAOSTATConnector:
    """Connector for FAO FAOSTAT data."""

    SOURCE = "FAO FAOSTAT"

    AVAILABLE_VARIABLES: dict[str, dict[str, str]] = {
        "food_supply_kcal": {
            "unit": "kcal/capita/day",
            "series_id": "FAOSTAT_FBS_KCD",
            "description": "Food supply in kilocalories per capita per day",
        },
        "arable_land": {
            "unit": "hectares",
            "series_id": "FAOSTAT_RL_ARA",
            "description": "Arable land area in hectares",
        },
        "crop_yield": {
            "unit": "hg/ha",
            "series_id": "FAOSTAT_QC_YIELD",
            "description": "Crop yield in hectograms per hectare",
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
