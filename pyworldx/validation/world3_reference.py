"""World3-03 historical validation (Section 13.1).

Target: reproduce Nebel et al. (2023) Recalibration23 result.
Pass criterion: total NRMSD <= 0.2719 on the 1970-2020 training window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from pyworldx.calibration.metrics import (
    NEBEL_2023_BOUNDS,
    NEBEL_2023_CALIBRATION_CONFIG,
    NEBEL_2023_TOTAL_NRMSD_BOUND,
    CrossValidationConfig,
    nrmsd_change_rate,
    nrmsd_direct,
)


@dataclass
class VariableValidation:
    """Validation result for a single variable."""

    variable: str
    nrmsd: float
    upper_bound: float
    nrmsd_function: str  # "direct" or "change_rate"
    passed: bool
    notes: str = ""


@dataclass
class World3ValidationReport:
    """Full World3-03 historical validation report."""

    config: CrossValidationConfig
    variable_results: list[VariableValidation] = field(default_factory=list)
    total_nrmsd: float = 0.0
    total_bound: float = NEBEL_2023_TOTAL_NRMSD_BOUND
    overall_passed: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def n_passed(self) -> int:
        return sum(1 for v in self.variable_results if v.passed)

    @property
    def n_total(self) -> int:
        return len(self.variable_results)


def validate_against_nebel2023(
    model_output: dict[str, "pd.Series[Any]"],
    historical_data: dict[str, "pd.Series[Any]"],
    config: CrossValidationConfig | None = None,
) -> World3ValidationReport:
    """Validate model output against Nebel et al. (2023) bounds.

    Args:
        model_output: model predictions keyed by variable name
        historical_data: empirical series keyed by variable name
        config: cross-validation config (defaults to NEBEL_2023_CALIBRATION_CONFIG)

    Returns:
        World3ValidationReport with per-variable and total NRMSD
    """
    if config is None:
        config = NEBEL_2023_CALIBRATION_CONFIG

    report = World3ValidationReport(config=config)
    nrmsd_scores: list[float] = []

    for var, (upper_bound, nrmsd_fn_name) in NEBEL_2023_BOUNDS.items():
        if var not in model_output or var not in historical_data:
            report.notes.append(f"Skipping {var}: missing data")
            continue

        pred = model_output[var]
        true = historical_data[var]

        # Restrict to training window
        train_mask = (true.index >= config.train_start) & (
            true.index <= config.train_end
        )
        true_train = true.loc[train_mask]
        pred_train = pred.reindex(true_train.index)

        if true_train.empty or pred_train.isna().all():
            report.notes.append(f"Skipping {var}: no overlapping data")
            continue

        pred_train = pred_train.dropna()
        true_train = true_train.loc[pred_train.index]

        # Compute NRMSD
        if nrmsd_fn_name == "direct":
            score = nrmsd_direct(true_train, pred_train)
        else:
            score = nrmsd_change_rate(true_train, pred_train)

        passed = score <= upper_bound
        nrmsd_scores.append(score)

        report.variable_results.append(
            VariableValidation(
                variable=var,
                nrmsd=score,
                upper_bound=upper_bound,
                nrmsd_function=nrmsd_fn_name,
                passed=passed,
            )
        )

    # Total NRMSD (mean of individual scores)
    if nrmsd_scores:
        report.total_nrmsd = sum(nrmsd_scores) / len(nrmsd_scores)
    report.overall_passed = report.total_nrmsd <= report.total_bound

    return report
