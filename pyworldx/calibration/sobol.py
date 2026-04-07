"""Sobol variance decomposition (Section 9.3 Step 3).

Re-exports from sensitivity.py to match spec file layout.
"""

from pyworldx.calibration.sensitivity import (
    SobolResult,
    run_sobol_analysis,
)

__all__ = ["SobolResult", "run_sobol_analysis"]
