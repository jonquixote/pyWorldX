"""pyWorldX simulation engine.

Orchestrates: sector initialization → dependency graph → algebraic
loop detection → multi-rate time loop with RK4 → loop resolution →
balance auditing → trajectory collection → RunResult.

Sprint 2: refactored to use general-purpose primitives from
graph.py, loops.py, multirate.py, and balance.py.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from pyworldx.core.balance import BalanceAuditor
from pyworldx.core.graph import DependencyGraph, build_dependency_graph
from pyworldx.core.integrators import rk4_step
from pyworldx.core.loops import LoopResult, resolve_algebraic_loop
from pyworldx.core.metadata import EquationSource
from pyworldx.core.multirate import (
    IncompatibleTimestepError,
    MultirateScheduler,
    resolve_substep_ratio,
)
from pyworldx.core.quantities import Quantity
from pyworldx.core.result import RunResult
from pyworldx.observability.manifest import build_manifest, finalize_manifest
from pyworldx.observability.tracing import (
    CausalTraceRef,
    SnapshotRingBuffer,
    TraceCollector,
    TraceLevel,
)
from pyworldx.core.central_registrar import CentralRegistrar
from pyworldx.sectors.base import RunContext

# Re-export for backward compatibility
__all__ = [
    "Engine",
    "IncompatibleTimestepError",
    "resolve_substep_ratio",
]


class Engine:
    """The pyWorldX simulation engine.

    Runs sectors through an RK4 integration loop with:
    - Automatic dependency graph construction and topological sort
    - Algebraic loop detection and fixed-point resolution
    - Multi-rate sub-stepping for fast sectors
    - Conservation balance auditing
    - NaN/inf guardrails
    """

    def __init__(
        self,
        sectors: list[Any],
        master_dt: float = 1.0,
        t_start: float = 0.0,
        t_end: float = 200.0,
        loop_tol: float = 1e-10,
        loop_max_iter: int = 100,
        balance_warn_tol: float = 1e-6,
        balance_fail_tol: float = 1e-3,
        trace_level: str = "OFF",
        trace_ring_buffer_size: int = 2,
        policy_applier: Callable[[dict[str, float], float], dict[str, float]] | None = None,
        exogenous_injector: Callable[[float], dict[str, float]] | None = None,
        central_registrar: CentralRegistrar | None = None,
        strict_bootstrap: bool = False,
    ) -> None:
        self.sectors = sectors
        self.master_dt = master_dt
        self.t_start = t_start
        self.t_end = t_end
        self.loop_tol = loop_tol
        self.loop_max_iter = loop_max_iter
        self.trace_level = TraceLevel(trace_level.lower())
        self.trace_ring_buffer_size = trace_ring_buffer_size
        self._policy_applier = policy_applier
        self._exogenous_injector = exogenous_injector
        self._central_registrar = central_registrar
        self._strict_bootstrap = strict_bootstrap

        # Build sector lookup
        self._sectors_by_name: dict[str, Any] = {
            s.name: s for s in self.sectors
        }

        # Build multi-rate scheduler FIRST (validates substep ratios at init)
        # Must come before graph so we know which sectors are sub-stepped
        self.scheduler: MultirateScheduler = MultirateScheduler.from_sectors(
            sectors, master_dt
        )

        # Backward-compatible substep_ratios attribute
        self.substep_ratios = self.scheduler.sector_ratios

        # Classify sectors
        self._sub_stepped = self.scheduler.get_sub_stepped_sectors(sectors)
        self._single_rate = self.scheduler.get_single_rate_sectors(sectors)

        # Identify sub-stepped sector names for graph builder
        sub_stepped_names = {s.name for s in self._sub_stepped}

        # Build dependency graph (detects loops in single-rate domain only)
        self.dep_graph: DependencyGraph = build_dependency_graph(
            sectors, sub_stepped_names=sub_stepped_names
        )

        # Balance auditor
        self._auditor = BalanceAuditor(
            warn_tol=balance_warn_tol,
            fail_tol=balance_fail_tol,
        )

    def run(self) -> RunResult:
        """Execute the full simulation and return structured results."""
        manifest = build_manifest(self.sectors)

        # Shared auxiliary/observable state (inter-sector communication)
        shared: dict[str, Quantity] = {}

        # Set known defaults before any sector runs
        shared["pollution_efficiency"] = Quantity(1.0, "dimensionless")

        ctx = RunContext(
            master_dt=self.master_dt,
            t_start=self.t_start,
            t_end=self.t_end,
            shared_state=shared,
        )

        # ── Seed exogenous overrides BEFORE init_stocks ──────────────────
        if self._exogenous_injector is not None:
            from pyworldx.data.bridge import _get_engine_var
            overrides = self._exogenous_injector(self.t_start)
            for ontology_name, val in overrides.items():
                engine_name = _get_engine_var(ontology_name) or ontology_name
                # Seed with placeholder 'dimensionless' since stocks haven't initialized units
                shared[engine_name] = Quantity(float(val), "dimensionless")

        # ── Initialize stocks ────────────────────────────────────────
        all_stocks: dict[str, Quantity] = {}
        sector_stock_names: dict[str, list[str]] = {}
        for s in self.sectors:
            sector_stocks = s.init_stocks(ctx)
            all_stocks.update(sector_stocks)
            sector_stock_names[s.name] = list(sector_stocks.keys())

        # Initialize shared state with defaults from all sector writes
        for s in self.sectors:
            for var in s.declares_writes():
                if var not in all_stocks and not var.startswith("d_"):
                    shared.setdefault(var, Quantity(0.0, "dimensionless"))

        # Seed stocks into shared so cross-sector stock reads work
        for k, v in all_stocks.items():
            shared[k] = v

        # ── Bootstrap: compute initial auxiliaries at t=0 ────────────
        self._bootstrap_initial_state(
            all_stocks, shared, sector_stock_names, ctx
        )

        # ── Collect all observable names for recording ───────────────
        obs_names: list[str] = []
        for s in self.sectors:
            for var in s.declares_writes():
                if var not in all_stocks and var not in obs_names:
                    obs_names.append(var)

        # ── Recording setup ──────────────────────────────────────────
        time_index: list[float] = [self.t_start]
        traj: dict[str, list[float]] = {}
        for name in all_stocks:
            traj[name] = [all_stocks[name].magnitude]
        for obs in obs_names:
            if obs in shared:
                traj[obs] = [shared[obs].magnitude]

        warnings_list: list[str] = []
        loop_diagnostics: list[LoopResult] = []

        # ── Trace collector ──────────────────────────────────────────
        collector = TraceCollector(
            level=self.trace_level,
            ring_buffer=SnapshotRingBuffer(size=self.trace_ring_buffer_size),
        )

        # ── Master time loop ─────────────────────────────────────────
        t = self.t_start
        steps = int(round((self.t_end - self.t_start) / self.master_dt))

        for step_idx in range(steps):
            # ── 0a) Apply policy events to shared state ─────────────
            if self._policy_applier is not None:
                shared_floats = {k: v.magnitude for k, v in shared.items()}
                shared_floats_out = self._policy_applier(shared_floats, t)
                for k, fval in shared_floats_out.items():
                    if k in shared and k not in all_stocks:
                        shared[k] = Quantity(fval, shared[k].unit)

            # ── 0b) Inject exogenous overrides into shared state ────
            if self._exogenous_injector is not None:
                overrides = self._exogenous_injector(t)
                from pyworldx.data.bridge import _get_engine_var
                for ontology_name, val in overrides.items():
                    engine_name = _get_engine_var(ontology_name) or ontology_name
                    if engine_name in shared:
                        shared[engine_name] = Quantity(
                            float(val), shared[engine_name].unit
                        )
                    else:
                        shared[engine_name] = Quantity(float(val), "dimensionless")

            # Snapshot stocks before step for balance auditing
            stocks_before = {k: Quantity(v.magnitude, v.unit) for k, v in all_stocks.items()}

            # ── 1) Sub-stepped sectors advance across master step ────
            for s in self._sub_stepped:
                record = self.scheduler.advance_sector(
                    sector=s,
                    t=t,
                    stocks=all_stocks,
                    frozen_inputs=dict(shared),
                    ctx=ctx,
                    sector_stock_names=sector_stock_names[s.name],
                )
                # Update global stocks
                for k, v in record.final_stocks.items():
                    all_stocks[k] = v
                # Update shared auxiliaries
                for k, v in record.auxiliaries.items():
                    shared[k] = v

            # ── 1b) CentralRegistrar: resolve demands, enforce ceiling ─
            if self._central_registrar is not None:
                self._central_registrar.resolve(shared)

            # ── 2) Resolve algebraic loops in single-rate domain ─────
            for loop_info in self.dep_graph.loops:
                loop_sectors = [
                    self._sectors_by_name[name]
                    for name in loop_info.sector_names
                    if not self.scheduler.is_sub_stepped(name)
                ]
                if not loop_sectors:
                    continue

                stock_map = {
                    s.name: {
                        k: all_stocks[k]
                        for k in sector_stock_names[s.name]
                    }
                    for s in loop_sectors
                }

                lr = resolve_algebraic_loop(
                    loop_sectors=loop_sectors,
                    sector_stock_map=stock_map,
                    shared=shared,
                    t=t + self.master_dt,
                    ctx=ctx,
                    tol=loop_info.tol,
                    max_iter=loop_info.max_iter,
                    damping=loop_info.damping,
                    loop_name=loop_info.name,
                )
                loop_diagnostics.append(lr)

            # ── 3) Integrate single-rate sector stocks via RK4 ───────
            flow_outputs: dict[str, dict[str, Quantity]] = {}
            for s in self._single_rate:
                s_stock_names = sector_stock_names[s.name]
                s_stocks = {k: all_stocks[k] for k in s_stock_names}

                # Capture flows for balance auditing
                current_flows = s.compute(t, s_stocks, shared, ctx)
                flow_outputs[s.name] = current_flows

                # Merge non-derivative outputs into shared so subsequent
                # sectors in this step see updated values (e.g. agriculture's
                # food_per_capita visible to population)
                for k, v in current_flows.items():
                    if not k.startswith("d_"):
                        shared[k] = v

                def _make_deriv(
                    sector: Any, shared_st: dict[str, Quantity], context: Any
                ) -> Any:
                    def deriv(
                        t_: float, st: dict[str, Quantity]
                    ) -> dict[str, Quantity]:
                        result = sector.compute(t_, st, shared_st, context)
                        return {
                            k.replace("d_", ""): v
                            for k, v in result.items()
                            if k.startswith("d_")
                        }
                    return deriv

                deriv_fn = _make_deriv(s, shared, ctx)
                new_stocks = rk4_step(deriv_fn, t, s_stocks, self.master_dt)
                for k, v in new_stocks.items():
                    all_stocks[k] = v
                    # Merge updated stocks into shared so other sectors
                    # (and next timestep) see current stock values
                    shared[k] = v

            # ── 4) Balance auditing ──────────────────────────────────
            self._auditor.audit_sectors(
                sectors=self.sectors,
                stocks_before=stocks_before,
                stocks_after=all_stocks,
                flow_outputs=flow_outputs,
                t=t + self.master_dt,
                dt=self.master_dt,
            )

            # ── 5) Trace snapshot ────────────────────────────────────
            collector.store_snapshot(step_idx, dict(shared))

            # Emit trace refs for sector outputs at FULL level
            if self.trace_level == TraceLevel.FULL:
                for s in self.sectors:
                    s_stocks = {
                        k: all_stocks[k]
                        for k in sector_stock_names[s.name]
                    }
                    out = s.compute(t + self.master_dt, s_stocks, shared, ctx)
                    meta = s.metadata()
                    eq_src_raw = meta.get(
                        "equation_source", "PLACEHOLDER"
                    )
                    if isinstance(eq_src_raw, EquationSource):
                        eq_src = eq_src_raw
                    else:
                        try:
                            eq_src = EquationSource(str(eq_src_raw).lower())
                        except ValueError:
                            eq_src = EquationSource.PLACEHOLDER
                    for var_name, val in out.items():
                        if not var_name.startswith("d_"):
                            ref = CausalTraceRef(
                                variable=var_name,
                                t=t + self.master_dt,
                                raw_value=val.magnitude,
                                unit=val.unit,
                                upstream_keys=s.declares_reads(),
                                state_snapshot_ref=step_idx,
                                equation_source=eq_src,
                                sector=s.name,
                                loop_resolved=False,
                            )
                            collector.emit(ref)

            # ── 6) Record state ──────────────────────────────────────
            t += self.master_dt
            time_index.append(t)
            for name in all_stocks:
                traj[name].append(all_stocks[name].magnitude)
            for obs in obs_names:
                if obs in shared:
                    traj[obs].append(shared[obs].magnitude)

        # ── Build result ─────────────────────────────────────────────
        result_trajectories = {k: np.array(v) for k, v in traj.items()}

        # Include balance audit summary in warnings
        audit_summary = self._auditor.summary()
        if audit_summary.get("WARN", 0) > 0:
            warnings_list.append(
                f"Balance auditor: {audit_summary['WARN']} WARN results"
            )
        if audit_summary.get("FAIL", 0) > 0:
            warnings_list.append(
                f"Balance auditor: {audit_summary['FAIL']} FAIL results"
            )

        finalize_manifest(manifest)

        return RunResult(
            time_index=np.array(time_index),
            trajectories=result_trajectories,
            warnings=warnings_list,
            balance_audits=[r.to_dict() for r in self._auditor.results],
            trace_ref=collector.refs if collector.refs else None,
            provenance=manifest.to_dict(),
        )

    def _bootstrap_initial_state(
        self,
        all_stocks: dict[str, Quantity],
        shared: dict[str, Quantity],
        sector_stock_names: dict[str, list[str]],
        ctx: RunContext,
    ) -> None:
        """Compute consistent initial auxiliaries at t=0.

        Without this, sectors with Cobb-Douglas or multiplicative coupling
        to initially-zero auxiliaries will produce zero output permanently.

        Strategy: seed initial guesses for auxiliary variables, then
        iterate: single-rate loop resolution → sub-stepped sectors →
        repeat until consistent.
        """
        # Seed an initial guess for industrial_output from K stock
        # io_guess = A * K^beta * er^(1-beta) * pe
        # With er=1 (guess), pe=1 → io = K^0.7
        if "K" in all_stocks:
            k0 = all_stocks["K"].magnitude
            io_guess = k0 ** 0.7  # A=1, er=1, pe=1
            shared["industrial_output"] = Quantity(
                io_guess, "industrial_output_units"
            )

        # Pass 1: Compute sub-stepped sectors with guessed inputs
        for s in self._sub_stepped:
            stocks = {k: all_stocks[k] for k in sector_stock_names[s.name]}
            try:
                out = s.compute(self.t_start, stocks, shared, ctx)
                for k, v in out.items():
                    if not k.startswith("d_"):
                        shared[k] = v
            except (KeyError, ZeroDivisionError):
                if self._strict_bootstrap:
                    raise

        # Pass 2: Resolve algebraic loops at t=0
        for loop_info in self.dep_graph.loops:
            loop_sectors = [
                self._sectors_by_name[name]
                for name in loop_info.sector_names
                if not self.scheduler.is_sub_stepped(name)
            ]
            if not loop_sectors:
                continue
            stock_map = {
                s.name: {k: all_stocks[k] for k in sector_stock_names[s.name]}
                for s in loop_sectors
            }
            resolve_algebraic_loop(
                loop_sectors=loop_sectors,
                sector_stock_map=stock_map,
                shared=shared,
                t=self.t_start,
                ctx=ctx,
                tol=self.loop_tol,
                max_iter=self.loop_max_iter,
                loop_name=f"{loop_info.name}_bootstrap",
            )

        # Pass 3: Compute ALL single-rate sectors to populate their outputs
        # (e.g. agriculture's food_per_capita) — not just loop sectors
        for s_name in self.dep_graph.execution_order:
            s = self._sectors_by_name.get(s_name)
            if s is None or self.scheduler.is_sub_stepped(s_name):
                continue
            stocks = {k: all_stocks[k] for k in sector_stock_names[s_name]}
            try:
                out = s.compute(self.t_start, stocks, shared, ctx)
                for k, v in out.items():
                    if not k.startswith("d_"):
                        shared[k] = v
            except (KeyError, ZeroDivisionError):
                if self._strict_bootstrap:
                    raise

        # Pass 3b: Re-compute sub-stepped sectors with converged values
        for s in self._sub_stepped:
            stocks = {k: all_stocks[k] for k in sector_stock_names[s.name]}
            try:
                out = s.compute(self.t_start, stocks, shared, ctx)
                for k, v in out.items():
                    if not k.startswith("d_"):
                        shared[k] = v
            except (KeyError, ZeroDivisionError):
                if self._strict_bootstrap:
                    raise

        # Pass 4: Final loop resolution with correct extraction_rate
        for loop_info in self.dep_graph.loops:
            loop_sectors = [
                self._sectors_by_name[name]
                for name in loop_info.sector_names
                if not self.scheduler.is_sub_stepped(name)
            ]
            if not loop_sectors:
                continue
            stock_map = {
                s.name: {k: all_stocks[k] for k in sector_stock_names[s.name]}
                for s in loop_sectors
            }
            resolve_algebraic_loop(
                loop_sectors=loop_sectors,
                sector_stock_map=stock_map,
                shared=shared,
                t=self.t_start,
                ctx=ctx,
                tol=self.loop_tol,
                max_iter=self.loop_max_iter,
                loop_name=f"{loop_info.name}_bootstrap_final",
            )

