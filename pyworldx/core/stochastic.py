"""Stochastic state management (Section 6.6).

Deterministic runs may omit it. Ensemble runs must record it.
Random perturbations use named streams, not ambient global RNG.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class StochasticState:
    """Tracks RNG state for reproducible ensemble runs."""

    master_seed: int
    stream_seeds: dict[str, int] = field(default_factory=dict)
    draws_used: dict[str, int] = field(default_factory=dict)

    def get_stream(self, name: str) -> np.random.Generator:
        """Get or create a named RNG stream."""
        if name not in self.stream_seeds:
            base_rng = np.random.default_rng(self.master_seed)
            name_hash = hash(name) & 0xFFFFFFFF
            self.stream_seeds[name] = int(
                base_rng.integers(0, 2**63, dtype=np.int64)
            ) ^ name_hash
            self.draws_used[name] = 0
        return np.random.default_rng(self.stream_seeds[name])

    def record_draws(self, stream_name: str, n: int) -> None:
        """Record that n draws were taken from a stream."""
        self.draws_used[stream_name] = (
            self.draws_used.get(stream_name, 0) + n
        )
