"""Threshold query types and evaluation (Section 10.4).

Thresholds are declared in EnsembleSpec and computed eagerly at run time.
"""

from __future__ import annotations

from pyworldx.forecasting.ensemble import (
    EnsembleResult,
    ThresholdQuery,
    ThresholdQueryResult,
    UndeclaredThresholdQueryError,
)


def probability_of_threshold(
    ensemble: EnsembleResult, query_name: str
) -> float:
    """Access threshold probability (Section 10.7).

    If the threshold was not declared in EnsembleSpec, raises
    UndeclaredThresholdQueryError. Re-running the ensemble with the
    query declared is the correct resolution.
    """
    return ensemble.probability_of_threshold(query_name)


__all__ = [
    "ThresholdQuery",
    "ThresholdQueryResult",
    "UndeclaredThresholdQueryError",
    "probability_of_threshold",
]
