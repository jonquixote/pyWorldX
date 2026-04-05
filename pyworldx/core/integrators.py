"""Fixed-step integrators for the pyWorldX engine.

Provides RK4 (default) and Euler (debug).  All integrators operate on
``dict[str, Quantity]`` state dictionaries and enforce NaN/inf guards
per Section 6.1.
"""

from __future__ import annotations

import math
from typing import Callable

from pyworldx.core.quantities import Quantity


class IntegrationError(Exception):
    """Raised on NaN, inf, or unit inconsistency during integration."""


# Type alias for a derivative function:
#   f(t, state) -> dict of derivative quantities
DerivativeFn = Callable[[float, dict[str, Quantity]], dict[str, Quantity]]


def _check_derivatives(
    derivatives: dict[str, Quantity], stage: str
) -> None:
    """Guard against NaN/inf in derivative values. Raises IntegrationError."""
    for name, qty in derivatives.items():
        if math.isnan(qty.magnitude):
            raise IntegrationError(
                f"NaN detected in derivative of '{name}' at {stage}"
            )
        if math.isinf(qty.magnitude):
            raise IntegrationError(
                f"Inf detected in derivative of '{name}' at {stage}"
            )


def _add_weighted(
    state: dict[str, Quantity],
    derivatives: dict[str, Quantity],
    weight: float,
) -> dict[str, Quantity]:
    """Return state + weight * derivatives, preserving units."""
    result: dict[str, Quantity] = {}
    for name, s in state.items():
        if name in derivatives:
            d = derivatives[name]
            result[name] = Quantity(s.magnitude + weight * d.magnitude, s.unit)
        else:
            result[name] = s
    return result


def rk4_step(
    f: DerivativeFn,
    t: float,
    state: dict[str, Quantity],
    dt: float,
) -> dict[str, Quantity]:
    """Advance state by one RK4 step.

    Args:
        f:     derivative function  f(t, state) -> derivatives
        t:     current time
        state: current stock values
        dt:    timestep

    Returns:
        New state dict at t + dt.

    Raises:
        IntegrationError: on NaN or inf in any intermediate derivative.
    """
    k1 = f(t, state)
    _check_derivatives(k1, f"RK4 k1 at t={t}")

    state_k2 = _add_weighted(state, k1, 0.5 * dt)
    k2 = f(t + 0.5 * dt, state_k2)
    _check_derivatives(k2, f"RK4 k2 at t={t + 0.5 * dt}")

    state_k3 = _add_weighted(state, k2, 0.5 * dt)
    k3 = f(t + 0.5 * dt, state_k3)
    _check_derivatives(k3, f"RK4 k3 at t={t + 0.5 * dt}")

    state_k4 = _add_weighted(state, k3, dt)
    k4 = f(t + dt, state_k4)
    _check_derivatives(k4, f"RK4 k4 at t={t + dt}")

    # Combine: state_new = state + (dt/6) * (k1 + 2*k2 + 2*k3 + k4)
    new_state: dict[str, Quantity] = {}
    for name, s in state.items():
        if name in k1:
            update = (
                k1[name].magnitude
                + 2.0 * k2[name].magnitude
                + 2.0 * k3[name].magnitude
                + k4[name].magnitude
            ) * dt / 6.0
            new_state[name] = Quantity(s.magnitude + update, s.unit)
        else:
            new_state[name] = s

    return new_state


def euler_step(
    f: DerivativeFn,
    t: float,
    state: dict[str, Quantity],
    dt: float,
) -> dict[str, Quantity]:
    """Advance state by one Euler step (debug only at master step).

    Args:
        f:     derivative function  f(t, state) -> derivatives
        t:     current time
        state: current stock values
        dt:    timestep

    Returns:
        New state dict at t + dt.

    Raises:
        IntegrationError: on NaN or inf in derivatives.
    """
    derivatives = f(t, state)
    _check_derivatives(derivatives, f"Euler at t={t}")

    new_state: dict[str, Quantity] = {}
    for name, s in state.items():
        if name in derivatives:
            new_state[name] = Quantity(
                s.magnitude + dt * derivatives[name].magnitude, s.unit
            )
        else:
            new_state[name] = s

    return new_state
