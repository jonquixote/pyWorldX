"""Tests for the generalized algebraic loop solver."""

from __future__ import annotations

import pytest

from pyworldx.core.loops import (
    AlgebraicLoopConvergenceError,
    resolve_algebraic_loop,
)
from pyworldx.core.quantities import DIMENSIONLESS, Quantity
from pyworldx.sectors.base import RunContext


# ── Mock sectors for loop testing ────────────────────────────────────────

class ContractiveSectorA:
    """out_a = 0.5 * out_b + 1.0  →  converges to a=2, b=1."""
    name = "loop_a"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        b = inputs.get("out_b", Quantity(0.0, DIMENSIONLESS)).magnitude
        return {"out_a": Quantity(0.5 * b + 1.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [{"name": "ab_loop", "variables": ["out_a", "out_b"],
                 "solver": "fixed_point", "tol": 1e-12, "max_iter": 200}]

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": []}

    def declares_reads(self) -> list[str]:
        return ["out_b"]

    def declares_writes(self) -> list[str]:
        return ["out_a"]


class ContractiveSectorB:
    """out_b = 0.3 * out_a  →  converges to a≈1.176, b≈0.353."""
    name = "loop_b"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        a = inputs.get("out_a", Quantity(0.0, DIMENSIONLESS)).magnitude
        return {"out_b": Quantity(0.3 * a, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [{"name": "ab_loop", "variables": ["out_a", "out_b"],
                 "solver": "fixed_point", "tol": 1e-12, "max_iter": 200}]

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": []}

    def declares_reads(self) -> list[str]:
        return ["out_a"]

    def declares_writes(self) -> list[str]:
        return ["out_b"]


class DivergentSectorA:
    """out_a = 2.0 * out_b + 1.0  →  diverges (Lipschitz > 1)."""
    name = "div_a"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        b = inputs.get("out_b", Quantity(0.0, DIMENSIONLESS)).magnitude
        return {"out_a": Quantity(2.0 * b + 1.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": []}

    def declares_reads(self) -> list[str]:
        return ["out_b"]

    def declares_writes(self) -> list[str]:
        return ["out_a"]


class DivergentSectorB:
    """out_b = 2.0 * out_a  →  diverges."""
    name = "div_b"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        a = inputs.get("out_a", Quantity(0.0, DIMENSIONLESS)).magnitude
        return {"out_b": Quantity(2.0 * a, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": []}

    def declares_reads(self) -> list[str]:
        return ["out_a"]

    def declares_writes(self) -> list[str]:
        return ["out_b"]


# ── Tests ────────────────────────────────────────────────────────────────

class TestAlgebraicLoopSolver:
    def test_contractive_loop_converges(self) -> None:
        """Two contractive sectors converge to fixed point."""
        a, b = ContractiveSectorA(), ContractiveSectorB()
        shared: dict[str, Quantity] = {
            "out_a": Quantity(0.0, DIMENSIONLESS),
            "out_b": Quantity(0.0, DIMENSIONLESS),
        }
        ctx = RunContext()

        result = resolve_algebraic_loop(
            loop_sectors=[a, b],
            sector_stock_map={"loop_a": {}, "loop_b": {}},
            shared=shared,
            t=0.0,
            ctx=ctx,
            tol=1e-12,
            max_iter=200,
            loop_name="ab_test",
        )

        assert result.converged
        assert result.iterations < 50  # should converge quickly

        # Analytical fixed point: a = 0.5b + 1, b = 0.3a
        # → a = 0.15a + 1 → a = 1/0.85 ≈ 1.17647
        # → b = 0.3/0.85 ≈ 0.35294
        assert abs(shared["out_a"].magnitude - 1.0 / 0.85) < 1e-10
        assert abs(shared["out_b"].magnitude - 0.3 / 0.85) < 1e-10

    def test_divergent_loop_raises(self) -> None:
        """Divergent loop should raise AlgebraicLoopConvergenceError."""
        a, b = DivergentSectorA(), DivergentSectorB()
        shared: dict[str, Quantity] = {
            "out_a": Quantity(1.0, DIMENSIONLESS),
            "out_b": Quantity(1.0, DIMENSIONLESS),
        }
        ctx = RunContext()

        with pytest.raises(AlgebraicLoopConvergenceError):
            resolve_algebraic_loop(
                loop_sectors=[a, b],
                sector_stock_map={"div_a": {}, "div_b": {}},
                shared=shared,
                t=0.0,
                ctx=ctx,
                tol=1e-10,
                max_iter=10,
                loop_name="divergent_test",
            )

    def test_loop_result_diagnostics(self) -> None:
        """LoopResult should report correct sector names and variables."""
        a, b = ContractiveSectorA(), ContractiveSectorB()
        shared: dict[str, Quantity] = {
            "out_a": Quantity(0.0, DIMENSIONLESS),
            "out_b": Quantity(0.0, DIMENSIONLESS),
        }
        ctx = RunContext()

        result = resolve_algebraic_loop(
            loop_sectors=[a, b],
            sector_stock_map={"loop_a": {}, "loop_b": {}},
            shared=shared,
            t=5.0,
            ctx=ctx,
            loop_name="diag_test",
        )

        assert result.name == "diag_test"
        assert result.sector_names == ["loop_a", "loop_b"]
        assert "out_a" in result.variables
        assert "out_b" in result.variables
        assert result.final_residual < 1e-10

    def test_damped_iteration(self) -> None:
        """Damped iteration with factor < 1 should also converge."""
        a, b = ContractiveSectorA(), ContractiveSectorB()
        shared: dict[str, Quantity] = {
            "out_a": Quantity(0.0, DIMENSIONLESS),
            "out_b": Quantity(0.0, DIMENSIONLESS),
        }
        ctx = RunContext()

        result = resolve_algebraic_loop(
            loop_sectors=[a, b],
            sector_stock_map={"loop_a": {}, "loop_b": {}},
            shared=shared,
            t=0.0,
            ctx=ctx,
            damping=0.5,
            loop_name="damped_test",
        )

        assert result.converged
        # Damping slows convergence, so more iterations are expected
        assert abs(shared["out_a"].magnitude - 1.0 / 0.85) < 1e-8

    def test_canonical_ip_loop(self) -> None:
        """The I<->P loop from canonical sectors should converge."""
        from pyworldx.sectors.rip_sectors import IndustrySector, PollutionSector

        i_sector = IndustrySector()
        p_sector = PollutionSector()
        shared: dict[str, Quantity] = {
            "extraction_rate": Quantity(100.0, "resource_units"),
            "industrial_output": Quantity(50.0, "industrial_output_units"),
            "pollution_fraction": Quantity(0.0, DIMENSIONLESS),
            "pollution_efficiency": Quantity(1.0, DIMENSIONLESS),
        }
        ctx = RunContext()

        result = resolve_algebraic_loop(
            loop_sectors=[i_sector, p_sector],
            sector_stock_map={
                "industry": {"K": Quantity(100.0, "capital_units")},
                "pollution": {"P": Quantity(10.0, "pollution_units")},
            },
            shared=shared,
            t=0.0,
            ctx=ctx,
            tol=1e-10,
            max_iter=100,
            loop_name="ip_canonical",
        )

        assert result.converged
        assert shared["industrial_output"].magnitude > 0
        assert shared["pollution_efficiency"].magnitude > 0
        assert shared["pollution_efficiency"].magnitude <= 1.0
