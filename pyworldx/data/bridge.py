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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypedDict

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


class DataBridgeError(Exception):
    """Raised when the aligned data store is missing or malformed.

    Use this instead of letting raw FileNotFoundError propagate, so callers
    can catch a single exception type for all DataBridge failures.
    """


# ── Fallback window for _normalize_to_index ──────────────────────────
# The ±N-year search window when the exact base_year value is zero/NaN.
# Changing this requires a separate PR and test updates.
_NORMALIZE_FALLBACK_WINDOW_YEARS: int = 5


class EntityMapEntry(TypedDict, total=False):
    """Typed structure for entries in ENTITY_TO_ENGINE_MAP."""

    engine_var: str
    unit: str
    nrmsd_method: str
    source_priority: list[str]
    unit_mismatch: bool
    excluded_from_objective: bool
    description: str


# ── World3 Layer-0 Namespace ─────────────────────────────────────────
# Keys in this namespace are structural references excluded from the
# calibration objective. They are NOT targets.
#
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
# Each entry is an EntityMapEntry TypedDict with at minimum:
#   engine_var: str           — the engine trajectory key
#   unit: str                 — pipeline unit of the empirical series
# Optional keys:
#   source_priority: list     — ordered list of preferred source IDs
#   unit_mismatch: bool       — True means excluded from default objective
#   excluded_from_objective: bool
#
# Rule: world3_reference_* keys must NEVER appear here.
# Rule: multi-source entities (SC, IC, AL) MUST have source_priority.
ENTITY_TO_ENGINE_MAP: dict[str, EntityMapEntry] = {
    "population.total": {
        "engine_var": "POP",
        "unit": "persons",
        "nrmsd_method": "direct",
    },
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
    "pollution_index_relative": {
        "engine_var": "PPOLX",
        "unit": "dimensionless",
        "nrmsd_method": "change_rate",
        "description": "Dimensionless persistent pollution index.",
    },
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
    "hdi.human_development_index": {
        "engine_var": "human_welfare_index",
        "unit": "dimensionless",
        "nrmsd_method": "direct",
    },
    "resources.nonrenewable_stock": {
        "engine_var": "NR",
        "unit": "resource_units",
        "nrmsd_method": "change_rate",
    },
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
    "carbon.atmospheric_gtc": {
        "engine_var": "C_atm",
        "unit": "GtC",
        "nrmsd_method": "direct",
    },
    "carbon.land_gtc": {
        "engine_var": "C_land",
        "unit": "GtC",
        "nrmsd_method": "direct",
    },
    "carbon.soil_gtc": {
        "engine_var": "C_soc",
        "unit": "GtC",
        "nrmsd_method": "direct",
    },
    "carbon.ocean_surface_gtc": {
        "engine_var": "C_ocean_surf",
        "unit": "GtC",
        "nrmsd_method": "direct",
    },
    "carbon.ocean_deep_gtc": {
        "engine_var": "C_ocean_deep",
        "unit": "GtC",
        "nrmsd_method": "direct",
    },
    "finance.resilience": {
        "engine_var": "financial_resilience",
        "unit": "dimensionless",
        "nrmsd_method": "direct",
    },
    "minerals.tech_metals_availability": {
        "engine_var": "tech_metals_availability",
        "unit": "dimensionless",
        "nrmsd_method": "direct",
    },
    "climate.temperature_anomaly": {
        "engine_var": "temperature_anomaly",
        "unit": "degC",
        "nrmsd_method": "direct",
    },
    "epidemiology.labor_force_multiplier": {
        "engine_var": "labor_force_multiplier",
        "unit": "dimensionless",
        "nrmsd_method": "direct",
    },
    "energy.supply_factor": {
        "engine_var": "energy_supply_factor",
        "unit": "dimensionless",
        "nrmsd_method": "direct",
    },
}


def _get_engine_var(entity: str) -> str | None:
    """Return the engine variable for an entity."""
    entry = ENTITY_TO_ENGINE_MAP.get(entity)
    if entry is None:
        return None
    return entry.get("engine_var")


NRMSD_METHOD: dict[str, str] = {}
for _entity, _entry in ENTITY_TO_ENGINE_MAP.items():
    _ev = _entry.get("engine_var")
    _method = _entry.get("nrmsd_method", "direct")
    if _ev:
        NRMSD_METHOD[_ev] = _method


@dataclass
class CalibrationTarget:
    """A time-series target for NRMSD comparison."""

    variable_name: str
    years: np.ndarray[Any, Any]
    values: np.ndarray[Any, Any]
    unit: str
    weight: float = 1.0
    source: str = ""
    nrmsd_method: str = "direct"


@dataclass
class BridgeResult:
    """Result of a DataBridge comparison."""

    per_variable_nrmsd: dict[str, float]
    composite_nrmsd: float
    n_targets: int
    coverage: dict[str, tuple[int, int]]


