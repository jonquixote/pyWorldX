"""Test strict_bootstrap=True surfaces bootstrap errors; False preserves legacy behavior."""
from __future__ import annotations

import pytest

from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


class _BrokenSector:
    """Minimal BaseSector duck type that triggers KeyError on compute()."""

    name = "broken"
    version = "0.0.1"
    timestep_hint: float | None = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        _ = inputs["nonexistent_key"]  # always triggers KeyError
        return {}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"name": self.name, "version": self.version}

    def declares_reads(self) -> list[str]:
        return ["nonexistent_key"]

    def declares_writes(self) -> list[str]:
        return []


def test_strict_bootstrap_raises_on_missing_key() -> None:
    engine = Engine(
        sectors=[_BrokenSector()],
        strict_bootstrap=True,
        t_start=0.0,
        t_end=0.0,
        master_dt=1.0,
    )
    with pytest.raises(KeyError):
        engine.run()


def test_nonstrict_bootstrap_swallows_error() -> None:
    """Legacy behavior: bootstrap errors are silently swallowed."""
    engine = Engine(
        sectors=[_BrokenSector()],
        strict_bootstrap=False,
        t_start=0.0,
        t_end=0.0,
        master_dt=1.0,
    )
    engine.run()  # must not raise
