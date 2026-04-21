"""Empirical calibration runner — ties DataBridge to the calibration pipeline.

Runs the full calibration pipeline (profile likelihood -> Morris ->
Nelder-Mead -> Sobol) using empirical data from the data pipeline
as calibration targets.

Three-layer calibration stack:
  Layer 1: W3-03 reference trajectories (structural correctness)
  Layer 2: Empirical data from 37 pipeline connectors (real-world fit)
  Layer 3: USGS mineral data (resource cross-validation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from pyworldx.calibration.metrics import CrossValidationConfig
from pyworldx.calibration.parameters import ParameterRegistry
from pyworldx.calibration.pipeline import PipelineReport, run_calibration_pipeline
from pyworldx.data.bridge import (
    BridgeResult,
    CalibrationTarget,
    DataBridge,
    ENTITY_TO_ENGINE_MAP,
)


@dataclass
class EmpiricalCalibrationReport:
    """Full report from empirical calibration."""

    # Layer 1: Reference validation
    reference_result: Optional[BridgeResult] = None

    # Layer 2: Empirical calibration
    empirical_targets_loaded: int = 0
    empirical_result: Optional[BridgeResult] = None          # all-years score
    train_result: Optional[BridgeResult] = None              # train-window-only score
    pipeline_report: Optional[PipelineReport] = None

    # Layer 3: USGS cross-validation
    usgs_targets_loaded: int = 0
    usgs_result: Optional[BridgeResult] = None

    # Summary
    calibrated_parameters: dict[str, float] = field(default_factory=dict)
    converged: bool = False
    total_evaluations: int = 0
    validation_nrmsd: Optional[float] = None
    overfit_flagged: bool = False


class EmpiricalCalibrationRunner:
    """Runs calibration against empirical data.

    Connects the data pipeline's aligned Parquet store to the engine's
    calibration system via the DataBridge.
    """

    def __init__(
        self,
        aligned_dir: Path,
        reference_connector: Optional[Any] = None,
        usgs_data_dir: Optional[Path] = None,
        reference_year: Optional[int] = None,
        normalize: bool = True,
        entity_map: Optional[dict[str, Any]] = None,
        frozen_params: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize the runner.

        Args:
            aligned_dir: Path to data_pipeline/data/aligned/
            reference_connector: Optional World3ReferenceConnector for Layer 1
            usgs_data_dir: Path to USGS data directory for Layer 3.
                Defaults to data_pipeline/data/usgs/
            reference_year: Base year for normalization.
                Defaults to CrossValidationConfig.train_start.
            normalize: Whether to normalize trajectories
            entity_map: Override for ENTITY_TO_ENGINE_MAP
            frozen_params: Parameters held fixed during optimization (e.g. previously
                calibrated sector params). These are merged into calibrated_parameters
                in the report but never varied by the optimizer.
        """
        from pyworldx.calibration.metrics import CrossValidationConfig

        resolved_ref_year = (
            reference_year
            if reference_year is not None
            else CrossValidationConfig.train_start
        )
        self.aligned_dir = aligned_dir
        self.reference_connector = reference_connector
        self.usgs_data_dir = usgs_data_dir
        self.frozen_params: dict[str, float] = frozen_params or {}
        self.bridge = DataBridge(
            reference_year=resolved_ref_year,
            normalize=normalize,
            entity_map=entity_map or ENTITY_TO_ENGINE_MAP,
        )

    def load_targets(
        self,
        weights: Optional[dict[str, float]] = None,
    ) -> list[CalibrationTarget]:
        """Load all empirical calibration targets from the aligned store."""
        return self.bridge.load_targets(self.aligned_dir, weights)

    def load_reference_targets(
        self,
        weight: float = 1.0,
    ) -> list[CalibrationTarget]:
        """Load W3-03 reference targets (Layer 1).

        Requires a World3ReferenceConnector to have been provided.
        """
        if self.reference_connector is None:
            return []

        targets: list[CalibrationTarget] = []
        target_dicts = self.reference_connector.to_calibration_targets(weight=weight)

        for td in target_dicts:
            targets.append(
                CalibrationTarget(
                    variable_name=td["variable_name"],
                    years=td["years"],
                    values=td["values"],
                    unit=td["unit"],
                    weight=td["weight"],
                    source=td["source"],
                    nrmsd_method=td["nrmsd_method"],
                )
            )

        return targets

    def validate_against_reference(
        self,
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]],
        ],
        params: dict[str, float],
    ) -> Optional[BridgeResult]:
        """Run Layer 1 validation: compare engine against W3-03 reference."""
        ref_targets = self.load_reference_targets()
        if not ref_targets:
            return None

        try:
            trajectories, time_index = engine_factory(params)
        except Exception:
            return None

        return self.bridge.compare(ref_targets, trajectories, time_index)

    def load_usgs_targets(
        self,
        weight: float = 0.5,
    ) -> list[CalibrationTarget]:
        """Load USGS resource proxy targets (Layer 3)."""
        try:
            from data_pipeline.connectors.usgs import (
                compute_resource_extraction_index,
                compute_reserve_depletion_ratio,
            )
        except (ImportError, ModuleNotFoundError):
            return []

        usgs_dir = str(self.usgs_data_dir) if self.usgs_data_dir else None
        targets: list[CalibrationTarget] = []

        ext_index = compute_resource_extraction_index(usgs_dir)
        if not ext_index.empty and len(ext_index) >= 3:
            targets.append(
                CalibrationTarget(
                    variable_name="resource_extraction_index",
                    years=np.array(ext_index.index, dtype=int),
                    values=np.array(ext_index.values, dtype=float),
                    unit="index_base_100",
                    weight=weight,
                    source="usgs:resource_extraction_index",
                    nrmsd_method="change_rate",
                )
            )

        depl_ratio = compute_reserve_depletion_ratio(usgs_dir)
        if not depl_ratio.empty and len(depl_ratio) >= 3:
            targets.append(
                CalibrationTarget(
                    variable_name="reserve_depletion_ratio",
                    years=np.array(depl_ratio.index, dtype=int),
                    values=np.array(depl_ratio.values, dtype=float),
                    unit="dimensionless",
                    weight=weight,
                    source="usgs:reserve_depletion_ratio",
                    nrmsd_method="change_rate",
                )
            )

        return targets

    def cross_validate_usgs(
        self,
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]],
        ],
        params: dict[str, float],
        weight: float = 0.5,
    ) -> Optional[BridgeResult]:
        """Run Layer 3 cross-validation: USGS resource proxies."""
        usgs_targets = self.load_usgs_targets(weight)
        if not usgs_targets:
            return None

        try:
            trajectories, time_index = engine_factory(params)
        except Exception:
            return None

        return self.bridge.compare(usgs_targets, trajectories, time_index)

    def run(
        self,
        registry: ParameterRegistry,
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]],
        ],
        weights: Optional[dict[str, float]] = None,
        cross_val_config: Optional[CrossValidationConfig] = None,
        morris_trajectories: int = 10,
        sobol_samples: int = 256,
        seed: int = 42,
    ) -> EmpiricalCalibrationReport:
        """Execute the full empirical calibration pipeline."""
        report = EmpiricalCalibrationReport()

        targets = self.load_targets(weights)
        report.empirical_targets_loaded = len(targets)

        if not targets:
            return report

        # Build active registry (exclude frozen params from optimization)
        if self.frozen_params:
            from pyworldx.calibration.parameters import ParameterRegistry as _PR
            active_registry = _PR()
            for entry in registry.all_entries():
                if entry.name not in self.frozen_params:
                    active_registry.register(entry)
            # Wrap engine_factory to always inject frozen values
            _frozen = self.frozen_params
            _base_factory = engine_factory
            def _engine_fn(
                params: dict[str, float],
            ) -> tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]:
                return _base_factory({**params, **_frozen})
            active_engine_factory = _engine_fn  # type: ignore[assignment]
        else:
            active_registry = registry
            active_engine_factory = engine_factory  # type: ignore[assignment]

        defaults = active_registry.get_defaults()
        ref_result = self.validate_against_reference(active_engine_factory, defaults)
        if ref_result is not None:
            report.reference_result = ref_result

        train_start: Optional[int] = None
        train_end: Optional[int] = None
        if cross_val_config is not None:
            train_start = cross_val_config.train_start
            train_end = cross_val_config.train_end

        objective = self.bridge.build_objective(
            targets,
            active_engine_factory,
            train_start=train_start,
            train_end=train_end,
        )

        pipeline_report = run_calibration_pipeline(
            objective_fn=objective,
            registry=active_registry,
            cross_val_config=cross_val_config,
            morris_trajectories=morris_trajectories,
            sobol_samples=sobol_samples,
            seed=seed,
        )
        report.pipeline_report = pipeline_report
        report.total_evaluations = pipeline_report.total_evaluations

        if pipeline_report.calibration is not None:
            # Merge frozen params into calibrated_parameters so downstream
            # consumers (e.g. T2-3 runner) have the full parameter set.
            report.calibrated_parameters = {
                **pipeline_report.calibration.parameters,
                **self.frozen_params,
            }
            report.converged = pipeline_report.calibration.converged

            try:
                trajectories, time_index = active_engine_factory(report.calibrated_parameters)

                # All-years score (diagnostic, not used for NRMSD gate)
                report.empirical_result = self.bridge.compare(
                    targets,
                    trajectories,
                    time_index,
                )

                # Train-window-only score (used for NRMSD gate)
                if cross_val_config is not None:
                    train_targets = self.bridge._clip_targets_to_window(
                        targets,
                        cross_val_config.train_start,
                        cross_val_config.train_end,
                    )
                    report.train_result = self.bridge.compare(
                        train_targets,
                        trajectories,
                        time_index,
                    )
            except Exception:
                pass

            if cross_val_config is not None:
                val_result = self.bridge.calculate_validation_score(
                    targets,
                    active_engine_factory,
                    report.calibrated_parameters,
                    validate_start=cross_val_config.validate_start,
                    validate_end=cross_val_config.validate_end,
                )
                report.validation_nrmsd = val_result.composite_nrmsd

                train_nrmsd = pipeline_report.calibration.total_nrmsd
                if np.isfinite(val_result.composite_nrmsd) and train_nrmsd > 0.0:
                    degradation = val_result.composite_nrmsd / train_nrmsd - 1.0
                    report.overfit_flagged = (
                        degradation > cross_val_config.overfit_threshold
                    )

        final_params = report.calibrated_parameters or defaults
        usgs_targets = self.load_usgs_targets()
        report.usgs_targets_loaded = len(usgs_targets)
        if usgs_targets:
            usgs_result = self.cross_validate_usgs(active_engine_factory, final_params)
            if usgs_result is not None:
                report.usgs_result = usgs_result

        return report

    def quick_evaluate(
        self,
        engine_factory: Callable[
            [dict[str, float]],
            tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]],
        ],
        params: dict[str, float],
        weights: Optional[dict[str, float]] = None,
    ) -> BridgeResult:
        """Quick NRMSD evaluation without full calibration."""
        targets = self.load_targets(weights)
        trajectories, time_index = engine_factory(params)
        return self.bridge.compare(targets, trajectories, time_index)


