"""Tests for multi-rate scheduler and sub-stepping."""

from __future__ import annotations

import pytest

from pyworldx.core.multirate import (
    IncompatibleTimestepError,
    MultirateScheduler,
    resolve_substep_ratio,
)
from pyworldx.core.quantities import DIMENSIONLESS, Quantity
from pyworldx.sectors.base import RunContext


# ── Mock sectors ─────────────────────────────────────────────────────────

class FastSector:
    """Sub-stepped sector: simple exponential decay at dt=0.25."""
    name = "fast"
    version = "1.0"
    timestep_hint = 0.25

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"x": Quantity(100.0, DIMENSIONLESS)}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        x = stocks["x"].magnitude
        return {
            "d_x": Quantity(-0.1 * x, DIMENSIONLESS),
            "fast_obs": Quantity(x * 2.0, DIMENSIONLESS),
        }

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return []

    def declares_writes(self) -> list[str]:
        return ["x", "fast_obs"]


class SlowSector:
    """Single-rate sector."""
    name = "slow"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"y": Quantity(50.0, DIMENSIONLESS)}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        y = stocks["y"].magnitude
        return {"d_y": Quantity(-0.05 * y, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["fast_obs"]

    def declares_writes(self) -> list[str]:
        return ["y"]


class BadTimestepSector:
    """Sector with non-integer substep ratio."""
    name = "bad"
    version = "1.0"
    timestep_hint = 0.3  # 1.0 / 0.3 is not integer

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return []

    def declares_writes(self) -> list[str]:
        return []


# ── Tests ────────────────────────────────────────────────────────────────

class TestResolveSubstepRatio:
    def test_exact_4_to_1(self) -> None:
        assert resolve_substep_ratio(1.0, 0.25) == 4

    def test_exact_2_to_1(self) -> None:
        assert resolve_substep_ratio(1.0, 0.5) == 2

    def test_exact_1_to_1(self) -> None:
        assert resolve_substep_ratio(1.0, 1.0) == 1

    def test_exact_10_to_1(self) -> None:
        assert resolve_substep_ratio(1.0, 0.1) == 10

    def test_non_integer_ratio_raises(self) -> None:
        with pytest.raises(IncompatibleTimestepError):
            resolve_substep_ratio(1.0, 0.3)

    def test_near_integer_passes(self) -> None:
        # 1.0 / 0.25000000001 ≈ 3.99999999998 — within 1e-9 tol
        assert resolve_substep_ratio(1.0, 0.25000000001) == 4


class TestMultirateScheduler:
    def test_from_sectors(self) -> None:
        scheduler = MultirateScheduler.from_sectors(
            [FastSector(), SlowSector()], master_dt=1.0
        )
        assert scheduler.sector_ratios["fast"] == 4
        assert scheduler.sector_ratios["slow"] == 1

    def test_is_sub_stepped(self) -> None:
        scheduler = MultirateScheduler.from_sectors(
            [FastSector(), SlowSector()], master_dt=1.0
        )
        assert scheduler.is_sub_stepped("fast")
        assert not scheduler.is_sub_stepped("slow")

    def test_get_sub_stepped_sectors(self) -> None:
        sectors = [FastSector(), SlowSector()]
        scheduler = MultirateScheduler.from_sectors(sectors, 1.0)
        sub = scheduler.get_sub_stepped_sectors(sectors)
        assert len(sub) == 1
        assert sub[0].name == "fast"

    def test_get_single_rate_sectors(self) -> None:
        sectors = [FastSector(), SlowSector()]
        scheduler = MultirateScheduler.from_sectors(sectors, 1.0)
        sr = scheduler.get_single_rate_sectors(sectors)
        assert len(sr) == 1
        assert sr[0].name == "slow"

    def test_bad_timestep_raises(self) -> None:
        with pytest.raises(IncompatibleTimestepError):
            MultirateScheduler.from_sectors(
                [BadTimestepSector()], master_dt=1.0
            )

    def test_advance_sector_produces_result(self) -> None:
        """advance_sector should integrate and return SubstepRecord."""
        fast = FastSector()
        scheduler = MultirateScheduler.from_sectors([fast], master_dt=1.0)
        ctx = RunContext()
        stocks = fast.init_stocks(ctx)

        record = scheduler.advance_sector(
            sector=fast,
            t=0.0,
            stocks=stocks,
            frozen_inputs={},
            ctx=ctx,
            sector_stock_names=["x"],
        )

        assert record.sector_name == "fast"
        assert record.substep_ratio == 4
        assert record.sub_dt == 0.25
        # x should have decayed from 100 by ~exp(-0.1)
        x_final = record.final_stocks["x"].magnitude
        assert 80.0 < x_final < 100.0  # decayed but not zeroed

    def test_advance_sector_accuracy(self) -> None:
        """Sub-stepped RK4 at 4:1 should be more accurate than 1:1."""
        import math
        fast = FastSector()
        scheduler = MultirateScheduler.from_sectors([fast], master_dt=1.0)
        ctx = RunContext()
        stocks = fast.init_stocks(ctx)

        record = scheduler.advance_sector(
            sector=fast, t=0.0, stocks=stocks,
            frozen_inputs={}, ctx=ctx, sector_stock_names=["x"],
        )

        analytical = 100.0 * math.exp(-0.1)
        rel_err = abs(record.final_stocks["x"].magnitude - analytical) / analytical
        assert rel_err < 1e-8  # RK4 with 4 substeps on simple decay

    def test_canonical_resource_sector(self) -> None:
        """ResourceSector from canonical model should sub-step correctly."""
        from pyworldx.sectors.rip_sectors import ResourceSector

        r = ResourceSector()
        scheduler = MultirateScheduler.from_sectors([r], master_dt=1.0)

        assert scheduler.sector_ratios["resources"] == 4
        assert scheduler.is_sub_stepped("resources")
