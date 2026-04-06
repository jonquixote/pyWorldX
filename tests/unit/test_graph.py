"""Tests for dependency graph, topological sort, and cycle detection."""

from __future__ import annotations

import pytest

from pyworldx.core.graph import (
    UndeclaredAlgebraicLoopError,
    build_dependency_graph,
)
from pyworldx.core.quantities import DIMENSIONLESS, Quantity
from pyworldx.sectors.base import RunContext


# ── Mock sectors for testing ─────────────────────────────────────────────

class MockSectorA:
    name = "sector_a"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"stock_a": Quantity(10.0, DIMENSIONLESS)}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {"d_stock_a": Quantity(-1.0, DIMENSIONLESS), "out_a": Quantity(5.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return []

    def declares_writes(self) -> list[str]:
        return ["stock_a", "out_a"]


class MockSectorB:
    name = "sector_b"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"stock_b": Quantity(20.0, DIMENSIONLESS)}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {"d_stock_b": Quantity(-0.5, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["out_a"]  # B depends on A

    def declares_writes(self) -> list[str]:
        return ["stock_b"]


class MockSectorC:
    """Creates cycle with B: C reads from B, B reads from A."""
    name = "sector_c"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"stock_c": Quantity(5.0, DIMENSIONLESS)}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {"d_stock_c": Quantity(0.1, DIMENSIONLESS), "out_c": Quantity(1.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["stock_b"]

    def declares_writes(self) -> list[str]:
        return ["stock_c", "out_c"]


class MockLoopSectorX:
    """Part of declared X<->Y loop."""
    name = "sector_x"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        val = inputs.get("out_y", Quantity(1.0, DIMENSIONLESS)).magnitude
        return {"out_x": Quantity(val * 0.9, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [{"name": "xy_loop", "variables": ["out_x", "out_y"],
                 "scope": "cross_sector", "solver": "fixed_point",
                 "tol": 1e-10, "max_iter": 50}]

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["out_y"]

    def declares_writes(self) -> list[str]:
        return ["out_x"]


class MockLoopSectorY:
    """Part of declared X<->Y loop."""
    name = "sector_y"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        val = inputs.get("out_x", Quantity(1.0, DIMENSIONLESS)).magnitude
        return {"out_y": Quantity(val * 0.8, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [{"name": "xy_loop", "variables": ["out_x", "out_y"],
                 "scope": "cross_sector", "solver": "fixed_point",
                 "tol": 1e-10, "max_iter": 50}]

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["out_x"]

    def declares_writes(self) -> list[str]:
        return ["out_y"]


class MockUndeclaredLoopP:
    """Creates undeclared cycle with Q."""
    name = "sector_p"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {"out_p": Quantity(1.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []  # NOT declared!

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["out_q"]

    def declares_writes(self) -> list[str]:
        return ["out_p"]


class MockUndeclaredLoopQ:
    """Creates undeclared cycle with P."""
    name = "sector_q"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {"out_q": Quantity(1.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []  # NOT declared!

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": [], "preferred_substep_integrator": "rk4"}

    def declares_reads(self) -> list[str]:
        return ["out_p"]

    def declares_writes(self) -> list[str]:
        return ["out_q"]


# ── Tests ────────────────────────────────────────────────────────────────

class TestDependencyGraph:
    def test_acyclic_graph_order(self) -> None:
        """A->B should produce order [A, B]."""
        graph = build_dependency_graph([MockSectorA(), MockSectorB()])
        assert graph.execution_order.index("sector_a") < graph.execution_order.index("sector_b")

    def test_no_loops_in_acyclic(self) -> None:
        graph = build_dependency_graph([MockSectorA(), MockSectorB()])
        assert len(graph.loops) == 0

    def test_edges_correct(self) -> None:
        graph = build_dependency_graph([MockSectorA(), MockSectorB()])
        assert "sector_a" in graph.edges["sector_b"]
        assert len(graph.edges["sector_a"]) == 0

    def test_variable_to_writer(self) -> None:
        graph = build_dependency_graph([MockSectorA(), MockSectorB()])
        assert graph.variable_to_writer["out_a"] == "sector_a"
        assert graph.variable_to_writer["stock_b"] == "sector_b"

    def test_declared_loop_detected(self) -> None:
        """X<->Y with declared hints should be detected and accepted."""
        graph = build_dependency_graph([MockLoopSectorX(), MockLoopSectorY()])
        assert len(graph.loops) == 1
        assert graph.loops[0].declared is True
        assert graph.loops[0].name == "xy_loop"

    def test_undeclared_loop_raises(self) -> None:
        """P<->Q without hints should raise UndeclaredAlgebraicLoopError."""
        with pytest.raises(UndeclaredAlgebraicLoopError):
            build_dependency_graph([MockUndeclaredLoopP(), MockUndeclaredLoopQ()])

    def test_canonical_rip_graph(self) -> None:
        """The R-I-P canonical model should produce correct graph."""
        from pyworldx.sectors.rip_sectors import (
            IndustrySector, PollutionSector, ResourceSector,
        )
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        sub_stepped = {"resources"}
        graph = build_dependency_graph(sectors, sub_stepped_names=sub_stepped)

        # R should be first (sub-stepped)
        assert graph.execution_order[0] == "resources"
        # I<->P loop should be detected
        assert len(graph.loops) == 1
        loop = graph.loops[0]
        assert set(loop.sector_names) == {"industry", "pollution"}
        assert loop.declared is True

    def test_multirate_boundary_not_a_loop(self) -> None:
        """R<->I crosses multi-rate boundary — should NOT be detected as loop."""
        from pyworldx.sectors.rip_sectors import (
            IndustrySector, PollutionSector, ResourceSector,
        )
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        sub_stepped = {"resources"}
        graph = build_dependency_graph(sectors, sub_stepped_names=sub_stepped)
        # Only I<->P loop, NOT R<->I
        for loop in graph.loops:
            assert "resources" not in loop.sector_names