def _resolve_registry(
    args: Any,
) -> tuple[ParameterRegistry, list[str]]:
    """Resolve a ParameterRegistry and parameter name list from CLI args.

    This is the canonical, testable replacement for the broken
    ParameterRegistry.for_sector() / registry.subset() calls.

    Args:
        args: Namespace with .sector (str) and .params (str | None)

    Returns:
        (full_registry, requested_names)
            full_registry — the complete 16-parameter registry
            requested_names — list of parameter names to calibrate

    Raises:
        ValueError: if sector has no parameters or a requested name is unknown
    """
    from pyworldx.calibration.parameters import build_world3_parameter_registry

    full_registry = build_world3_parameter_registry()

    params_arg = getattr(args, "params", None)
    if params_arg and str(params_arg).strip():
        requested = [p.strip() for p in str(params_arg).split(",") if p.strip()]
    else:
        requested = [
            e.name for e in full_registry.get_sector_parameters(args.sector)
        ]

    if not requested:
        raise ValueError(
            f"No parameters found for sector {args.sector!r}. "
            "Check that sector name matches 'sector_owner' in parameters.py. "
            "Valid sectors: population, capital, agriculture, resources, pollution"
        )

    missing = [n for n in requested if n not in full_registry._entries]
    if missing:
        raise ValueError(
            f"Unknown parameter(s): {missing}. "
            "Run: python -c \"from pyworldx.calibration.parameters import "
            "build_world3_parameter_registry; "
            "[print(e.name) for e in build_world3_parameter_registry().all_entries()]\""
        )

    return full_registry, requested


