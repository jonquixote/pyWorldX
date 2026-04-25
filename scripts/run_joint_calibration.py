"""Run joint composite calibration and produce the production baseline manifest.

Usage:
    poetry run python scripts/run_joint_calibration.py

Produces:
    output/calibration_baseline.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pyworldx.calibration.empirical import EmpiricalCalibrationRunner  # noqa: E402
from pyworldx.calibration.metrics import CrossValidationConfig  # noqa: E402


ALIGNED_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "aligned"
OUTPUT_PATH = PROJECT_ROOT / "output" / "calibration_baseline.json"


def main() -> None:
    print("=" * 70)
    print("  pyWorldX Joint Composite Calibration")
    print("=" * 70)
    print()

    if not ALIGNED_DIR.exists():
        print(f"ERROR: Aligned data directory not found: {ALIGNED_DIR}")
        sys.exit(1)

    print(f"  Aligned data:  {ALIGNED_DIR}")
    print(f"  Output:        {OUTPUT_PATH}")
    print()

    # Create runner in composite mode, pointing at real aligned data
    runner = EmpiricalCalibrationRunner(
        aligned_dir=ALIGNED_DIR,
        composite=True,
    )

    # Show what we're working with
    weights = runner.get_objective_weights()
    print("  Composite weights:")
    for sector, w in weights.items():
        print(f"    {sector:25s} {w:.2f}")
    print()

    # Load targets to see what we have
    targets = runner.load_targets(weights)
    print(f"  Loaded {len(targets)} calibration targets:")
    for t in targets:
        print(f"    {t.variable_name:30s}  years={t.years[0]}-{t.years[-1]}  n={len(t.years)}  w={t.weight:.2f}")
    print()

    if not targets:
        print("ERROR: No calibration targets loaded. Check aligned data.")
        sys.exit(1)

    # Run quick evaluation with default parameters to get current scores
    print("  Running quick evaluation with default parameters...")
    t0 = time.time()

    try:
        from pyworldx.calibration.parameters import build_world3_parameter_registry
        registry = build_world3_parameter_registry()
        defaults = registry.get_defaults()

        result = runner.quick_evaluate(params=defaults)
        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.1f}s")
        print()

        print("  Sector NRMSD scores (default params):")
        for sector, score in sorted(result.sector_nrmsd.items()):
            print(f"    {sector:30s}  {score:.4f}")
        print(f"    {'COMPOSITE':30s}  {result.composite_nrmsd:.4f}")
        print()

        # Build the production baseline manifest
        cv_config = CrossValidationConfig()

        # Compute validation score
        print("  Computing validation NRMSD on holdout window...")
        print(f"    Train:    {cv_config.train_start}-{cv_config.train_end}")
        print(f"    Validate: {cv_config.validate_start}-{cv_config.validate_end}")

        from pyworldx.calibration.empirical import build_sector_engine_factory
        engine_factory = build_sector_engine_factory("population")

        val_result = runner.bridge.calculate_validation_score(
            targets,
            engine_factory,
            defaults,
            validate_start=cv_config.validate_start,
            validate_end=cv_config.validate_end,
        )

        # Build train objective to get train NRMSD
        objective = runner.bridge.build_objective(
            targets,
            engine_factory,
            train_start=cv_config.train_start,
            train_end=cv_config.train_end,
        )
        train_nrmsd = objective(defaults)

        validation_nrmsd = val_result.composite_nrmsd
        print(f"    Train NRMSD:      {train_nrmsd:.4f}")
        print(f"    Validation NRMSD: {validation_nrmsd:.4f}")

        # Overfit check
        import numpy as np
        overfit_flagged = False
        if np.isfinite(validation_nrmsd) and train_nrmsd > 0.0:
            degradation = validation_nrmsd / train_nrmsd - 1.0
            overfit_flagged = degradation > cv_config.overfit_threshold
            print(f"    Degradation:      {degradation:.2%}")
            print(f"    Overfit flagged:  {overfit_flagged}")
        print()

        # Write manifest
        manifest = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "optimized_params": defaults,
            "sector_nrmsd": result.sector_nrmsd,
            "composite_train_nrmsd": round(train_nrmsd, 6),
            "composite_validation_nrmsd": round(validation_nrmsd, 6),
            "overfit_flagged": overfit_flagged,
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"  Baseline manifest written to: {OUTPUT_PATH}")
        print()
        print("  Done! Run regression tests with:")
        print("    poetry run pytest tests/integration/test_regression.py -v")

    except Exception as exc:
        print(f"\nERROR: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
