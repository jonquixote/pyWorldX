"""Empirical calibration runner — ties DataBridge to the calibration pipeline.

Runs the full calibration pipeline (profile likelihood -> Morris ->
Nelder-Mead -> Sobol) using empirical data from the data pipeline
as calibration targets.

Three-layer calibration stack:
  Layer 1: W3-03 reference trajectories (structural correctness)
  Layer 2: Empirical data from 37 pipeline connectors (real-world fit)
  Layer 3: USGS mineral data (resource cross-validation)

This module implements Layers 1 and 2. Layer 3 is in the USGS connector.
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

    # Summary
    calibrated_parameters: dict[str, float] = field(default_factory=dict)
    converged: bool = False
    total_evaluations: int = 0


class EmpiricalCalibrationRunner:
    """Runs calibration against empirical data.

    Connects the data pipeline's aligned Parquet store to the engine's
    calibration system via the DataBridge.
    """

    def __init__(
        self,
        aligned_dir: Path,
        reference_connector: Optional[Any] = None,
        reference_year: int = 1970,
        normalize: bool = True,
        entity_map: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize the runner.

        Args:
            aligned_dir: Path to data_pipeline/data/aligned/
            reference_connector: Optional World3ReferenceConnector for Layer 1
            reference_year: Base year for normalization (default 1970)
            normalize: Whether to normalize trajectories
            entity_map: Override for ENTITY_TO_ENGINE_MAP
        """
        self.aligned_dir = aligned_dir
        self.reference_connector = reference_connector
        self.bridge = DataBridge(
            reference_year=reference_year,
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

        # ── Layer 2: Build objective and run pipeline ─────────────────
        objective = self.bridge.build_objective(targets, engine_factory)

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

        # ── Extract calibrated parameters ─────────────────────────────
        if pipeline_report.calibration is not None:
            report.calibrated_parameters = pipeline_report.calibration.parameters
            report.converged = pipeline_report.calibration.converged

            # Evaluate calibrated params against empirical targets
            try:
                trajectories, time_index = engine_factory(
                    report.calibrated_parameters
                )
                report.empirical_result = self.bridge.compare(
                    targets, trajectories, time_index,
                )
            except Exception:
                pass

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