# ── Sector map for engine factory ─────────────────────────────────────

_SECTOR_NAMES: frozenset[str] = frozenset(
    ["population", "capital", "agriculture", "resources", "pollution"]
)


def build_sector_engine_factory(
    sector: str,
    t_start: float = 0.0,
    t_end: float = 200.0,
    master_dt: float = 1.0,
    calendar_base: float = 1900.0,
) -> Callable[[dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]]:
    """Build an engine_factory callable for calibration.

    Always runs all 5 World3 sectors (parameter coupling requires it),
    but the ``sector`` argument is validated to catch typos early.

    Parameters are injected as exogenous overrides keyed by their
    short name (i.e. ``"len_scale"`` not ``"population.len_scale"``),
    since that is what the sector ``compute()`` methods read from
    the shared-state ``inputs`` dict.

    Args:
        sector: One of the 5 World3 sector names (validated only).
        t_start: Simulation start in sim-time units (0 = year 1900).
        t_end: Simulation end in sim-time units (200 = year 2100).
        master_dt: Integration step size in years.
        calendar_base: Calendar year corresponding to t_start (default 1900).

    Returns:
        Callable: params -> (trajectories_dict, time_index_array)
            time_index_array is in calendar years.

    Raises:
        ValueError: if sector is not one of the 5 known World3 sectors.
    """
    if sector not in _SECTOR_NAMES:
        raise ValueError(
            f"Unknown sector {sector!r}. "
            f"Valid sectors: {sorted(_SECTOR_NAMES)}"
        )

    def factory(
        params: dict[str, float],
    ) -> tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]:
        from pyworldx.core.engine import Engine
        from pyworldx.sectors.population import PopulationSector
        from pyworldx.sectors.capital import CapitalSector
        from pyworldx.sectors.agriculture import AgricultureSector
        from pyworldx.sectors.resources import ResourcesSector
        from pyworldx.sectors.pollution import PollutionSector

        short_params: dict[str, float] = {}
        for name, val in params.items():
            short_key = name.split(".", 1)[-1] if "." in name else name
            short_params[short_key] = val

        def _injector(_t: float) -> dict[str, float]:
            return short_params

        engine = Engine(
            sectors=[
                PopulationSector(),
                CapitalSector(),
                AgricultureSector(),
                ResourcesSector(),
                PollutionSector(),
            ],
            master_dt=master_dt,
            t_start=t_start,
            t_end=t_end,
            exogenous_injector=_injector,
        )
        result = engine.run()

        time_index: np.ndarray[Any, Any] = (
            np.asarray(result.time_index, dtype=float) + calendar_base
        )
        return result.trajectories, time_index

    return factory


