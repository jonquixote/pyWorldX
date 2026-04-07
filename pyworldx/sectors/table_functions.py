"""Table function interpolation for World3-03 lookup tables.

World3 uses piecewise-linear table functions extensively. This module
provides a single interpolation utility used by all World3-03 sectors.
"""

from __future__ import annotations

import numpy as np


def table_lookup(
    x: float,
    x_points: list[float] | tuple[float, ...],
    y_points: list[float] | tuple[float, ...],
) -> float:
    """Piecewise-linear interpolation matching World3 table functions.

    Extrapolation: clamps to boundary values (flat extension).

    Args:
        x: input value
        x_points: monotonically increasing x breakpoints
        y_points: corresponding y values (same length as x_points)

    Returns:
        Interpolated y value
    """
    return float(np.interp(x, x_points, y_points))
