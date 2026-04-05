"""Tests for the RK4 integrator.

THE ANALYTICAL DECAY TEST IS WRITTEN FIRST.
The integrator code does not exist yet when this test is first committed.

Analytical sub-case from Section 17.4:
    P(t) = 100 * exp(-t / 20)

Pass criterion (hybrid — FIX-24):
    - For t <= 100: max relative error < 1e-4
    - For t > 100:  max absolute error < 1e-6
"""

from __future__ import annotations

import math

import pytest

from pyworldx.core.integrators import IntegrationError, rk4_step
from pyworldx.core.quantities import POLLUTION_UNITS, Quantity


class TestRK4AnalyticalDecay:
    """The canonical analytical sub-case: exponential decay.

    Config:
        pollution_inflow  = 0
        pollution_outflow = P / tau_p
        P(0) = 100
        tau_p = 20.0
        t_end = 200
        dt = 1.0

    Analytical solution: P(t) = 100 * exp(-t / tau_p)
    """

    TAU_P = 20.0
    P0 = 100.0
    DT = 1.0
    T_END = 200.0

    @staticmethod
    def analytical(t: float) -> float:
        return 100.0 * math.exp(-t / 20.0)

    @staticmethod
    def decay_derivatives(
        t: float, state: dict[str, Quantity]
    ) -> dict[str, Quantity]:
        """dP/dt = -P / tau_p"""
        p = state["P"].magnitude
        tau_p = 20.0
        dp_dt = -p / tau_p
        return {"P": Quantity(dp_dt, POLLUTION_UNITS)}

    def test_rk4_matches_analytical_hybrid_criterion(self) -> None:
        """Full 200-year run. Hybrid pass criterion per Section 17.4 / FIX-24."""
        state: dict[str, Quantity] = {"P": Quantity(self.P0, POLLUTION_UNITS)}
        t = 0.0

        max_rel_error = 0.0
        max_abs_error = 0.0

        while t < self.T_END - 1e-12:
            state = rk4_step(self.decay_derivatives, t, state, self.DT)
            t += self.DT

            expected = self.analytical(t)
            actual = state["P"].magnitude
            abs_error = abs(actual - expected)

            if t <= 100.0:
                # Relative error regime
                rel_error = abs_error / abs(expected) if expected != 0 else abs_error
                max_rel_error = max(max_rel_error, rel_error)
            else:
                # Absolute error regime (P approaching zero)
                max_abs_error = max(max_abs_error, abs_error)

        # Section 17.4 pass criteria
        assert max_rel_error < 1e-4, (
            f"Max relative error for t<=100: {max_rel_error:.2e} (limit: 1e-4)"
        )
        assert max_abs_error < 1e-6, (
            f"Max absolute error for t>100: {max_abs_error:.2e} (limit: 1e-6)"
        )

    def test_rk4_preserves_units(self) -> None:
        """Output state must carry the same unit family as input state."""
        state: dict[str, Quantity] = {"P": Quantity(self.P0, POLLUTION_UNITS)}
        new_state = rk4_step(self.decay_derivatives, 0.0, state, self.DT)
        assert new_state["P"].unit == POLLUTION_UNITS

    def test_rk4_single_step_accuracy(self) -> None:
        """One RK4 step on exponential decay. Should be extremely accurate."""
        state: dict[str, Quantity] = {"P": Quantity(self.P0, POLLUTION_UNITS)}
        new_state = rk4_step(self.decay_derivatives, 0.0, state, self.DT)

        expected = self.analytical(self.DT)
        actual = new_state["P"].magnitude
        rel_error = abs(actual - expected) / expected
        assert rel_error < 1e-8, f"Single-step relative error: {rel_error:.2e}"


class TestRK4Guards:
    """NaN/inf guardrails per Section 6.1."""

    @staticmethod
    def nan_derivatives(
        t: float, state: dict[str, Quantity]
    ) -> dict[str, Quantity]:
        return {"x": Quantity(float("nan"), "test")}

    @staticmethod
    def inf_derivatives(
        t: float, state: dict[str, Quantity]
    ) -> dict[str, Quantity]:
        return {"x": Quantity(float("inf"), "test")}

    def test_nan_derivative_raises(self) -> None:
        state = {"x": Quantity(1.0, "test")}
        with pytest.raises(IntegrationError, match="NaN"):
            rk4_step(self.nan_derivatives, 0.0, state, 1.0)

    def test_inf_derivative_raises(self) -> None:
        state = {"x": Quantity(1.0, "test")}
        with pytest.raises(IntegrationError, match="[Ii]nf"):
            rk4_step(self.inf_derivatives, 0.0, state, 1.0)
