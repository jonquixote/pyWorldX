"""DataBridge — connects data pipeline outputs to engine calibration.

This module bridges the gap between:
  - data_pipeline outputs (ConnectorResult / PipelineConnectorResult with
    real-world units and year-indexed pd.Series)
  - pyworldx calibration system (parameter dict -> scalar NRMSD objective)

The bridge operates via CalibrationTarget objects and normalization to
a common reference year (default 1970), so NRMSD compares trajectory
*shapes* rather than absolute magnitudes.

Architecture (from data_pipeline_integration_report.md):
  Pipeline ConnectorResult -> DataBridge -> CalibrationTarget[]
  CalibrationTarget[] + engine_factory -> objective_fn(params) -> float
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np


# ── Entity-to-Engine mapping ──────────────────────────────────────────

# Maps pipeline entity names to engine variable names.
# Keys are pipeline entity names (dot-separated), values are engine
# variable names as they appear in Engine.run().trajectories.
ENTITY_TO_ENGINE_MAP: dict[str, str] = {
    # Population & Demographics
    "population.total": "POP",

    # Industrial & Economic
    "gdp.current_usd": "industrial_output",
    "gdp.per_capita": "industrial_output_per_capita",
    "capital.industrial_stock": "IC",

    # Agriculture & Food
    "food.supply.kcal_per_capita": "food_per_capita",
    "land.arable_hectares": "AL",

    # Pollution & Climate
    "emissions.co2_fossil": "pollution_generation",
    "atmospheric.co2": "pollution_index",

    # Welfare & Development
    "hdi.human_development_index": "human_welfare_index",

    # Resources (indirect proxies)
    "resources.nonrenewable_stock": "NR",

    # USGS Layer 3 cross-validation proxies
    "resources.extraction_index": "resource_extraction_index",
    "resources.depletion_ratio": "reserve_depletion_ratio",
}

# NRMSD comparison method per variable (from Nebel 2023 conventions).
# "direct" = level-compared, "change_rate" = annual-%-change-compared.
NRMSD_METHOD: dict[str, str] = {
    "POP": "direct",
    "industrial_output": "change_rate",
    "industrial_output_per_capita": "change_rate",
    "IC": "change_rate",
    "food_per_capita": "change_rate",
    "AL": "direct",
    "pollution_generation": "change_rate",
    "pollution_index": "change_rate",
    "human_welfare_index": "direct",
    "NR": "change_rate",
    "life_expectancy": "direct",
    "service_output_per_capita": "change_rate",
    "ecological_footprint": "direct",
    "PPOL": "change_rate",
    # USGS Layer 3 proxies
    "resource_extraction_index": "change_rate",
    "reserve_depletion_ratio": "change_rate",
}


@dataclass
class CalibrationTarget:
    """A time-series target for NRMSD comparison.

    Represents one empirical observation to compare against engine output.
    The bridge produces these from pipeline ConnectorResult objects.
    """

    variable_name: str           # Engine variable (e.g., "POP")
    years: np.ndarray[Any, Any]  # Year indices (integer years)
    values: np.ndarray[Any, Any] # Observed values at those years
    unit: str                    # Unit string (for provenance)
    weight: float = 1.0          # Weight in composite NRMSD
    source: str = ""             # Provenance description
    nrmsd_method: str = "direct" # "direct" or "change_rate"


@dataclass
class BridgeResult:
    """Result of a DataBridge comparison."""

    per_variable_nrmsd: dict[str, float]
    composite_nrmsd: float
    n_targets: int
    coverage: dict[str, tuple[int, int]]  # variable -> (start_year, end_year)


class DataBridge:
    """Connects data pipeline outputs to engine calibration.

    Usage:
        bridge = DataBridge()
        targets = bridge.load_targets(aligned_dir, ENTITY_TO_ENGINE_MAP)
        objective = bridge.build_objective(targets, engine_factory)
        score = objective({"resources.initial_nr": 1e12, ...})
    """

    def __init__(
        self,
        reference_year: int = 1970,
        normalize: bool = True,
        entity_map: Optional[dict[str, str]] = None,
    ) -> None:
        self.reference_year = reference_year
        self.normalize = normalize
        self.entity_map = entity_map or ENTITY_TO_ENGINE_MAP

    def load_targets(
        self,
        aligned_dir: Path,
        weights: Optional[dict[str, float]] = None,
    ) -> list[CalibrationTarget]:
        """Load aligned Parquet data as calibration targets.

        Reads each mapped entity from the aligned store, builds a
        CalibrationTarget with year-indexed values and NRMSD method.

        Args:
            aligned_dir: Path to data_pipeline/data/aligned/
            weights: Optional per-variable weights (default: equal)

        Returns:
            List of CalibrationTarget objects.
        """
        try:
            from data_pipeline.storage.parquet_store import read_aligned
        except (ImportError, ModuleNotFoundError):
            # Pipeline extras (duckdb, pyarrow) not installed
            return []

        targets: list[CalibrationTarget] = []

        for entity, engine_var in self.entity_map.items():
            safe_name = entity.replace(".", "_")
            df = read_aligned(safe_name, aligned_dir)

            if df is None or df.empty:
                continue

            # Filter to world aggregate
            if "country_code" in df.columns:
                df = df[df["country_code"].isin(["WLD", "World", "5000"])]

            if df.empty:
                continue

            # Extract year and value
            year_col = "year" if "year" in df.columns else None
            if year_col is None:
                continue

            value_col = "value"
            if value_col not in df.columns:
                numeric_idx = df.select_dtypes(include=["number"]).columns
                col_names = [c for c in numeric_idx if c != year_col]
                if not col_names:
                    continue
                value_col = col_names[0]

            # Sort and deduplicate
            df = df.sort_values(year_col).drop_duplicates(subset=[year_col], keep="last")

            years = df[year_col].values.astype(int)
            values = df[value_col].values.astype(float)

            # Remove NaN
            valid = np.isfinite(values)
            years = years[valid]
            values = values[valid]

            if len(years) < 3:
                continue

            # Determine NRMSD method
            method = NRMSD_METHOD.get(engine_var, "direct")
            weight = (weights or {}).get(engine_var, 1.0)

            # Determine unit
            unit = "unknown"
            if "unit" in df.columns:
                unit_vals = df["unit"].dropna()
                if len(unit_vals) > 0:
                    unit = str(unit_vals.iloc[0])

            targets.append(CalibrationTarget(
                variable_name=engine_var,
                years=np.asarray(years, dtype=int),
                values=np.asarray(values, dtype=float),
                unit=unit,
                weight=weight,
                source=f"pipeline:{entity}",
                nrmsd_method=method,
            ))

        return targets

    def load_targets_from_results(
        self,
        results: dict[str, Any],
        weights: Optional[dict[str, float]] = None,
    ) -> list[CalibrationTarget]:
        """Load targets from PipelineConnectorResult dict.

        Args:
            results: Dict mapping entity name to PipelineConnectorResult
            weights: Optional per-variable weights

        Returns:
            List of CalibrationTarget objects.
        """
        targets: list[CalibrationTarget] = []

        for entity, result in results.items():
            engine_var = self.entity_map.get(entity)
            if engine_var is None:
                continue

            series = result.series
            if series is None or series.empty:
                continue

            years = np.array(series.index, dtype=int)
            values = np.array(series.values, dtype=float)

            valid = np.isfinite(values)
            years = years[valid]
            values = values[valid]

            if len(years) < 3:
                continue

            method = NRMSD_METHOD.get(engine_var, "direct")
            weight = (weights or {}).get(engine_var, 1.0)

            targets.append(CalibrationTarget(
                variable_name=engine_var,
                years=np.asarray(years, dtype=int),
                values=np.asarray(values, dtype=float),
                unit=result.unit,
                weight=weight,
                source=f"pipeline:{entity}",
                nrmsd_method=method,
            ))

        return targets

    def compare(
        self,
        targets: list[CalibrationTarget],
        engine_trajectories: dict[str, np.ndarray[Any, Any]],
        engine_time: np.ndarray[Any, Any],
    ) -> BridgeResult:
        """Compare engine trajectories against calibration targets.

        Both engine and observed data are normalized to reference_year
        baseline if self.normalize is True, then NRMSD is computed.

        Args:
            targets: Calibration targets from load_targets()
            engine_trajectories: Engine.run().trajectories dict
            engine_time: Engine.run().time_index (absolute years)

        Returns:
            BridgeResult with per-variable and composite NRMSD.
        """
        per_var: dict[str, float] = {}
        coverage: dict[str, tuple[int, int]] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for target in targets:
            if target.variable_name not in engine_trajectories:
                continue

            engine_traj = engine_trajectories[target.variable_name]

            # Interpolate engine to target years
            engine_at_years = np.interp(
                target.years.astype(float),
                engine_time.astype(float),
                engine_traj,
            )
            obs_values = target.values

            if self.normalize:
                # Normalize both to reference year
                engine_at_years, obs_values = self._normalize_pair(
                    engine_at_years, obs_values,
                    target.years, engine_traj, engine_time,
                )

            # Compute NRMSD
            nrmsd = self._compute_nrmsd(
                engine_at_years, obs_values, target.nrmsd_method,
            )

            if np.isfinite(nrmsd):
                per_var[target.variable_name] = nrmsd
                coverage[target.variable_name] = (
                    int(target.years[0]), int(target.years[-1])
                )
                weighted_sum += target.weight * nrmsd
                total_weight += target.weight

        composite = weighted_sum / total_weight if total_weight > 0 else float("nan")

        return BridgeResult(
            per_variable_nrmsd=per_var,
            composite_nrmsd=composite,
            n_targets=len(per_var),
            coverage=coverage,
        )

    def build_objective(
        self,
        targets: list[CalibrationTarget],
        engine_factory: Callable[[dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]],
    ) -> Callable[[dict[str, float]], float]:
        """Build NRMSD objective function from targets.

        Args:
            targets: Calibration targets
            engine_factory: Callable that takes parameter dict and returns
                (trajectories_dict, time_index) tuple. This runs the engine
                with the given parameters.

        Returns:
            Callable that maps parameter dict -> scalar NRMSD.
        """

        def objective(params: dict[str, float]) -> float:
            try:
                trajectories, time_index = engine_factory(params)
            except Exception:
                return float("inf")

            result = self.compare(targets, trajectories, time_index)
            return result.composite_nrmsd

        return objective

    def _normalize_pair(
        self,
        engine_at_years: np.ndarray[Any, Any],
        obs_values: np.ndarray[Any, Any],
        obs_years: np.ndarray[Any, Any],
        full_engine_traj: np.ndarray[Any, Any],
        full_engine_time: np.ndarray[Any, Any],
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """Normalize both series to reference year baseline."""
        # Engine value at reference year
        engine_ref = float(np.interp(
            self.reference_year, full_engine_time.astype(float), full_engine_traj,
        ))

        # Observed value at reference year (interpolated)
        obs_ref = float(np.interp(
            self.reference_year, obs_years.astype(float), obs_values,
        ))

        # Avoid division by zero
        if abs(engine_ref) < 1e-15:
            engine_ref = 1.0
        if abs(obs_ref) < 1e-15:
            obs_ref = 1.0

        return engine_at_years / engine_ref, obs_values / obs_ref

    @staticmethod
    def _compute_nrmsd(
        model: np.ndarray[Any, Any],
        reference: np.ndarray[Any, Any],
        method: str,
    ) -> float:
        """Compute NRMSD using the specified method."""
        if len(model) == 0 or len(reference) == 0:
            return float("nan")

        if method == "change_rate" and len(model) >= 2:
            # Annual percent change
            model_pct = np.diff(model) / np.where(
                np.abs(model[:-1]) > 1e-15, model[:-1], 1.0
            ) * 100.0
            ref_pct = np.diff(reference) / np.where(
                np.abs(reference[:-1]) > 1e-15, reference[:-1], 1.0
            ) * 100.0

            valid = np.isfinite(model_pct) & np.isfinite(ref_pct)
            if not valid.any():
                return float("nan")
            model_pct = model_pct[valid]
            ref_pct = ref_pct[valid]

            mean_ref = np.mean(np.abs(ref_pct))
            if mean_ref < 1e-10:
                return float("nan")
            return float(np.sqrt(np.mean((model_pct - ref_pct) ** 2)) / mean_ref)

        # Direct method
        mean_ref = np.mean(np.abs(reference))
        if mean_ref < 1e-15:
            return float("nan")
        return float(np.sqrt(np.mean((model - reference) ** 2)) / mean_ref)
