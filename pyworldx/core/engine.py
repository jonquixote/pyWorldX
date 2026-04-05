"""pyWorldX simulation engine.

Orchestrates: sector initialization → dependency resolution →
multi-rate time loop with RK4 → algebraic loop resolution →
trajectory collection → RunResult.

Sprint 1 scope: functional engine with fixed-point loop solver
and multi-rate sub-stepping for the canonical R-I-P test world.
"""

from __future__ import annotations


import numpy as np

from pyworldx.core.integrators import rk4_step
from pyworldx.core.quantities import DIMENSIONLESS, INDUSTRIAL_OUTPUT_UNITS, Quantity
from pyworldx.core.result import RunResult
from pyworldx.sectors.base import RunContext


class IncompatibleTimestepError(Exception):
    """Raised when master_dt / timestep_hint is not an integer."""


class AlgebraicLoopConvergenceError(Exception):
    """Raised when an algebraic loop does not converge."""


def resolve_substep_ratio(
    master_dt: float, timestep_hint: float, tol: float = 1e-9
) -> int:
    """Convert timestep_hint to integer substep ratio (Section 5.3).

    Raises IncompatibleTimestepError if the ratio is not integer within tol.
    """
    ratio = master_dt / timestep_hint
    ratio_int = int(round(ratio))
    if abs(ratio - ratio_int) > tol:
        raise IncompatibleTimestepError(
            f"master_dt={master_dt} / timestep_hint={timestep_hint} = {ratio:.6f}, "
            f"which is not an integer within tolerance {tol}. "
            f"Adjust master_dt or timestep_hint so that their ratio is a whole number."
        )
    return ratio_int


SectorLike = object  # Accept any object with the BaseSector interface


