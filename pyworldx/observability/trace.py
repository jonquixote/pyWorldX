"""Trace module (Section 12 — spec-required filename alias).

Re-exports from tracing.py.
"""

from pyworldx.observability.tracing import (
    CausalTrace,
    CausalTraceRef,
    SnapshotRingBuffer,
    StaleTraceRefError,
    TraceCollector,
    TraceLevel,
)

__all__ = [
    "CausalTrace",
    "CausalTraceRef",
    "SnapshotRingBuffer",
    "StaleTraceRefError",
    "TraceCollector",
    "TraceLevel",
]
