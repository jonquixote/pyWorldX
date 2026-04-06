"""Algebraic loop solvers (Section 6.3).

Provides generalized fixed-point iteration (plain and damped) for
resolving simultaneous algebraic couplings between sectors.

The solver is topology-agnostic: it takes a list of sectors in the loop
and iterates their compute() calls until all shared variables converge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyworldx.core.quantities import Quantity


class AlgebraicLoopConvergenceError(Exception):
    """Raised when an algebraic loop does not converge."""


@dataclass
class LoopResult:
    """Diagnostics from algebraic loop resolution.

    Attributes:
        name: loop identifier
        converged: whether the loop converged within max_iter
        iterations: number of iterations used
        final_residual: max relative residual at convergence (or at exit)
        sector_names: sectors involved
        variables: variables in the loop
    """

    name: str
    converged: bool
    iterations: int
    final_residual: float
    sector_names: list[str]
    variables: list[str]


def resolve_algebraic_loop(
    loop_sectors: list[Any],
    sector_stock_map: dict[str, dict[str, Quantity]],
    shared: dict[str, Quantity],
    t: float,
    ctx: Any,
    *,
    tol: float = 1e-10,
    max_iter: int = 100,
    damping: float = 1.0,
    loop_name: str = "unnamed",
) -> LoopResult:
    """Resolve an algebraic loop via (optionally damped) fixed-point iteration.

    The solver iterates over the sectors in the loop, computing each one
    with the latest shared state, until all output variables converge.

    Args:
        loop_sectors: sectors participating in the loop, in evaluation order
        sector_stock_map: dict mapping sector.name -> {stock_name: Quantity}
        shared: mutable dict of inter-sector shared variables (updated in place)
        t: current time
        ctx: RunContext
        tol: convergence tolerance (max relative change)
        max_iter: maximum iterations
        damping: damping factor (1.0 = no damping, <1.0 = damped)
        loop_name: identifier for diagnostics

    Returns:
        LoopResult with convergence diagnostics

    Raises:
        AlgebraicLoopConvergenceError: if convergence is not achieved
    """
    # Track which variables each sector writes (non-derivative outputs)
    sector_outputs: dict[str, list[str]] = {}
    for s in loop_sectors:
        sector_outputs[s.name] = [
            v for v in s.declares_writes()
            if not v.startswith("d_")
        ]

    # All loop variables to track for convergence
    loop_vars: list[str] = []
    for outputs in sector_outputs.values():
        for v in outputs:
            if v not in loop_vars:
                loop_vars.append(v)

    # Snapshot current values for convergence checking
    prev_values: dict[str, float] = {}
    for var in loop_vars:
        if var in shared:
            prev_values[var] = shared[var].magnitude
        else:
            prev_values[var] = 0.0

    max_residual = float("inf")
    iterations_used = 0

    for iteration in range(max_iter):
        iterations_used = iteration + 1

        # Evaluate each sector in the loop with current shared state
        for s in loop_sectors:
            stocks = sector_stock_map.get(s.name, {})
            outputs = s.compute(t, stocks, shared, ctx)

            # Update shared state with non-derivative outputs
            for k, v in outputs.items():
                if not k.startswith("d_"):
                    if damping < 1.0 and k in prev_values:
                        # Damped update: new = damping * computed + (1-damping) * old
                        old_val = prev_values[k]
                        damped_val = damping * v.magnitude + (1.0 - damping) * old_val
                        shared[k] = Quantity(damped_val, v.unit)
                    else:
                        shared[k] = v

        # Check convergence: max relative change across all loop variables
        max_residual = 0.0
        for var in loop_vars:
            if var in shared:
                new_val = shared[var].magnitude
                old_val = prev_values.get(var, 0.0)
                diff = abs(new_val - old_val)
                if abs(new_val) > 1e-30:
                    rel = diff / abs(new_val)
                else:
                    rel = diff
                max_residual = max(max_residual, rel)
                prev_values[var] = new_val

        if max_residual < tol:
            return LoopResult(
                name=loop_name,
                converged=True,
                iterations=iterations_used,
                final_residual=max_residual,
                sector_names=[s.name for s in loop_sectors],
                variables=loop_vars,
            )

    raise AlgebraicLoopConvergenceError(
        f"Algebraic loop '{loop_name}' did not converge after {max_iter} "
        f"iterations at t={t}. Final residual: {max_residual:.2e}, "
        f"tol={tol}. Sectors: {[s.name for s in loop_sectors]}"
    )
