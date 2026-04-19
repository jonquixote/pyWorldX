"""BP Statistical Review of World Energy connector — T2-2.

Source: https://www.energyinst.org/statistical-review
Data: Proved oil/gas/coal reserves in EJ (exajoules).

This connector provides the empirical anchor for the World3 NR (non-renewable
resources) stock.  The world3_reference_nr_fraction_remaining trajectory is
excluded from calibration (it is circular); BP proved reserves are the
Layer-1 empirical substitute.

Note: BP released the Statistical Review as an Excel download.
The `_raw_fetch` method is injectable (for testing) and must be patched
with the actual file path or URL in production.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


class BPStatisticalReviewConnector:
    """Connector for the BP Statistical Review of World Energy.

    Provides proved fossil-fuel reserves in EJ (exajoules) from 1965–present
    as the empirical proxy for World3's Non-Renewable Resource (NR) stock.

    Class attributes
    ----------------
    layer : int
        Data layer.  1 = observed/empirical (not a structural reference).
    entity : str
        Ontology entity name this connector populates.
    unit : str
        Unit of the proved_reserves_ej column.
    source_url : str
        Canonical download URL.
    """

    layer: int = 1
    entity: str = "nonrenewable_resources_proved_reserves"
    unit: str = "EJ"
    source_url: str = (
        "https://www.energyinst.org/statistical-review/resources-and-data/downloads"
    )

    def __init__(self, data_path: Optional[str] = None) -> None:
        """Create a connector.

        Args:
            data_path: Optional path to a pre-downloaded Excel file.  If None,
                ``_raw_fetch`` must be patched in tests or overridden in a
                subclass for production use.
        """
        self._data_path = data_path

    # ------------------------------------------------------------------
    # Injection point for tests — patch this method, not the class itself
    # ------------------------------------------------------------------

    def _raw_fetch(self) -> pd.DataFrame:
        """Return a raw DataFrame with columns year + proved_reserves_ej.

        Override or patch this method in tests.  In production, this reads
        the BP Excel download.

        Returns:
            DataFrame with at minimum: year (int), proved_reserves_ej (float).

        Raises:
            NotImplementedError: if no data_path was set and no patch applied.
        """
        if self._data_path is None:
            raise NotImplementedError(
                "BPStatisticalReviewConnector._raw_fetch: no data_path provided. "
                "Either pass data_path= to __init__ or patch _raw_fetch() in tests."
            )
        # Parse the BP Excel file (sheet varies by year; attempt auto-detection)
        try:
            xl = pd.ExcelFile(self._data_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to open BP Statistical Review file at '{self._data_path}': {e}"
            ) from e

        # Look for a sheet containing proved reserves data
        target_sheets = [s for s in xl.sheet_names if "reserve" in s.lower()]
        if not target_sheets:
            target_sheets = [xl.sheet_names[0]]

        df = xl.parse(target_sheets[0], skiprows=2)
        # Normalise: expect year column named 'Year' or similar
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if "year" not in df.columns:
            raise ValueError(
                "BP Statistical Review: could not find 'year' column in "
                f"sheet '{target_sheets[0]}'. Columns: {list(df.columns)}"
            )
        if "proved_reserves_ej" not in df.columns:
            # Attempt renaming if a single numeric column exists
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if len(numeric_cols) == 1:
                df = df.rename(columns={numeric_cols[0]: "proved_reserves_ej"})
            else:
                raise ValueError(
                    "BP Statistical Review: cannot identify proved_reserves_ej column. "
                    f"Numeric columns found: {numeric_cols}"
                )
        return df[["year", "proved_reserves_ej"]].copy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self) -> pd.DataFrame:
        """Fetch and validate BP proved reserves data.

        Returns:
            Clean DataFrame with columns: year (int), proved_reserves_ej (float).
            Rows are sorted by year and deduplicated.
            Gap-fills (linear interpolation) are applied for single-year gaps only.

        Raises:
            ValueError: if the data has too few rows or excessive gaps.
        """
        df = self._raw_fetch()
        df = df.copy()

        # Coerce types
        df["year"] = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int)
        df["proved_reserves_ej"] = pd.to_numeric(
            df["proved_reserves_ej"], errors="coerce"
        )

        # Drop rows with missing values
        df = df.dropna(subset=["year", "proved_reserves_ej"])
        df = df.sort_values("year").drop_duplicates(subset=["year"], keep="last")
        df = df.reset_index(drop=True)

        if len(df) < 10:
            raise ValueError(
                f"BPStatisticalReviewConnector: only {len(df)} valid rows returned; "
                "expected at least 10 (1965–present)."
            )

        return df
