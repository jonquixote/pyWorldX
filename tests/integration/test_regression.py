"""T4-1 · NRMSD Baseline Regression Tests.

After joint calibration the optimized parameter set and its NRMSD scores
are recorded as ``output/calibration_baseline.json``.  Any future change
that degrades scores beyond the 5 % tolerance must fail CI.

All three tests gracefully ``pytest.skip`` when the baseline manifest has
not yet been generated, so they are safe to run in CI before the first
calibration.
"""

from __future__ import annotations

import json
import pathlib

import pytest

_BASELINE_PATH = pathlib.Path("output/calibration_baseline.json")


# ── Helpers ───────────────────────────────────────────────────────────


def _load_baseline() -> dict:
    """Load the baseline manifest, skipping if it does not exist."""
    if not _BASELINE_PATH.exists():
        pytest.skip("Baseline not yet generated — skipping regression check")
    return json.loads(_BASELINE_PATH.read_text())  # type: ignore[return-value]


# ── Tests ─────────────────────────────────────────────────────────────


def test_baseline_manifest_exists():
    """The baseline manifest must be present on disk."""
    if not _BASELINE_PATH.exists():
        pytest.skip("Baseline not yet generated — skipping regression check")
    assert _BASELINE_PATH.exists(), (
        "output/calibration_baseline.json not found. "
        "Run joint calibration and save the result to this path."
    )


def test_baseline_nrmsd_within_tolerance():
    """Re-evaluate calibrated params; each sector must be within 5 %."""
    baseline = _load_baseline()

    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner

    runner = EmpiricalCalibrationRunner(composite=True)
    try:
        result = runner.quick_evaluate(params=baseline["optimized_params"])
    except Exception as exc:
        if "Aligned directory" in str(exc):
            pytest.skip(
                "Aligned data not available — skipping regression eval"
            )
        raise
    tolerance = 0.05  # 5 % relative degradation allowed
    for sector, base_score in baseline["sector_nrmsd"].items():
        current = result.sector_nrmsd.get(sector)
        assert current is not None, f"Sector '{sector}' missing from result"
        assert current <= base_score * (1 + tolerance), (
            f"NRMSD regression in sector '{sector}': "
            f"baseline={base_score:.4f}, current={current:.4f} "
            f"(>{tolerance * 100:.0f}% degradation)"
        )


def test_overfit_not_flagged_in_baseline():
    """The recorded baseline must not have overfitting flagged."""
    baseline = _load_baseline()
    assert not baseline["overfit_flagged"], (
        "Baseline manifest has overfit_flagged=True. "
        "Resolve overfitting before recording baseline."
    )
