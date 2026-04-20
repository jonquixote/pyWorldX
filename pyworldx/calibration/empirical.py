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
    empirical_result: Optional[BridgeResult] = None
    pipeline_report: Optional[PipelineReport] = None

    # Layer 3: USGS cross-validation
    usgs_targets_loaded: int = 0
    usgs_result: Optional[BridgeResult] = None

    # Summary
    calibrated_parameters: dict[str, float] = field(default_factory=dict)
    converged: bool = False
    total_evaluations: int = 0
    validation_nrmsd: Optional[float] = None   # holdout window NRMSD
    overfit_flagged: bool = False               # True if validation degrades > overfit_threshold


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
        """
        from pyworldx.calibration.metrics import CrossValidationConfig
        resolved_ref_year = reference_year if reference_year is not None else CrossValidationConfig.train_start
        self.aligned_dir = aligned_dir
        self.reference_connector = reference_connector
        self.usgs_data_dir = usgs_data_dir
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
            targets.append(CalibrationTarget(
                variable_name=td["variable_name"],
                years=td["years"],
                values=td["values"],
                unit=td["unit"],
                weight=td["weight"],
                source=td["source"],
                nrmsd_method=td["nrmsd_method"],
            ))

        return targets

    def validate_against_reference(
        self,
        engine_factory: Callable[
            [dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]
        ],
        params: dict[str, float],
    ) -> Optional[BridgeResult]:
        """Run Layer 1 validation: compare engine against W3-03 reference.

        Args:
            engine_factory: Callable(params) -> (trajectories, time_index)
            params: Parameter dict to evaluate

        Returns:
            BridgeResult or None if no reference connector.
        """
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
        """Load USGS resource proxy targets (Layer 3).

        Computes aggregate extraction index and depletion ratio from
        USGS world production data for cross-validation against the
        engine's resource sector.

        Args:
            weight: Weight for USGS targets in composite NRMSD.
                Default 0.5 (lower than empirical data, since these
                are proxy comparisons, not direct measurements).

        Returns:
            List of CalibrationTarget objects (0-2 targets).
        """
        try:
            from data_pipeline.connectors.usgs import (
                compute_resource_extraction_index,
                compute_reserve_depletion_ratio,
            )
        except (ImportError, ModuleNotFoundError):
            return []

        usgs_dir = str(self.usgs_data_dir) if self.usgs_data_dir else None
        targets: list[CalibrationTarget] = []

        # Extraction index -> proxy for NRUR
        ext_index = compute_resource_extraction_index(usgs_dir)
        if not ext_index.empty and len(ext_index) >= 3:
            targets.append(CalibrationTarget(
                variable_name="resource_extraction_index",
                years=np.array(ext_index.index, dtype=int),
                values=np.array(ext_index.values, dtype=float),
                unit="index_base_100",
                weight=weight,
                source="usgs:resource_extraction_index",
                nrmsd_method="change_rate",
            ))

        # Depletion ratio -> proxy for (1 - NRFR) rate
        depl_ratio = compute_reserve_depletion_ratio(usgs_dir)
        if not depl_ratio.empty and len(depl_ratio) >= 3:
            targets.append(CalibrationTarget(
                variable_name="reserve_depletion_ratio",
                years=np.array(depl_ratio.index, dtype=int),
                values=np.array(depl_ratio.values, dtype=float),
                unit="dimensionless",
                weight=weight,
                source="usgs:reserve_depletion_ratio",
                nrmsd_method="change_rate",
            ))

        return targets

    def cross_validate_usgs(
        self,
        engine_factory: Callable[
            [dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]
        ],
        params: dict[str, float],
        weight: float = 0.5,
    ) -> Optional[BridgeResult]:
        """Run Layer 3 cross-validation: USGS resource proxies.

        Args:
            engine_factory: Callable(params) -> (trajectories, time_index)
            params: Parameter dict to evaluate
            weight: Weight for USGS targets

        Returns:
            BridgeResult or None if USGS data unavailable.
        """
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
            [dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]
        ],
        weights: Optional[dict[str, float]] = None,
        cross_val_config: Optional[CrossValidationConfig] = None,
        morris_trajectories: int = 10,
        sobol_samples: int = 256,
        seed: int = 42,
    ) -> EmpiricalCalibrationReport:
        """Execute the full empirical calibration pipeline.

        Steps:
        1. Load empirical targets from aligned store
        2. (Optional) Validate against W3-03 reference (Layer 1)
        3. Build NRMSD objective from empirical targets
        4. Run full calibration pipeline (profile → Morris → NM → Sobol)
        5. Evaluate final calibrated parameters

        Args:
            registry: Parameter registry with bounds and defaults
            engine_factory: Callable(params) -> (trajectories, time_index)
            weights: Per-variable weights for NRMSD composite
            cross_val_config: Train/validate split config
            morris_trajectories: Morris screening trajectories
            sobol_samples: Sobol analysis base samples
            seed: Random seed

        Returns:
            EmpiricalCalibrationReport
        """
        report = EmpiricalCalibrationReport()

        # ── Load targets ──────────────────────────────────────────────
        targets = self.load_targets(weights)
        report.empirical_targets_loaded = len(targets)

        if not targets:
            return report

        # ── Layer 1: Reference validation (pre-calibration) ───────────
        defaults = registry.get_defaults()
        ref_result = self.validate_against_reference(engine_factory, defaults)
        if ref_result is not None:
            report.reference_result = ref_result

        # ── Layer 2: Build objective and run pipeline ───────────────
        # Build objective restricted to the train window (avoids look-ahead bias)
        train_start: Optional[int] = None
        train_end: Optional[int] = None
        if cross_val_config is not None:
            train_start = cross_val_config.train_start
            train_end = cross_val_config.train_end

        objective = self.bridge.build_objective(
            targets, engine_factory,
            train_start=train_start,
            train_end=train_end,
        )

        pipeline_report = run_calibration_pipeline(
            objective_fn=objective,
            registry=registry,
            cross_val_config=cross_val_config,
            morris_trajectories=morris_trajectories,
            sobol_samples=sobol_samples,
            seed=seed,
        )
        report.pipeline_report = pipeline_report
        report.total_evaluations = pipeline_report.total_evaluations

        # ── Extract calibrated parameters ─────────────────────────
        if pipeline_report.calibration is not None:
            report.calibrated_parameters = pipeline_report.calibration.parameters
            report.converged = pipeline_report.calibration.converged

            # Evaluate calibrated params against empirical targets (all years)
            try:
                trajectories, time_index = engine_factory(
                    report.calibrated_parameters
                )
                report.empirical_result = self.bridge.compare(
                    targets, trajectories, time_index,
                )
            except Exception:
                pass

            # Validation score on holdout window
            if cross_val_config is not None:
                val_result = self.bridge.calculate_validation_score(
                    targets,
                    engine_factory,
                    report.calibrated_parameters,
                    validate_start=cross_val_config.validate_start,
                    validate_end=cross_val_config.validate_end,
                )
                report.validation_nrmsd = val_result.composite_nrmsd

                train_nrmsd = pipeline_report.calibration.total_nrmsd
                if (
                    np.isfinite(val_result.composite_nrmsd)
                    and train_nrmsd > 0.0
                ):
                    degradation = val_result.composite_nrmsd / train_nrmsd - 1.0
                    report.overfit_flagged = (
                        degradation > cross_val_config.overfit_threshold
                    )

        # ── Layer 3: USGS cross-validation (post-calibration) ──────────
        final_params = report.calibrated_parameters or defaults
        usgs_targets = self.load_usgs_targets()
        report.usgs_targets_loaded = len(usgs_targets)
        if usgs_targets:
            usgs_result = self.cross_validate_usgs(
                engine_factory, final_params,
            )
            if usgs_result is not None:
                report.usgs_result = usgs_result

        return report

    def quick_evaluate(
        self,
        engine_factory: Callable[
            [dict[str, float]], tuple[dict[str, np.ndarray[Any, Any]], np.ndarray[Any, Any]]
        ],
        params: dict[str, float],
        weights: Optional[dict[str, float]] = None,
    ) -> BridgeResult:
        """Quick NRMSD evaluation without full calibration.

        Useful for spot-checking a parameter set against empirical data.

        Args:
            engine_factory: Callable(params) -> (trajectories, time_index)
            params: Parameter dict to evaluate
            weights: Per-variable weights

        Returns:
            BridgeResult with per-variable and composite NRMSD.
        """
        targets = self.load_targets(weights)
        trajectories, time_index = engine_factory(params)
        return self.bridge.compare(targets, trajectories, time_index)


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
        help="Comma-separated list of parameter names to tune (e.g. population.len_scale,population.mtfn_scale). "
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
        help="Exit with code 1 if final composite NRMSD exceeds this threshold.",
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
        validate_start, validate_end = _parse_window(args.holdout_window, "holdout-window")

    # ── Build CrossValidationConfig ──────────────────────────────────
    cfg = CrossValidationConfig(
        train_start=train_start,
        train_end=train_end,
        validate_start=validate_start or train_end,
        validate_end=validate_end or train_end,
    )

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
        from pyworldx.calibration.parameters import build_world3_parameter_registry
        full_registry = build_world3_parameter_registry()

        # Determine which parameter names to tune
        if args.params:
            requested = [p.strip() for p in args.params.split(",") if p.strip()]
        else:
            requested = [
                e.name for e in full_registry.get_sector_parameters(args.sector)
            ]

        if not requested:
            _log.error(
                "No parameters found for sector %r. "
                "Check that sector name matches 'sector_owner' in parameters.py. "
                "Valid sectors: %s",
                args.sector,
                sorted({e.sector_owner for e in full_registry.all_entries()}),
            )
            sys.exit(1)

        # Validate all requested names exist in the registry
        missing = [n for n in requested if n not in full_registry._entries]
        if missing:
            _log.error(
                "Unknown parameter(s): %s\n"
                "To list all valid parameter names run:\n"
                "  python -c \"from pyworldx.calibration.parameters import "
                "build_world3_parameter_registry; "
                "[print(e.name) for e in build_world3_parameter_registry().all_entries()]\"",
                missing,
            )
            sys.exit(1)

        registry = full_registry

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
        from pyworldx.engine import build_sector_engine_factory
        engine_factory = build_sector_engine_factory(args.sector)
    except Exception as exc:
        _log.error("Could not build engine factory for sector %r: %s", args.sector, exc)
        sys.exit(1)

    # ── Run calibration ──────────────────────────────────────────────
    report = runner.run(
        registry=registry,
        engine_factory=engine_factory,
        cross_val_config=cfg,
        morris_trajectories=args.morris_trajectories,
        sobol_samples=args.sobol_samples,
        seed=args.seed,
    )

    # ── Print results ────────────────────────────────────────────────
    print("── Calibration Results ─────────────────────────────────────")
    print(f"  Converged:          {report.converged}")
    print(f"  Total evaluations:  {report.total_evaluations}")

    if report.empirical_result:
        print(f"  Train NRMSD:        {report.empirical_result.composite_nrmsd:.4f}")
        for var, nrmsd in sorted(report.empirical_result.per_variable_nrmsd.items()):
            print(f"    {var:<33s}  {nrmsd:.4f}")

    if report.validation_nrmsd is not None:
        print(f"  Holdout NRMSD:      {report.validation_nrmsd:.4f}")
        if report.overfit_flagged:
            print("  ⚠  Overfit flagged — validation NRMSD degraded beyond threshold.")

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

    # ── NRMSD gate ───────────────────────────────────────────────────
    if args.nrmsd_target is not None and report.empirical_result is not None:
        final_nrmsd = report.empirical_result.composite_nrmsd
        if final_nrmsd > args.nrmsd_target:
            _log.error(
                "NRMSD gate FAILED: composite NRMSD %.4f > target %.4f",
                final_nrmsd,
                args.nrmsd_target,
            )
            sys.exit(1)
        else:
            _log.info(
                "NRMSD gate PASSED: composite NRMSD %.4f <= target %.4f",
                final_nrmsd,
                args.nrmsd_target,
            )
