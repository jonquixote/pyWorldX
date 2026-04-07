"""Causal tracing system (Section 12.1–12.2).

Two-type pattern:
- CausalTraceRef: lightweight, emitted during run at zero materialization cost
- CausalTrace: fully materialized form, produced by .render()

Ring buffer contract:
- Configurable size (default 2)
- FIFO eviction
- StaleTraceRefError on expired snapshot refs
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyworldx.core.metadata import EquationSource
from pyworldx.core.quantities import Quantity


class TraceLevel(Enum):
    """Trace emission levels (Section 12.1)."""

    OFF = "off"
    SUMMARY = "summary"
    FULL = "full"


class StaleTraceRefError(Exception):
    """Raised when a CausalTraceRef references an evicted snapshot."""

    def __init__(self, step_index: int, buffer_window: tuple[int, int]) -> None:
        self.step_index = step_index
        self.buffer_window = buffer_window
        super().__init__(
            f"Snapshot at step {step_index} has been evicted. "
            f"Current buffer window: steps {buffer_window[0]}–{buffer_window[1]}. "
            f"Increase trace_ring_buffer_size or render refs within the buffer window."
        )


@dataclass
class CausalTraceRef:
    """Lightweight trace reference emitted during run (Section 12.2).

    Stores indices and keys only — zero materialization cost.
    """

    variable: str
    t: float
    raw_value: float
    unit: str
    upstream_keys: list[str]
    state_snapshot_ref: int  # absolute step index
    equation_source: EquationSource
    sector: str
    loop_resolved: bool

    def render(self, run_result: Any) -> CausalTrace:
        """Materialize this ref into a full CausalTrace.

        Uses the run_result's snapshot ring buffer to resolve
        upstream input values.

        Raises:
            StaleTraceRefError: if the referenced snapshot has been evicted
        """
        ring_buffer: SnapshotRingBuffer = getattr(
            run_result, "_snapshot_buffer", SnapshotRingBuffer(size=2)
        )

        snapshot = ring_buffer.get(self.state_snapshot_ref)

        # Resolve upstream inputs from snapshot
        upstream_inputs: dict[str, Quantity] = {}
        for key in self.upstream_keys:
            if key in snapshot:
                val = snapshot[key]
                if isinstance(val, Quantity):
                    upstream_inputs[key] = val
                else:
                    upstream_inputs[key] = Quantity(float(val), "unknown")

        return CausalTrace(
            variable=self.variable,
            t=self.t,
            value=Quantity(self.raw_value, self.unit),
            upstream_inputs=upstream_inputs,
            equation_source=self.equation_source,
            sector=self.sector,
            loop_resolved=self.loop_resolved,
        )


@dataclass
class CausalTrace:
    """Fully materialized causal trace (Section 12.2).

    Produced by calling .render() on a CausalTraceRef.
    """

    variable: str
    t: float
    value: Quantity
    upstream_inputs: dict[str, Quantity]
    equation_source: EquationSource
    sector: str
    loop_resolved: bool


class SnapshotRingBuffer:
    """Ring buffer for state snapshots (Section 12.2).

    Contract:
    - Size configurable via RunConfig.trace_ring_buffer_size (default 2)
    - FIFO eviction — oldest snapshot evicted first
    - Index validity checked on access; StaleTraceRefError on eviction
    """

    def __init__(self, size: int = 2) -> None:
        if size < 1:
            raise ValueError("Ring buffer size must be >= 1")
        self._size = size
        self._buffer: deque[tuple[int, dict[str, Any]]] = deque(maxlen=size)
        self._min_step: int = 0
        self._max_step: int = -1

    @property
    def size(self) -> int:
        return self._size

    @property
    def window(self) -> tuple[int, int]:
        """Return (min_step, max_step) currently in buffer."""
        if not self._buffer:
            return (0, -1)
        return (self._buffer[0][0], self._buffer[-1][0])

    def store(self, step_index: int, snapshot: dict[str, Any]) -> None:
        """Store a snapshot at the given step index."""
        self._buffer.append((step_index, dict(snapshot)))
        self._max_step = step_index
        if len(self._buffer) == 1:
            self._min_step = step_index
        else:
            self._min_step = self._buffer[0][0]

    def get(self, step_index: int) -> dict[str, Any]:
        """Retrieve snapshot at step_index.

        Raises StaleTraceRefError if the step has been evicted.
        """
        for stored_step, snapshot in self._buffer:
            if stored_step == step_index:
                return snapshot

        window = self.window
        raise StaleTraceRefError(step_index, window)

    def contains(self, step_index: int) -> bool:
        """Check if a step index is still in the buffer."""
        return any(s == step_index for s, _ in self._buffer)

    def __len__(self) -> int:
        return len(self._buffer)


@dataclass
class TraceCollector:
    """Collects CausalTraceRefs during a run.

    Used by the engine when trace level is SUMMARY or FULL.
    """

    level: TraceLevel = TraceLevel.OFF
    refs: list[CausalTraceRef] = field(default_factory=list)
    ring_buffer: SnapshotRingBuffer = field(
        default_factory=lambda: SnapshotRingBuffer(size=2)
    )

    def emit(self, ref: CausalTraceRef) -> None:
        """Emit a trace ref if tracing is enabled."""
        if self.level == TraceLevel.OFF:
            return
        if self.level == TraceLevel.SUMMARY:
            # Only collect sector-level summaries (first variable per sector per step)
            return
        self.refs.append(ref)

    def store_snapshot(
        self, step_index: int, state: dict[str, Any]
    ) -> None:
        """Store a state snapshot in the ring buffer."""
        if self.level != TraceLevel.OFF:
            self.ring_buffer.store(step_index, state)

    def get_refs_for_variable(
        self, variable: str
    ) -> list[CausalTraceRef]:
        """Get all trace refs for a specific variable."""
        return [r for r in self.refs if r.variable == variable]

    def get_refs_at_time(self, t: float) -> list[CausalTraceRef]:
        """Get all trace refs at a specific time."""
        return [r for r in self.refs if abs(r.t - t) < 1e-10]
