"""Forecast report artifacts (Section 12.4).

Compact machine-readable reports for dashboards and notebooks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pyworldx.core.result import RunResult
from pyworldx.observability.manifest import RunManifest


@dataclass
class ForecastReport:
    """Compact machine-readable forecast report (Section 12.4).

    Suitable for dashboards and notebooks. Emitted for each run or ensemble.
    """

    report_type: str  # "deterministic" | "ensemble"
    manifest: dict[str, Any] = field(default_factory=dict)

    # Deterministic run summary
    final_values: dict[str, float] = field(default_factory=dict)
    peak_values: dict[str, float] = field(default_factory=dict)
    peak_times: dict[str, float] = field(default_factory=dict)

    # Ensemble summary
    ensemble_size: int = 0
    percentile_bands: dict[str, dict[str, float]] = field(default_factory=dict)
    threshold_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Diagnostics
    warnings: list[str] = field(default_factory=list)
    balance_audit_summary: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self._to_serializable(), indent=2)

    def _to_serializable(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "report_type": self.report_type,
            "manifest": self.manifest,
            "final_values": self.final_values,
            "peak_values": self.peak_values,
            "peak_times": self.peak_times,
            "ensemble_size": self.ensemble_size,
            "percentile_bands": self.percentile_bands,
            "threshold_results": self.threshold_results,
            "warnings": self.warnings,
            "balance_audit_summary": self.balance_audit_summary,
        }


def build_deterministic_report(
    result: RunResult,
    manifest: RunManifest | None = None,
    variables: list[str] | None = None,
) -> ForecastReport:
    """Build a forecast report from a deterministic run result.

    Args:
        result: RunResult from engine.run()
        manifest: optional RunManifest for provenance
        variables: subset of variables (None = all)
    """
    report = ForecastReport(report_type="deterministic")

    if manifest is not None:
        report.manifest = manifest.to_dict()
    report.warnings = list(result.warnings)

    # Collect balance audit summary
    audit_counts: dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for audit in result.balance_audits:
        status = str(audit.get("status", "PASS"))
        audit_counts[status] = audit_counts.get(status, 0) + 1
    report.balance_audit_summary = audit_counts

    # Compute final and peak values
    var_names = variables or list(result.trajectories.keys())
    for var in var_names:
        if var not in result.trajectories:
            continue
        traj = result.trajectories[var]
        report.final_values[var] = float(traj[-1])
        peak_idx = int(np.argmax(np.abs(traj)))
        report.peak_values[var] = float(traj[peak_idx])
        report.peak_times[var] = float(result.time_index[peak_idx])

    return report


def build_ensemble_report(
    summary: dict[str, pd.DataFrame],
    threshold_results: dict[str, Any] | None = None,
    manifest: RunManifest | None = None,
    ensemble_size: int = 0,
) -> ForecastReport:
    """Build a forecast report from an ensemble result.

    Args:
        summary: per-variable DataFrames with mean, median, percentiles
        threshold_results: threshold query results
        manifest: optional RunManifest for provenance
        ensemble_size: number of ensemble members
    """
    report = ForecastReport(
        report_type="ensemble",
        ensemble_size=ensemble_size,
    )

    if manifest is not None:
        report.manifest = manifest.to_dict()

    # Extract final-time percentile bands
    for var, df in summary.items():
        if df.empty:
            continue
        last = df.iloc[-1]
        report.percentile_bands[var] = {
            "mean": float(last.get("mean", 0.0)),
            "median": float(last.get("median", 0.0)),
            "p05": float(last.get("p05", 0.0)),
            "p95": float(last.get("p95", 0.0)),
            "min": float(last.get("min", 0.0)),
            "max": float(last.get("max", 0.0)),
        }
        report.final_values[var] = float(last.get("mean", 0.0))

    # Threshold results
    if threshold_results is not None:
        for name, tr in threshold_results.items():
            if hasattr(tr, "probability"):
                report.threshold_results[name] = {
                    "probability": tr.probability,
                    "member_count": tr.member_count,
                }
            else:
                report.threshold_results[name] = {"raw": str(tr)}

    return report
