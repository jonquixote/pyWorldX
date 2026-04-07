"""Run result container.

RunResult holds the complete output of a deterministic simulation run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import pandas as pd


@dataclass
class RunResult:
    """Structured result from a single deterministic engine run (Section 6.7).

    Attributes:
        time_index:       array of time values (years).
        trajectories:     dict mapping variable name -> array of values.
        observables:      dict mapping observable name -> array of values.
        trace_ref:        reference to trace data (CausalTraceRef list or None).
        balance_audits:   list of balance audit result dicts.
        warnings:         list of warning strings emitted during the run.
        scenario_metadata: scenario name, hash, and config snapshot.
        provenance:       provenance manifest reference dict.
    """

    time_index: npt.NDArray[np.float64]
    trajectories: dict[str, npt.NDArray[np.float64]]
    observables: dict[str, npt.NDArray[np.float64]] = field(
        default_factory=dict
    )
    trace_ref: object | None = None
    balance_audits: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scenario_metadata: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert trajectories to a pandas DataFrame with time index."""
        data = {"t": self.time_index}
        data.update(self.trajectories)
        data.update(self.observables)
        return pd.DataFrame(data)