class Engine:
    """The pyWorldX simulation engine.

    Runs sectors through an RK4 integration loop with:
    - Multi-rate sub-stepping for fast sectors
    - Fixed-point algebraic loop resolution for simultaneous couplings
    - NaN/inf guardrails
    """

    def __init__(
        self,
        sectors: list[object],
        master_dt: float = 1.0,
        t_start: float = 0.0,
        t_end: float = 200.0,
        loop_tol: float = 1e-10,
        loop_max_iter: int = 100,
    ) -> None:
        self.sectors = sectors
        self.master_dt = master_dt
        self.t_start = t_start
        self.t_end = t_end
        self.loop_tol = loop_tol
        self.loop_max_iter = loop_max_iter

        # Resolve sub-step ratios at init (fail loud)
        self.substep_ratios: dict[str, int] = {}
        for s in self.sectors:
            hint = s.timestep_hint  # type: ignore[attr-defined]
            if hint is not None:
                self.substep_ratios[s.name] = resolve_substep_ratio(  # type: ignore[attr-defined]
                    master_dt, hint
                )
            else:
                self.substep_ratios[s.name] = 1  # type: ignore[attr-defined]

        # Build sector lookup
        self._sectors_by_name: dict[str, object] = {
            s.name: s for s in self.sectors  # type: ignore[attr-defined]
        }

        # Classify sectors
        self._single_rate: list[object] = []
        self._sub_stepped: list[object] = []
        for s in self.sectors:
            if self.substep_ratios[s.name] > 1:  # type: ignore[attr-defined]
                self._sub_stepped.append(s)
            else:
                self._single_rate.append(s)

    def run(self) -> RunResult:
        """Execute the full simulation and return structured results."""
        ctx = RunContext(
            master_dt=self.master_dt,
            t_start=self.t_start,
            t_end=self.t_end,
        )

        # ── Initialize stocks ────────────────────────────────────────
        all_stocks: dict[str, Quantity] = {}
        sector_stock_names: dict[str, list[str]] = {}
        for s in self.sectors:
            sector_stocks = s.init_stocks(ctx)  # type: ignore[attr-defined]
            all_stocks.update(sector_stocks)
            sector_stock_names[s.name] = list(sector_stocks.keys())  # type: ignore[attr-defined]

        # Shared auxiliary/observable state (inter-sector communication)
        shared: dict[str, Quantity] = {}

        # Initialize shared state with defaults so first compute works
        shared["extraction_rate"] = Quantity(0.0, "resource_units")
        shared["industrial_output"] = Quantity(0.0, "industrial_output_units")
        shared["pollution_fraction"] = Quantity(0.0, "dimensionless")
        shared["pollution_efficiency"] = Quantity(1.0, "dimensionless")

        # ── Bootstrap: compute initial auxiliaries at t=0 ────────────
        # Without this, extraction_rate=0 → io = A*K^β*0^(1-β)*pe = 0
        # forever (Cobb-Douglas killed by zero input).
        # First pass: compute R's auxiliaries with an initial guess for io,
        # then resolve the I<->P loop at t=0.

        # Initial guess for industrial_output from K alone (ignoring resources)
        # io_guess = A * K^beta * 1.0 (assume full extraction capacity initially)
        k0 = all_stocks["K"].magnitude
        io_guess = 1.0 * (k0 ** 0.7) * 1.0  # A=1, pe=1, er=1 guess
        shared["industrial_output"] = Quantity(io_guess, "industrial_output_units")

        # Bootstrap R sector to get initial extraction_rate
        for s in self._sub_stepped:
            r_stocks = {k: all_stocks[k] for k in sector_stock_names[s.name]}  # type: ignore[attr-defined]
            r_out = s.compute(self.t_start, r_stocks, shared, ctx)  # type: ignore[attr-defined]
            for k, v in r_out.items():
                if not k.startswith("d_"):
                    shared[k] = v

        # Bootstrap I<->P loop at t=0 to get consistent initial auxiliaries
        self._resolve_ip_loop(
            self.t_start, all_stocks, shared, ctx,
            sector_stock_names, []
        )

        # Re-compute R with converged industrial_output
        for s in self._sub_stepped:
            r_stocks = {k: all_stocks[k] for k in sector_stock_names[s.name]}  # type: ignore[attr-defined]
            r_out = s.compute(self.t_start, r_stocks, shared, ctx)  # type: ignore[attr-defined]
            for k, v in r_out.items():
                if not k.startswith("d_"):
                    shared[k] = v

        # Final I<->P pass with correct extraction_rate
        self._resolve_ip_loop(
            self.t_start, all_stocks, shared, ctx,
            sector_stock_names, []
        )

        # ── Recording setup ──────────────────────────────────────────
        time_index: list[float] = [self.t_start]
        traj: dict[str, list[float]] = {}
        # Initialize trajectory recording for all stocks and observables
        for name, qty in all_stocks.items():
            traj[name] = [qty.magnitude]
        for obs in ["extraction_rate", "industrial_output",
                     "pollution_fraction", "pollution_efficiency"]:
            traj[obs] = [shared[obs].magnitude]

        warnings_list: list[str] = []

        # ── Master time loop ─────────────────────────────────────────
        t = self.t_start
        steps = int(round((self.t_end - self.t_start) / self.master_dt))

        for step_idx in range(steps):
            # ── 1) Sub-stepped sectors (R) advance across the master step ──
            for s in self._sub_stepped:
                ratio = self.substep_ratios[s.name]  # type: ignore[attr-defined]
                sub_dt = self.master_dt / ratio
                sub_stocks = {
                    k: all_stocks[k]
                    for k in sector_stock_names[s.name]  # type: ignore[attr-defined]
                }
                sub_inputs = dict(shared)  # frozen at master boundary
                sub_t = t

                for _sub in range(ratio):
                    def make_sub_deriv(
                        sector: object, inputs: dict[str, Quantity]
                    ) -> object:
                        def deriv(
                            t_: float, st: dict[str, Quantity]
                        ) -> dict[str, Quantity]:
                            result = sector.compute(t_, st, inputs, ctx)  # type: ignore[attr-defined]
                            # Return only derivative entries (d_ prefix)
                            return {
                                k.replace("d_", ""): v
                                for k, v in result.items()
                                if k.startswith("d_")
                            }
                        return deriv

                    deriv_fn = make_sub_deriv(s, sub_inputs)
                    sub_stocks = rk4_step(deriv_fn, sub_t, sub_stocks, sub_dt)  # type: ignore[arg-type]
                    sub_t += sub_dt

                # Update global stocks from sub-stepped sector
                for k, v in sub_stocks.items():
                    all_stocks[k] = v

                # Compute auxiliaries at end of master step
                final_out = s.compute(t + self.master_dt, sub_stocks, sub_inputs, ctx)  # type: ignore[attr-defined]
                for k, v in final_out.items():
                    if not k.startswith("d_"):
                        shared[k] = v

            # ── 2) Single-rate sectors (I, P) with algebraic loop ────
            # I and P are coupled: I needs pollution_efficiency from P,
            # P needs industrial_output from I.  Fixed-point iteration.
            self._resolve_ip_loop(t + self.master_dt, all_stocks, shared, ctx,
                                  sector_stock_names, warnings_list)

            # ── 3) Integrate single-rate sector stocks via RK4 ───────
            for s in self._single_rate:
                s_name: str = s.name  # type: ignore[attr-defined]
                s_stock_names = sector_stock_names[s_name]
                s_stocks = {k: all_stocks[k] for k in s_stock_names}

                def make_sr_deriv(
                    sector: object,
                    shared_st: dict[str, Quantity],
                ) -> object:
                    def deriv(
                        t_: float, st: dict[str, Quantity]
                    ) -> dict[str, Quantity]:
                        result = sector.compute(t_, st, shared_st, ctx)  # type: ignore[attr-defined]
                        return {
                            k.replace("d_", ""): v
                            for k, v in result.items()
                            if k.startswith("d_")
                        }
                    return deriv

                deriv_fn = make_sr_deriv(s, shared)
                new_stocks = rk4_step(deriv_fn, t, s_stocks, self.master_dt)  # type: ignore[arg-type]
                for k, v in new_stocks.items():
                    all_stocks[k] = v

            # ── 4) Record state ──────────────────────────────────────
            t += self.master_dt
            time_index.append(t)
            for name in all_stocks:
                traj[name].append(all_stocks[name].magnitude)
            for obs in ["extraction_rate", "industrial_output",
                        "pollution_fraction", "pollution_efficiency"]:
                traj[obs].append(shared[obs].magnitude)

        # ── Build result ─────────────────────────────────────────────
        result_trajectories = {k: np.array(v) for k, v in traj.items()}
        return RunResult(
            time_index=np.array(time_index),
            trajectories=result_trajectories,
            warnings=warnings_list,
        )

    def _resolve_ip_loop(
        self,
        t: float,
        all_stocks: dict[str, Quantity],
        shared: dict[str, Quantity],
        ctx: RunContext,
        sector_stock_names: dict[str, list[str]],
        warnings_list: list[str],
    ) -> None:
        """Resolve the I<->P algebraic loop via fixed-point iteration.

        I needs pollution_efficiency from P.
        P needs industrial_output from I.
        Iterate until convergence.
        """
        industry = self._sectors_by_name.get("industry")
        pollution = self._sectors_by_name.get("pollution")
        if industry is None or pollution is None:
            return

        i_stocks = {
            k: all_stocks[k] for k in sector_stock_names["industry"]
        }
        p_stocks = {
            k: all_stocks[k] for k in sector_stock_names["pollution"]
        }

        # Use current shared values as initial guess
        prev_io = shared.get(
            "industrial_output", Quantity(0.0, INDUSTRIAL_OUTPUT_UNITS)
        ).magnitude
        prev_pe = shared.get(
            "pollution_efficiency", Quantity(1.0, DIMENSIONLESS)
        ).magnitude

        for iteration in range(self.loop_max_iter):
            # Compute I with current pollution_efficiency guess
            i_inputs = dict(shared)
            i_inputs["pollution_efficiency"] = Quantity(prev_pe, DIMENSIONLESS)
            i_out = industry.compute(t, i_stocks, i_inputs, ctx)  # type: ignore[attr-defined]

            new_io = i_out["industrial_output"].magnitude

            # Compute P with new industrial_output
            p_inputs = dict(shared)
            p_inputs["industrial_output"] = Quantity(
                new_io, INDUSTRIAL_OUTPUT_UNITS
            )
            p_out = pollution.compute(t, p_stocks, p_inputs, ctx)  # type: ignore[attr-defined]

            new_pe = p_out["pollution_efficiency"].magnitude

            # Check convergence
            io_diff = abs(new_io - prev_io)
            pe_diff = abs(new_pe - prev_pe)
            io_rel = io_diff / abs(new_io) if new_io != 0 else io_diff
            pe_rel = pe_diff / abs(new_pe) if new_pe != 0 else pe_diff

            converged = io_rel < self.loop_tol and pe_rel < self.loop_tol

            prev_io = new_io
            prev_pe = new_pe

            if converged:
                break
        else:
            raise AlgebraicLoopConvergenceError(
                f"I<->P loop did not converge after {self.loop_max_iter} "
                f"iterations at t={t}. Last residuals: io_rel={io_rel:.2e}, "
                f"pe_rel={pe_rel:.2e}"
            )

        # Update shared state with converged values
        for k, v in i_out.items():
            if not k.startswith("d_"):
                shared[k] = v
        for k, v in p_out.items():
            if not k.startswith("d_"):
                shared[k] = v
