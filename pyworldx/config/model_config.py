"""Model configuration (Section 3.2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Top-level model configuration."""

    master_dt: float = 1.0
    t_start: float = 0.0
    t_end: float = 200.0
    integrator: str = "rk4"
    loop_tol: float = 1e-10
    loop_max_iter: int = 100
    balance_warn_tol: float = 1e-6
    balance_fail_tol: float = 1e-3
    trace_level: str = "OFF"
    trace_ring_buffer_size: int = 2
