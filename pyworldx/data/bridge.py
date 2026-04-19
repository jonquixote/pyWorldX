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

import logging
import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


class DataBridgeError(Exception):
    """Raised when the aligned data store is missing or malformed.

    Use this instead of letting raw FileNotFoundError propagate, so callers
    can catch a single exception type for all DataBridge failures.
    """


# ── World3 Layer-0 Namespace ─────────────────────────────────────────
# World3 reference trajectories must NEVER appear in ENTITY_TO_ENGINE_MAP.
# They are structural references only (Layer 0), not empirical targets.
# Mapping them alongside real data creates circular calibration.

WORLD3_NAMESPACE: dict[str, dict[str, Any]] = {
    "world3.population": {
        "source_id": "world3_reference_population",
        "unit": "persons",
        "layer": 0,
        "description": "World3-03 Standard Run reference population trajectory",
    },
    "world3.industrial_output": {
        "source_id": "world3_reference_industrial_output",
        "unit": "industrial_output_units",
        "layer": 0,
        "description": "World3-03 industrial output — NOT GDP",
    },
    "world3.food_per_capita": {
        "source_id": "world3_reference_food_per_capita",
        "unit": "veg_equiv_kg_per_person_yr",
        "layer": 0,
        "description": "World3-03 food per capita in vegetable-equivalent kg — NOT kcal",
    },
    "world3.nr_fraction": {
        "source_id": "world3_reference_nr_fraction_remaining",
        "unit": "dimensionless",
        "layer": 0,
        "description": "World3-03 NR fraction remaining — circular if used as calibration target",
    },
    "world3.pollution_index": {
        "source_id": "world3_reference_pollution_index",
        "unit": "dimensionless",
        "layer": 0,
        "description": "World3-03 dimensionless pollution index — NOT ppm CO2",
    },
    "world3.life_expectancy": {
        "source_id": "world3_reference_life_expectancy",
        "unit": "years",
        "layer": 0,
        "description": "World3-03 life expectancy reference",
    },
    "world3.human_welfare_index": {
        "source_id": "world3_reference_human_welfare_index",
        "unit": "dimensionless",
        "layer": 0,
        "description": "World3-03 human welfare index reference",
    },
    "world3.ecological_footprint": {
        "source_id": "world3_reference_ecological_footprint",
        "unit": "dimensionless",
        "layer": 0,
        "description": "World3-03 ecological footprint reference",
    },
}


# ── Entity-to-Engine mapping (rich dict format) ───────────────────────
#
# Each entry is a dict with at minimum:
#   engine_var: str           — the engine trajectory key
#   unit: str                 — pipeline unit of the empirical series
# Optional keys:
#   source_priority: list     — ordered list of preferred source IDs
#   unit_mismatch: bool       — True means excluded from default objective
#   excluded_from_objective: bool
#
# Rule: world3_reference_* keys must NEVER appear here.
# Rule: multi-source entities (SC, IC, AL) MUST have source_priority.