if __name__ == "__main__":
    import argparse
    import json
    import logging
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    _log = logging.getLogger("empirical.cli")

    parser = argparse.ArgumentParser(
        prog="python -m pyworldx.calibration.empirical",
        description="Run empirical calibration for one sector of the World3 engine.",
    )
    parser.add_argument(
        "--sector",
        required=True,
        help="Sector to calibrate (e.g. population, agriculture, resources).",
    )
    parser.add_argument(
        "--params",
        required=False,
        default="",
        help="Comma-separated list of parameter names to tune "
        "(e.g. population.len_scale,population.mtfn_scale). "
        "If omitted, all parameters registered for the sector are used.",
    )
    parser.add_argument(
        "--train-window",
        required=False,
        default=f"{CrossValidationConfig.train_start}-{CrossValidationConfig.train_end}",
        metavar="YYYY-YYYY",
        help=f"Training window as START-END (default: "
        f"{CrossValidationConfig.train_start}-{CrossValidationConfig.train_end}).",
    )
    parser.add_argument(
        "--holdout-window",
        required=False,
        default=None,
        metavar="YYYY-YYYY",
        help="Holdout/validation window as START-END. "
        "If omitted, no validation score is computed.",
    )
    parser.add_argument(
        "--nrmsd-target",
        type=float,
        default=None,
        metavar="FLOAT",
        help="Exit with code 1 if final train composite NRMSD exceeds this threshold.",
    )
    parser.add_argument(
        "--aligned-dir",
        default="output/aligned",
        metavar="PATH",
        help="Path to the aligned Parquet store (default: output/aligned).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write calibrated parameters as JSON to this path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the optimizer. Load targets, report data coverage, and exit.",
    )
    parser.add_argument(
        "--morris-trajectories",
        type=int,
        default=10,
        metavar="N",
        help="Morris screening trajectories (default: 10).",
    )
    parser.add_argument(
        "--sobol-samples",
        type=int,
        default=256,
        metavar="N",
        help="Sobol analysis base samples (default: 256).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42).",
    )

    args = parser.parse_args()

    # ── Parse windows ────────────────────────────────────────────────
    def _parse_window(s: str, label: str) -> tuple[int, int]:
        parts = s.split("-")
        if len(parts) != 2:
            parser.error(f"--{label} must be YYYY-YYYY, got: {s!r}")
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            parser.error(f"--{label} years must be integers, got: {s!r}")

    train_start, train_end = _parse_window(args.train_window, "train-window")

    validate_start: Optional[int] = None
    validate_end: Optional[int] = None
    if args.holdout_window:
        validate_start, validate_end = _parse_window(
            args.holdout_window, "holdout-window"
        )

    # ── Build CrossValidationConfig ──────────────────────────────────
    cfg = None
    if args.holdout_window:
        try:
            cfg = CrossValidationConfig(
                train_start=train_start,
                train_end=train_end,
                validate_start=validate_start,
                validate_end=validate_end,
            )
        except ValueError as e:
            parser.error(str(e))

    # ── Build runner ─────────────────────────────────────────────────
    aligned_dir = Path(args.aligned_dir)
    runner = EmpiricalCalibrationRunner(aligned_dir=aligned_dir)

    # ── Load targets ─────────────────────────────────────────────────
    _log.info("Loading empirical targets from %s …", aligned_dir)
    try:
        targets = runner.load_targets()
    except Exception as exc:
        _log.error("Failed to load targets: %s", exc)
        sys.exit(1)

    _log.info("Loaded %d calibration target(s).", len(targets))

    if not targets:
        _log.error(
            "No calibration targets loaded. "
            "Run: python -m data_pipeline run  then retry."
        )
        sys.exit(1)

    # ── Coverage report (always printed) ────────────────────────────
    print("\n── Data Coverage ───────────────────────────────────────────")
    for t in sorted(targets, key=lambda x: x.variable_name):
        print(
            f"  {t.variable_name:<35s}  "
            f"{int(t.years[0])}-{int(t.years[-1])}  "
            f"({len(t.years)} pts)  "
            f"source={t.source}"
        )
    print()

    if args.dry_run:
        _log.info("--dry-run: skipping optimizer. Exiting.")
        sys.exit(0)

    # ── Build ParameterRegistry scoped to requested params ───────────
    try:
        registry, requested = _resolve_registry(args)

        # Scope registry to only the requested parameters.
        # The pipeline optimizes over registry.all_entries(), so passing the
        # full 17-param registry causes it to drift all sectors while the
        # requested params sit at their defaults unchanged.
        from pyworldx.calibration.parameters import (
            ParameterEntry,
            build_world3_parameter_registry,
        )
        full_registry = build_world3_parameter_registry()
        scoped_registry = ParameterRegistry()
        for name in requested:
            scoped_registry.register(full_registry.lookup(name))
        registry = scoped_registry

    except ValueError as exc:
        _log.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        _log.error("Could not build ParameterRegistry: %s", exc)
        sys.exit(1)

    _log.info(
        "Calibrating %d parameter(s) in sector %r over train window %d-%d …",
        len(requested),
        args.sector,
        train_start,
        train_end,
    )

    # ── Engine factory (sector-scoped) ───────────────────────────────
    try:
        engine_factory = build_sector_engine_factory(args.sector)
    except Exception as exc:
        _log.error(
            "Could not build engine factory for sector %r: %s",
            args.sector,
            exc,
        )
        sys.exit(1)

    # ── Build sector-scoped objective weights ─────────────────────────
    _SECTOR_ENGINE_VARS: dict[str, set[str]] = {
        "population": {"POP"},
        "capital":    {"IC", "SC", "industrial_output", "industrial_output_per_capita"},
        "agriculture": {"AL", "food_per_capita"},
        "pollution":  {"PPOLX", "pollution_generation", "C_atm_ppm"},
        "resources":  {"NR", "resource_extraction_index", "reserve_depletion_ratio"},
    }
    sector_engine_vars = _SECTOR_ENGINE_VARS.get(args.sector, set())

    weights: dict[str, float] = {
        t.variable_name: (1.0 if t.variable_name in sector_engine_vars else 0.0)
        for t in targets
    }

    if not any(w > 0.0 for w in weights.values()):
        _log.error(
            "No calibration targets matched sector %r. "
            "Known sector engine vars: %s",
            args.sector,
            sorted(sector_engine_vars),
        )
        sys.exit(1)

    _log.info(
        "Objective restricted to sector-relevant target(s): %s",
        sorted(k for k, v in weights.items() if v > 0.0),
    )

    # ── Run calibration ──────────────────────────────────────────────
    report = runner.run(
        registry=registry,
        engine_factory=engine_factory,
        weights=weights,
        cross_val_config=cfg,
        morris_trajectories=args.morris_trajectories,
        sobol_samples=args.sobol_samples,
        seed=args.seed,
    )

    # ── Print results ────────────────────────────────────────────────
    print("── Calibration Results ─────────────────────────────────────")
    print(f"  Converged:          {report.converged}")
    print(f"  Total evaluations:  {report.total_evaluations}")

    if report.train_result is not None:
        print(f"  Train NRMSD:        {report.train_result.composite_nrmsd:.4f}")
        for var, nrmsd in sorted(report.train_result.per_variable_nrmsd.items()):
            print(f"    {var:<33s}  {nrmsd:.4f}")
    elif report.pipeline_report and report.pipeline_report.calibration is not None:
        print(
            f"  Train NRMSD:        "
            f"{report.pipeline_report.calibration.total_nrmsd:.4f}  (optimizer objective)"
        )

    if report.validation_nrmsd is not None:
        print(f"  Holdout NRMSD:      {report.validation_nrmsd:.4f}")
        if report.overfit_flagged:
            print(
                "  ⚠  Overfit flagged — validation NRMSD degraded beyond threshold."
            )

    if report.empirical_result is not None:
        print(f"  All-years NRMSD:    {report.empirical_result.composite_nrmsd:.4f}  (diagnostic)")

    if report.calibrated_parameters:
        print("\n── Calibrated Parameters ───────────────────────────────────")
        for k, v in sorted(report.calibrated_parameters.items()):
            print(f"  {k:<40s}  {v:.6g}")

    # ── Write output JSON ────────────────────────────────────────────
    if args.output and report.calibrated_parameters:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump(report.calibrated_parameters, fh, indent=2)
        _log.info("Calibrated parameters written to %s", out_path)

    # ── NRMSD gate (uses train-window score, not all-years) ──────────
    if args.nrmsd_target is not None:
        gate_nrmsd: Optional[float] = None
        if report.train_result is not None:
            gate_nrmsd = report.train_result.composite_nrmsd
        elif (
            report.pipeline_report is not None
            and report.pipeline_report.calibration is not None
        ):
            gate_nrmsd = report.pipeline_report.calibration.total_nrmsd

        if gate_nrmsd is not None:
            if gate_nrmsd > args.nrmsd_target:
                _log.error(
                    "NRMSD gate FAILED: train NRMSD %.4f > target %.4f",
                    gate_nrmsd,
                    args.nrmsd_target,
                )
                sys.exit(1)
            else:
                _log.info(
                    "NRMSD gate PASSED: train NRMSD %.4f <= target %.4f",
                    gate_nrmsd,
                    args.nrmsd_target,
                )
