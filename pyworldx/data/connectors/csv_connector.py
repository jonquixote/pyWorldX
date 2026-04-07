"""CSV/Parquet data connector (Section 8).

Loads empirical data from local CSV or Parquet files with
caching, vintage tracking, and unit metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from pyworldx.data.connectors.base import ConnectorResult


@dataclass
class CSVConnector:
    """Load data from CSV or Parquet files.

    Attributes:
        name: connector identifier
        source_url: base directory for data files
        file_map: dict mapping variable_name -> file path (relative to source_url)
        unit_map: dict mapping variable_name -> unit string
    """

    name: str = "csv_connector"
    source_url: str = ""
    file_map: dict[str, str] = field(default_factory=dict)
    unit_map: dict[str, str] = field(default_factory=dict)
    _cache: dict[str, ConnectorResult] = field(default_factory=dict)

    def fetch(
        self,
        variable_name: str,
        vintage: str | None = None,
    ) -> ConnectorResult:
        """Fetch data from a CSV or Parquet file."""
        cache_key = f"{variable_name}:{vintage or 'latest'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if variable_name not in self.file_map:
            raise FileNotFoundError(
                f"No file mapping for variable '{variable_name}'. "
                f"Available: {list(self.file_map.keys())}"
            )

        filepath = os.path.join(self.source_url, self.file_map[variable_name])

        if filepath.endswith(".parquet"):
            df = pd.read_parquet(filepath)
        else:
            df = pd.read_csv(filepath)

        # Expect columns: 'year' (or first column) and 'value' (or second)
        if "year" in df.columns and "value" in df.columns:
            series = pd.Series(
                df["value"].values, index=df["year"].values, name=variable_name
            )
        else:
            # Use first two columns
            series = pd.Series(
                df.iloc[:, 1].values,
                index=df.iloc[:, 0].values,
                name=variable_name,
            )

        result = ConnectorResult(
            series=series,
            unit=self.unit_map.get(variable_name, "unknown"),
            source=self.name,
            source_series_id=variable_name,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            vintage=vintage,
            transform_log=["loaded_from_file"],
        )

        self._cache[cache_key] = result
        return result

    def available_variables(self) -> list[str]:
        """List all mapped variable names."""
        return list(self.file_map.keys())