ENTITY_TO_ENGINE_MAP: dict[str, dict[str, Any]] = {
    # ── Population ─────────────────────────────────────────────
    "population.total": {
        "engine_var": "POP",
        "unit": "persons",
        "nrmsd_method": "direct",
    },

    # ── Industrial Capital (multi-source → deterministic priority) ──
    "industrial_capital": {
        "engine_var": "IC",
        "unit": "constant_2017_USD",
        "nrmsd_method": "change_rate",
        "source_priority": [
            "penn_world_table",
            "world_bank_capital_stock",
            "unido",
        ],
        "description": "PWT rnna is authoritative; WB and UNIDO are fallbacks",
    },
    "capital.industrial_stock": {
        "engine_var": "IC",
        "unit": "constant_2017_USD",
        "nrmsd_method": "change_rate",
    },

    # ── Service Capital (multi-source → deterministic priority) ────
    "service_capital": {
        "engine_var": "SC",
        "unit": "constant_2017_USD_PPP",
        "nrmsd_method": "change_rate",
        "source_priority": [
            "penn_world_table",
            "world_bank_capital_stock",
            "gapminder_gdp_per_capita",
        ],
        "description": "PWT rgdpe per capita is authoritative; others are fallbacks",
    },
    "gdp.current_usd": {
        "engine_var": "industrial_output",
        "unit": "current_USD",
        "nrmsd_method": "change_rate",
    },
    "gdp.per_capita": {
        "engine_var": "industrial_output_per_capita",
        "unit": "constant_2015_USD_per_capita",
        "nrmsd_method": "change_rate",
    },

    # ── Agriculture (multi-source land, single-source food) ────────
    "arable_land": {
        "engine_var": "AL",
        "unit": "hectares",
        "nrmsd_method": "direct",
        "source_priority": [
            "faostat_rl",
            "world_bank_land",
        ],
        "description": "FAOSTAT RL is authoritative; World Bank land is fallback",
    },
    "land.arable_hectares": {
        "engine_var": "AL",
        "unit": "hectares",
        "nrmsd_method": "direct",
    },

    # ── Food Per Capita — FAOSTAT is the SOLE empirical source ─────
    # world3_reference_food_per_capita is EXCLUDED (kg vs kcal collision).
    "food_per_capita": {
        "engine_var": "food_per_capita",
        "unit": "kcal_per_capita_per_day",
        "nrmsd_method": "change_rate",
        "description": "Sourced exclusively from FAOSTAT FBS/FBSH. World3 reference excluded.",
    },
    "food.supply.kcal_per_capita": {
        "engine_var": "food_per_capita",
        "unit": "kcal_per_capita_per_day",
        "nrmsd_method": "change_rate",
    },

    # ── Pollution ──────────────────────────────────────────────────
    # pollution_index_relative: dimensionless PPOLX — THIS is in the objective
    "pollution_index_relative": {
        "engine_var": "PPOLX",
        "unit": "dimensionless",
        "nrmsd_method": "change_rate",
        "description": "Dimensionless persistent pollution index.",
    },
    # atmospheric_co2_ppm: excluded from default objective until ppm→index conversion exists
    "atmospheric_co2_ppm": {
        "engine_var": "C_atm_ppm",
        "unit": "ppm",
        "nrmsd_method": "direct",
        "unit_mismatch": True,
        "excluded_from_objective": True,
        "description": (
            "NOAA atmospheric CO2 in ppm. Excluded from default objective: "
            "unit_mismatch with dimensionless PPOLX. Add ppm→index conversion before enabling."
        ),
    },
    "emissions.co2_fossil": {
        "engine_var": "pollution_generation",
        "unit": "Mt_CO2",
        "nrmsd_method": "change_rate",
    },

    # ── Welfare & Development ──────────────────────────────────────
    "hdi.human_development_index": {
        "engine_var": "human_welfare_index",
        "unit": "dimensionless",
        "nrmsd_method": "direct",
    },

    # ── Resources — BP proved reserves is the empirical anchor ─────
    # world3_reference_nr_fraction_remaining is EXCLUDED (circular).
    "resources.nonrenewable_stock": {
        "engine_var": "NR",
        "unit": "resource_units",
        "nrmsd_method": "change_rate",
    },

    # ── USGS Layer 3 cross-validation proxies ──────────────────────
    "resources.extraction_index": {
        "engine_var": "resource_extraction_index",
        "unit": "index_1996_eq_100",
        "nrmsd_method": "change_rate",
    },
    "resources.depletion_ratio": {
        "engine_var": "reserve_depletion_ratio",
        "unit": "dimensionless",
        "nrmsd_method": "change_rate",
    },

    # ── Phase 2: Carbon cycle ──────────────────────────────────────
    "carbon.atmospheric_gtc": {"engine_var": "C_atm", "unit": "GtC", "nrmsd_method": "direct"},
    "carbon.land_gtc": {"engine_var": "C_land", "unit": "GtC", "nrmsd_method": "direct"},
    "carbon.soil_gtc": {"engine_var": "C_soc", "unit": "GtC", "nrmsd_method": "direct"},
    "carbon.ocean_surface_gtc": {"engine_var": "C_ocean_surf", "unit": "GtC", "nrmsd_method": "direct"},
    "carbon.ocean_deep_gtc": {"engine_var": "C_ocean_deep", "unit": "GtC", "nrmsd_method": "direct"},

    # ── Phase 2: Cross-sector coupling signals ─────────────────────
    "finance.resilience": {"engine_var": "financial_resilience", "unit": "dimensionless", "nrmsd_method": "direct"},
    "minerals.tech_metals_availability": {"engine_var": "tech_metals_availability", "unit": "dimensionless", "nrmsd_method": "direct"},
    "climate.temperature_anomaly": {"engine_var": "temperature_anomaly", "unit": "degC", "nrmsd_method": "direct"},
    "epidemiology.labor_force_multiplier": {"engine_var": "labor_force_multiplier", "unit": "dimensionless", "nrmsd_method": "direct"},
    "energy.supply_factor": {"engine_var": "energy_supply_factor", "unit": "dimensionless", "nrmsd_method": "direct"},
}


