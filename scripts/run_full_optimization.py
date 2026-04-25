"""Run full Optuna + Nelder-Mead joint calibration.

This script runs the REAL optimization pipeline (not mocked):
  Step 0: Profile likelihood identifiability pre-screen
  Step 1: Morris elementary effects screening
  Step 2: Bayesian global search (Optuna TPE, 100 trials)
  Step 3: Local fine-tuning (Nelder-Mead)
  Step 4: Sobol variance decomposition

Usage:
    python3 scripts/run_full_optimization.py

Produces:
    output/calibration_baseline.json  (production manifest with optimized params)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from pyworldx.calibration.empirical import (  # noqa: E402
    EmpiricalCalibrationRunner,
    build_sector_engine_factory,
)
from pyworldx.calibration.metrics import CrossValidationConfig  # noqa: E402
from pyworldx.calibration.parameters import (  # noqa: E402
    build_world3_parameter_registry,
)

ALIGNED_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "aligned"
OUTPUT_PATH = PROJECT_ROOT / "output" / "calibration_baseline.json"
SEED = 42


def main() -> None:
    print("=" * 70)
    print("  pyWorldX Full Joint Optimization")
    print("  Optuna TPE (100 trials) + Nelder-Mead + Sobol")
    print("=" * 70)
    print()

    if not ALIGNED_DIR.exists():
        print(f"ERROR: Aligned data not found: {ALIGNED_DIR}")
        sys.exit(1)

    # ── Setup ─────────────────────────────────────────────────────────
    runner = EmpiricalCalibrationRunner(
        aligned_dir=ALIGNED_DIR,
        composite=True,
    )
    registry = build_world3_parameter_registry()
    defaults = registry.get_defaults()
    cv_config = CrossValidationConfig()
    engine_factory = build_sector_engine_factory("population")

    weights = runner.get_objective_weights()
    targets = runner.load_targets(weights)

    print(f"  Parameters:   {len(registry.all_entries())}")
    print(f"  Targets:      {len(targets)}")
    print(f"  Train window: {cv_config.train_start}-{cv_config.train_end}")
    print(f"  Holdout:      {cv_config.validate_start}-{cv_config.validate_end}")
    print(f"  Seed:         {SEED}")
    print()

    # ── Pre-optimization baseline ─────────────────────────────────────
    pre_result = runner.quick_evaluate(params=defaults)
    print(f"  Pre-optimization composite NRMSD: {pre_result.composite_nrmsd:.4f}")
    for sector, score in sorted(pre_result.sector_nrmsd.items()):
        print(f"    {sector:30s}  {score:.4f}")
    print()

    # ── Build objective ───────────────────────────────────────────────
    print("  Building composite objective function...")
    objective = runner.bridge.build_objective(
        targets,
        engine_factory,
        train_start=cv_config.train_start,
        train_end=cv_config.train_end,
    )

    # Verify objective works
    obj_default = objective(defaults)
    print(f"  Objective(defaults) = {obj_default:.4f}")
    print()

    # ── Run full pipeline ─────────────────────────────────────────────
    print("  Starting full calibration pipeline...")
    print("  This will take a while (Optuna 100 trials + Nelder-Mead + Sobol)...")
    print()
    t0 = time.time()

    optimized_params = runner._run_optimizer(
        objective_fn=objective,
        registry=registry,
        cross_val_config=cv_config,
        bayesian_n_trials=100,
        seed=SEED,
    )

    elapsed = time.time() - t0
    print(f"\n  Optimization complete in {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print()

    # ── Post-optimization evaluation ──────────────────────────────────
    post_result = runner.quick_evaluate(params=optimized_params)
    print(f"  Post-optimization composite NRMSD: {post_result.composite_nrmsd:.4f}")
    for sector, score in sorted(post_result.sector_nrmsd.items()):
        print(f"    {sector:30s}  {score:.4f}")
    print()

    # Show improvement
    improvement = (1.0 - post_result.composite_nrmsd / pre_result.composite_nrmsd) * 100
    print(f"  Improvement: {improvement:.1f}% reduction in composite NRMSD")
    print()

    # ── Train vs validation ───────────────────────────────────────────
    train_nrmsd = objective(optimized_params)
    val_result = runner.bridge.calculate_validation_score(
        targets,
        engine_factory,
        optimized_params,
        validate_start=cv_config.validate_start,
        validate_end=cv_config.validate_end,
    )
    validation_nrmsd = val_result.composite_nrmsd

    overfit_flagged = False
    if np.isfinite(validation_nrmsd) and train_nrmsd > 0.0:
        degradation = validation_nrmsd / train_nrmsd - 1.0
        overfit_flagged = degradation > cv_config.overfit_threshold
    else:
        degradation = float("nan")

    print(f"  Train NRMSD:      {train_nrmsd:.4f}")
    print(f"  Validation NRMSD: {validation_nrmsd:.4f}")
    print(f"  Degradation:      {degradation:.2%}")
    print(f"  Overfit flagged:  {overfit_flagged}")
    print()

    # ── Show optimized parameters ─────────────────────────────────────
    print("  Optimized parameters:")
    for name, val in sorted(optimized_params.items()):
        default_val = defaults.get(name, 0.0)
        delta = ((val / default_val) - 1.0) * 100 if default_val != 0 else 0.0
        print(f"    {name:40s}  {val:>15.4f}  ({delta:+.1f}%)")
    print()

    # ── Write manifest ────────────────────────────────────────────────
    manifest = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "optimized_params": optimized_params,
        "sector_nrmsd": post_result.sector_nrmsd,
        "composite_train_nrmsd": round(train_nrmsd, 6),
        "composite_validation_nrmsd": round(validation_nrmsd, 6),
        "overfit_flagged": overfit_flagged,
        "optimization_time_seconds": round(elapsed, 1),
        "seed": SEED,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  Manifest written to: {OUTPUT_PATH}")
    print()
    print("=" * 70)
    print("  DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
