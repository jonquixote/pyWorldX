"""Tests for causal tracing system."""

from __future__ import annotations

import pytest

from pyworldx.core.metadata import EquationSource
from pyworldx.core.quantities import Quantity
from pyworldx.observability.tracing import (
    CausalTraceRef,
    SnapshotRingBuffer,
    StaleTraceRefError,
    TraceCollector,
    TraceLevel,
)


class TestSnapshotRingBuffer:
    def test_store_and_get(self) -> None:
        buf = SnapshotRingBuffer(size=3)
        buf.store(0, {"x": 1.0})
        buf.store(1, {"x": 2.0})
        assert buf.get(0)["x"] == 1.0
        assert buf.get(1)["x"] == 2.0

    def test_fifo_eviction(self) -> None:
        buf = SnapshotRingBuffer(size=2)
        buf.store(0, {"x": 1.0})
        buf.store(1, {"x": 2.0})
        buf.store(2, {"x": 3.0})  # evicts step 0
        with pytest.raises(StaleTraceRefError) as exc_info:
            buf.get(0)
        assert exc_info.value.step_index == 0
        assert exc_info.value.buffer_window == (1, 2)

    def test_window(self) -> None:
        buf = SnapshotRingBuffer(size=2)
        assert buf.window == (0, -1)  # empty
        buf.store(5, {})
        buf.store(6, {})
        assert buf.window == (5, 6)

    def test_contains(self) -> None:
        buf = SnapshotRingBuffer(size=2)
        buf.store(0, {})
        assert buf.contains(0)
        assert not buf.contains(1)

    def test_size_validation(self) -> None:
        with pytest.raises(ValueError):
            SnapshotRingBuffer(size=0)

    def test_len(self) -> None:
        buf = SnapshotRingBuffer(size=3)
        assert len(buf) == 0
        buf.store(0, {})
        assert len(buf) == 1


class TestCausalTraceRef:
    def test_render_with_buffer(self) -> None:
        buf = SnapshotRingBuffer(size=5)
        buf.store(0, {
            "io": Quantity(1000.0, "industrial_output_units"),
            "pe": Quantity(0.9, "dimensionless"),
        })

        ref = CausalTraceRef(
            variable="pollution_fraction",
            t=1.0,
            raw_value=0.5,
            unit="dimensionless",
            upstream_keys=["io", "pe"],
            state_snapshot_ref=0,
            equation_source=EquationSource.MEADOWS_SPEC,
            sector="pollution",
            loop_resolved=True,
        )

        # Create a mock run result with the buffer
        class MockResult:
            _snapshot_buffer = buf

        trace = ref.render(MockResult())
        assert trace.variable == "pollution_fraction"
        assert trace.value.magnitude == 0.5
        assert "io" in trace.upstream_inputs
        assert trace.upstream_inputs["io"].magnitude == 1000.0
        assert trace.loop_resolved is True

    def test_render_stale_raises(self) -> None:
        buf = SnapshotRingBuffer(size=1)
        buf.store(0, {})
        buf.store(1, {})  # evicts step 0

        ref = CausalTraceRef(
            variable="x", t=0.0, raw_value=1.0, unit="m",
            upstream_keys=[], state_snapshot_ref=0,
            equation_source=EquationSource.MEADOWS_SPEC,
            sector="test", loop_resolved=False,
        )

        class MockResult:
            _snapshot_buffer = buf

        with pytest.raises(StaleTraceRefError):
            ref.render(MockResult())


class TestTraceCollector:
    def test_off_level_ignores(self) -> None:
        tc = TraceCollector(level=TraceLevel.OFF)
        ref = CausalTraceRef(
            "x", 0.0, 1.0, "m", [], 0,
            EquationSource.MEADOWS_SPEC, "s", False,
        )
        tc.emit(ref)
        assert len(tc.refs) == 0

    def test_full_level_collects(self) -> None:
        tc = TraceCollector(level=TraceLevel.FULL)
        ref = CausalTraceRef(
            "x", 0.0, 1.0, "m", [], 0,
            EquationSource.MEADOWS_SPEC, "s", False,
        )
        tc.emit(ref)
        assert len(tc.refs) == 1

    def test_get_refs_for_variable(self) -> None:
        tc = TraceCollector(level=TraceLevel.FULL)
        tc.emit(CausalTraceRef(
            "x", 0.0, 1.0, "m", [], 0,
            EquationSource.MEADOWS_SPEC, "s", False,
        ))
        tc.emit(CausalTraceRef(
            "y", 0.0, 2.0, "m", [], 0,
            EquationSource.MEADOWS_SPEC, "s", False,
        ))
        assert len(tc.get_refs_for_variable("x")) == 1
        assert len(tc.get_refs_for_variable("y")) == 1

    def test_store_snapshot(self) -> None:
        tc = TraceCollector(level=TraceLevel.FULL)
        tc.store_snapshot(0, {"x": 1.0})
        assert tc.ring_buffer.contains(0)