# ── Legacy engine_var lookup (backward compat for old code) ──────────
def _get_engine_var(entity: str) -> str | None:
    """Return the engine variable for an entity, from either old or new map format."""
    entry = ENTITY_TO_ENGINE_MAP.get(entity)
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry
    return entry.get("engine_var")


# ── NRMSD method per engine var (derived from the rich map above) ─────
NRMSD_METHOD: dict[str, str] = {}
for _entity, _entry in ENTITY_TO_ENGINE_MAP.items():
    if isinstance(_entry, dict):
        _ev = _entry.get("engine_var")
        _method = _entry.get("nrmsd_method", "direct")
        if _ev:
            NRMSD_METHOD[_ev] = _method


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

    Supports two constructor call styles:
      # New style (preflight plan contracts):
      bridge = DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())
      # Legacy style (backward compat):
      bridge = DataBridge(normalize=True)
    """

    # Class-level cache TTL (days). Files older than this trigger a WARNING.
    cache_ttl: int = 30

    def __init__(
        self,
        reference_year: Optional[int] = None,
        normalize: bool = True,
        entity_map: Optional[dict[str, Any]] = None,
        # New-style kwargs
        aligned_dir: Optional[Path] = None,
        config: Any = None,
    ) -> None:
        self.normalize = normalize
        self.entity_map = entity_map or ENTITY_TO_ENGINE_MAP
        # New-style: aligned_dir and config override reference_year
        self._aligned_dir = aligned_dir
        self._config = config
        if config is not None:
            self.reference_year = int(config.train_start)
        elif reference_year is not None:
            self.reference_year = reference_year
        else:
            from pyworldx.calibration.metrics import CrossValidationConfig
            self.reference_year = CrossValidationConfig.train_start

    def load_targets(
        self,
        aligned_dir: Optional[Path] = None,
        weights: Optional[dict[str, float]] = None,
        sector: Optional[str] = None,
    ) -> list["CalibrationTarget"]:
        """Load aligned Parquet data as calibration targets.

        Supports both new-style (no positional args when aligned_dir set in __init__)
        and legacy-style (aligned_dir as first positional arg).

        Args:
            aligned_dir: Path to aligned Parquet store.  If None, uses self._aligned_dir.
            weights: Optional per-variable weights (default: equal).
            sector: If provided, only load targets for that sector.

        Raises:
            DataBridgeError: if any required Parquet file is missing.

        Returns:
            List of CalibrationTarget objects.
        """
        resolved_dir = aligned_dir or self._aligned_dir
        if resolved_dir is None:
            raise DataBridgeError(
                "No aligned_dir provided. Pass it to DataBridge() or to load_targets()."
                " Run: python -m data_pipeline --align"
            )

        # Check the dir itself exists
        resolved_dir = Path(resolved_dir)

        try:
            from data_pipeline.storage.parquet_store import read_aligned
        except (ImportError, ModuleNotFoundError):
            read_aligned = None  # type: ignore[assignment]

        # Staleness and existence check
        now = time.time()
        ttl_secs = self.cache_ttl * 86400
        missing_entities: list[str] = []

        for entity in self.entity_map:
            safe_name = entity.replace(".", "_")
            candidates = list(resolved_dir.glob(f"{safe_name}*.parquet"))
            # Also try without sub-suffix
            direct = resolved_dir / f"{safe_name}.parquet"
            if direct.exists():
                candidates = [direct]

            if not candidates:
                missing_entities.append(entity)
                continue

            for p in candidates:
                age_secs = now - p.stat().st_mtime
                if age_secs > ttl_secs:
                    age_days = age_secs / 86400
                    logger.warning(
                        "Stale Parquet cache for '%s': %.0f days old (ttl=%d). "
                        "Refresh: python -m data_pipeline.connectors.%s",
                        entity, age_days, self.cache_ttl, entity.replace(".", "_"),
                    )

        if missing_entities:
            first = missing_entities[0]
            connector_name = first.replace(".", "_")
            raise DataBridgeError(
                f"Parquet cache missing for '{first}'. "
                f"Run: python -m data_pipeline.connectors.{connector_name}"
            )

        if read_aligned is None:
            return []

        targets: list[CalibrationTarget] = []

        for entity, entry in self.entity_map.items():
            if isinstance(entry, dict):
                engine_var = entry.get("engine_var", "")
                excluded = entry.get("excluded_from_objective", False)
            else:
                engine_var = str(entry)
                excluded = False

            if excluded:
                continue

            safe_name = entity.replace(".", "_")
            df = read_aligned(safe_name, resolved_dir)

            if df is None or df.empty:
                continue

            # Filter to world aggregate
            if "country_code" in df.columns:
                df = df[df["country_code"].isin(["WLD", "World", "5000"])]

            if df.empty:
                continue

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

            df = df.sort_values(year_col).drop_duplicates(subset=[year_col], keep="last")
            years = df[year_col].values.astype(int)
            values = df[value_col].values.astype(float)

            valid = np.isfinite(values)
            years = years[valid]
            values = values[valid]

            if len(years) < 3:
                continue

            if isinstance(entry, dict):
                method = entry.get("nrmsd_method", NRMSD_METHOD.get(engine_var, "direct"))
            else:
                method = NRMSD_METHOD.get(engine_var, "direct")
            weight = (weights or {}).get(engine_var, 1.0)

            unit = "unknown"
            if "unit" in df.columns:
                unit_vals = df["unit"].dropna()
                if len(unit_vals) > 0:
                    unit = str(unit_vals.iloc[0])

            logger.info(
                "DataBridge: loaded '%s' -> engine var '%s' (%d points)",
                entity, engine_var, len(years),
            )

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

    def _normalize_to_index(
        self,
        series: "pd.Series[float]",
        base_year: int,
    ) -> "pd.Series[float]":
        """Normalize series so that series[base_year] == 1.0.

        Zero-guard: if series[base_year] is 0 or NaN, falls back to the
        first non-zero value within ±5 years of base_year, emitting a
        WARNING. Raises DataBridgeError if no non-zero fallback exists.

        Args:
            series: Year-indexed pd.Series.
            base_year: The reference year (must be CrossValidationConfig.train_start).

        Returns:
            Normalized pd.Series (same index as input).

        Raises:
            DataBridgeError: if no non-zero base value can be found near base_year.
        """
        import pandas as pd

        base_val: float | None = None

        # Try exact match
        if base_year in series.index:
            v = float(series[base_year])
            if np.isfinite(v) and v != 0.0:
                base_val = v

        # Fallback: search ±5 years
        if base_val is None:
            for delta in range(1, 6):
                for candidate in [base_year + delta, base_year - delta]:
                    if candidate in series.index:
                        v = float(series[candidate])
                        if np.isfinite(v) and v != 0.0:
                            base_val = v
                            logger.warning(
                                "_normalize_to_index: base_year=%d has zero/NaN value; "
                                "falling back to year=%d (delta=%d).",
                                base_year, candidate, delta,
                            )
                            break
                if base_val is not None:
                    break

        if base_val is None:
            raise DataBridgeError(
                f"no non-zero base value near {base_year} in series "
                f"(searched ±5 years). All values are zero or NaN."
            )

        result = series / base_val
        # Ensure no inf/NaN introduced by normalisation itself
        result = result.replace([np.inf, -np.inf], np.nan)
        return result


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
            entry = self.entity_map.get(entity)
            if entry is None:
                continue

            if isinstance(entry, dict):
                engine_var = entry.get("engine_var", "")
                if not engine_var or entry.get("excluded_from_objective", False):
                    continue
            else:
                engine_var = str(entry)
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

    def _clip_targets_to_window(
        self,
        targets: list[CalibrationTarget],
        start_year: int,
        end_year: int,
    ) -> list[CalibrationTarget]:
        """Return targets with years clipped to [start_year, end_year].

        Targets with fewer than 3 points after clipping are dropped.
        """
        clipped: list[CalibrationTarget] = []
        for t in targets:
            mask = (t.years >= start_year) & (t.years <= end_year)
            years = t.years[mask]
            values = t.values[mask]
            if len(years) < 3:
                continue
            clipped.append(
                CalibrationTarget(
                    variable_name=t.variable_name,
                    years=years,
                    values=values,
                    unit=t.unit,
                    weight=t.weight,
                    source=t.source,
                    nrmsd_method=t.nrmsd_method,
                )
            )
        return clipped

    def build_objective(
        self,
        targets: list[CalibrationTarget],
        engine_factory: Callable[[dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]],
        train_start: Optional[int] = None,
        train_end: Optional[int] = None,
    ) -> Callable[[dict[str, float]], float]:
        """Build NRMSD objective function from targets.

        Args:
            targets: Calibration targets
            engine_factory: Callable(params) -> (trajectories, time_index)
            train_start: If provided, clip targets to years >= train_start
            train_end: If provided, clip targets to years <= train_end

        Returns:
            Callable mapping parameter dict -> scalar NRMSD.
        """
        # Pre-clip to train window (no per-call overhead)
        active_targets = targets
        if train_start is not None or train_end is not None:
            lo = train_start if train_start is not None else int(targets[0].years.min())
            hi = train_end if train_end is not None else int(targets[0].years.max())
            active_targets = self._clip_targets_to_window(targets, lo, hi)

        def objective(params: dict[str, float]) -> float:
            try:
                trajectories, time_index = engine_factory(params)
            except Exception:
                return float("inf")

            result = self.compare(active_targets, trajectories, time_index)
            return result.composite_nrmsd

        return objective

    def calculate_validation_score(
        self,
        targets: list[CalibrationTarget],
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, "np.ndarray[Any, Any]"], "np.ndarray[Any, Any]"],
        ],
        params: dict[str, float],
        validate_start: int,
        validate_end: int,
    ) -> "BridgeResult":
        """Evaluate NRMSD on the holdout validation window only.

        Args:
            targets: All calibration targets (clipped to validation years internally)
            engine_factory: Callable(params) -> (trajectories, time_index)
            params: Parameter dict to evaluate
            validate_start: First year of the holdout window (inclusive)
            validate_end: Last year of the holdout window (inclusive)

        Returns:
            BridgeResult computed on validation years only.
        """
        val_targets = self._clip_targets_to_window(targets, validate_start, validate_end)
        try:
            trajectories, time_index = engine_factory(params)
        except Exception:
            return BridgeResult(
                per_variable_nrmsd={},
                composite_nrmsd=float("nan"),
                n_targets=0,
                coverage={},
            )
        return self.compare(val_targets, trajectories, time_index)

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