class DataBridge:
    """Connects data pipeline outputs to engine calibration."""

    cache_ttl: int = 30

    def __init__(
        self,
        reference_year: Optional[int] = None,
        normalize: bool = True,
        entity_map: Optional[dict[str, EntityMapEntry]] = None,
        aligned_dir: Optional[Path] = None,
        config: Any = None,
    ) -> None:
        self.normalize = normalize
        self.entity_map = entity_map or ENTITY_TO_ENGINE_MAP
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
    ) -> list[CalibrationTarget]:
        """Load aligned Parquet data as calibration targets."""
        resolved_dir = aligned_dir or self._aligned_dir
        if resolved_dir is None:
            raise DataBridgeError(
                "No aligned_dir provided. Pass it to DataBridge() or to load_targets(). "
                "Run: python -m data_pipeline --align"
            )

        resolved_dir = Path(resolved_dir)
        if not resolved_dir.is_dir():
            raise DataBridgeError(
                f"Aligned directory does not exist: '{resolved_dir}'. "
                "Run: python -m data_pipeline --align"
            )

        try:
            from data_pipeline.storage.parquet_store import read_aligned
        except (ImportError, ModuleNotFoundError):
            read_aligned = None  # type: ignore[assignment]

        now = time.time()
        ttl_secs = self.cache_ttl * 86400
        missing_entities: list[str] = []

        for entity in self.entity_map:
            safe_name = entity.replace(".", "_")
            candidates = list(resolved_dir.glob(f"{safe_name}*.parquet"))
            direct = resolved_dir / f"{safe_name}.parquet"
            if direct.exists():
                candidates = [direct]

            if not candidates:
                missing_entities.append(entity)
                continue

            for path in candidates:
                age_secs = now - path.stat().st_mtime
                if age_secs > ttl_secs:
                    age_days = age_secs / 86400
                    logger.warning(
                        "Stale Parquet cache for '%s': %.0f days old (ttl=%d). "
                        "Refresh: python -m data_pipeline.connectors.%s",
                        entity,
                        age_days,
                        self.cache_ttl,
                        entity.replace(".", "_"),
                    )

        if missing_entities:
            logger.warning(
                "DataBridge: %d entity/entities have no direct Parquet file: %s. "
                "These will be skipped unless covered by source_priority waterfall. "
                "Run: python -m data_pipeline run",
                len(missing_entities),
                ", ".join(missing_entities[:5])
                + ("..." if len(missing_entities) > 5 else ""),
            )

        if read_aligned is None:
            return []

        targets: list[CalibrationTarget] = []

        for entity, entry in self.entity_map.items():
            engine_var = entry.get("engine_var", "")
            excluded = entry.get("excluded_from_objective", False)
            source_priority = entry.get("source_priority", [])

            if excluded:
                continue

            safe_name = entity.replace(".", "_")
            df = None

            if source_priority:
                for idx, source_id in enumerate(source_priority):
                    candidate_name = source_id.replace(".", "_")
                    candidate_df = read_aligned(candidate_name, resolved_dir)
                    if candidate_df is not None and not candidate_df.empty:
                        if idx == 0:
                            logger.info(
                                "DataBridge: '%s' -> using primary source '%s'",
                                entity,
                                source_id,
                            )
                        else:
                            logger.info(
                                "DataBridge: '%s' -> fell back to source '%s' "
                                "(priority %d; earlier sources unavailable)",
                                entity,
                                source_id,
                                idx,
                            )
                        df = candidate_df
                        break

                if df is None:
                    logger.warning(
                        "DataBridge: '%s' -> all %d sources in source_priority exhausted; "
                        "falling back to entity name '%s'",
                        entity,
                        len(source_priority),
                        safe_name,
                    )

            if df is None:
                df = read_aligned(safe_name, resolved_dir)

            if df is None or df.empty:
                continue

            if sector is not None and entry.get("engine_var") != sector:
                pass

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

            method = entry.get("nrmsd_method", NRMSD_METHOD.get(engine_var, "direct"))
            weight = (weights or {}).get(engine_var, 1.0)

            unit = "unknown"
            if "unit" in df.columns:
                unit_vals = df["unit"].dropna()
                if len(unit_vals) > 0:
                    unit = str(unit_vals.iloc[0])

            logger.info(
                "DataBridge: loaded '%s' -> engine var '%s' (%d points)",
                entity,
                engine_var,
                len(years),
            )

            targets.append(
                CalibrationTarget(
                    variable_name=engine_var,
                    years=np.asarray(years, dtype=int),
                    values=np.asarray(values, dtype=float),
                    unit=unit,
                    weight=weight,
                    source=f"pipeline:{entity}",
                    nrmsd_method=method,
                )
            )

        return targets

    def _normalize_to_index(
        self,
        series: pd.Series[float],
        base_year: int,
    ) -> pd.Series[float]:
        """Normalize series so that series[base_year] == 1.0.

        Zero-guard: if series[base_year] is 0 or NaN, falls back to the
        first non-zero value within ±_NORMALIZE_FALLBACK_WINDOW_YEARS years
        of base_year, emitting a WARNING. Raises DataBridgeError if no
        non-zero fallback exists.
        """
        base_val: float | None = None

        if base_year in series.index:
            exact_value = float(series[base_year])
            if np.isfinite(exact_value) and exact_value != 0.0:
                base_val = exact_value

        if base_val is None:
            for delta in range(1, _NORMALIZE_FALLBACK_WINDOW_YEARS + 1):
                for candidate in (base_year + delta, base_year - delta):
                    if candidate in series.index:
                        candidate_value = float(series[candidate])
                        if np.isfinite(candidate_value) and candidate_value != 0.0:
                            base_val = candidate_value
                            logger.warning(
                                "_normalize_to_index: base_year=%d has zero/NaN value; "
                                "falling back to year=%d (delta=%d).",
                                base_year,
                                candidate,
                                delta,
                            )
                            break
                if base_val is not None:
                    break

        if base_val is None:
            raise DataBridgeError(
                f"no non-zero base value near {base_year} in series "
                f"(searched ±{_NORMALIZE_FALLBACK_WINDOW_YEARS} years). "
                "All values are zero or NaN."
            )

        result = series / base_val
        result = result.replace([np.inf, -np.inf], np.nan)
        return result

    def load_targets_from_results(
        self,
        results: dict[str, Any],
        weights: Optional[dict[str, float]] = None,
    ) -> list[CalibrationTarget]:
        """Load targets from PipelineConnectorResult dict."""
        targets: list[CalibrationTarget] = []

        for entity, result in results.items():
            entry = self.entity_map.get(entity)
            if entry is None:
                continue

            engine_var = entry.get("engine_var", "")
            if not engine_var or entry.get("excluded_from_objective", False):
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

            targets.append(
                CalibrationTarget(
                    variable_name=engine_var,
                    years=np.asarray(years, dtype=int),
                    values=np.asarray(values, dtype=float),
                    unit=result.unit,
                    weight=weight,
                    source=f"pipeline:{entity}",
                    nrmsd_method=method,
                )
            )

        return targets

    def compare(
        self,
        targets: list[CalibrationTarget],
        engine_trajectories: dict[str, np.ndarray[Any, Any]],
        engine_time: np.ndarray[Any, Any],
    ) -> BridgeResult:
        """Compare engine trajectories against calibration targets."""
        per_var: dict[str, float] = {}
        coverage: dict[str, tuple[int, int]] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for target in targets:
            if target.variable_name not in engine_trajectories:
                continue

            engine_traj = engine_trajectories[target.variable_name]
            engine_at_years = np.interp(
                target.years.astype(float),
                engine_time.astype(float),
                engine_traj,
            )
            obs_values = target.values

            if self.normalize:
                engine_at_years, obs_values = self._normalize_pair(
                    engine_at_years,
                    obs_values,
                    target.years,
                    engine_traj,
                    engine_time,
                )

            nrmsd = self._compute_nrmsd(
                engine_at_years,
                obs_values,
                target.nrmsd_method,
            )

            if np.isfinite(nrmsd):
                per_var[target.variable_name] = nrmsd
                coverage[target.variable_name] = (
                    int(target.years[0]),
                    int(target.years[-1]),
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
        """Return targets with years clipped to [start_year, end_year]."""
        clipped: list[CalibrationTarget] = []
        for target in targets:
            mask = (target.years >= start_year) & (target.years <= end_year)
            years = target.years[mask]
            values = target.values[mask]
            if len(years) < 2:
                continue
            clipped.append(
                CalibrationTarget(
                    variable_name=target.variable_name,
                    years=years,
                    values=values,
                    unit=target.unit,
                    weight=target.weight,
                    source=target.source,
                    nrmsd_method=target.nrmsd_method,
                )
            )
        return clipped

    def build_objective(
        self,
        targets: list[CalibrationTarget],
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]],
        ],
        train_start: Optional[int] = None,
        train_end: Optional[int] = None,
    ) -> Callable[[dict[str, float]], float]:
        """Build NRMSD objective function from targets."""
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
            tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]],
        ],
        params: dict[str, float],
        validate_start: int,
        validate_end: int,
    ) -> BridgeResult:
        """Evaluate NRMSD on the holdout validation window only."""
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
        engine_ref = float(
            np.interp(
                self.reference_year,
                full_engine_time.astype(float),
                full_engine_traj,
            )
        )
        obs_ref = float(
            np.interp(
                self.reference_year,
                obs_years.astype(float),
                obs_values,
            )
        )

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
            model_pct = (
                np.diff(model) / np.where(np.abs(model[:-1]) > 1e-15, model[:-1], 1.0) * 100.0
            )
            ref_pct = (
                np.diff(reference)
                / np.where(np.abs(reference[:-1]) > 1e-15, reference[:-1], 1.0)
                * 100.0
            )

            valid = np.isfinite(model_pct) & np.isfinite(ref_pct)
            if not valid.any():
                return float("nan")
            model_pct = model_pct[valid]
            ref_pct = ref_pct[valid]

            mean_ref = np.mean(np.abs(ref_pct))
            if mean_ref < 1e-10:
                return float("nan")
            return float(np.sqrt(np.mean((model_pct - ref_pct) ** 2)) / mean_ref)

        mean_ref = np.mean(np.abs(reference))
        if mean_ref < 1e-15:
            return float("nan")
        return float(np.sqrt(np.mean((model - reference) ** 2)) / mean_ref)
