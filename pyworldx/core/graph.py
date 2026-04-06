"""Dependency graph construction, topological sort, and cycle detection.

Builds a directed graph from sector declares_reads/declares_writes,
produces a topological execution order for the acyclic remainder,
and detects algebraic loops (Section 6.2).

Multi-rate awareness (Section 6.4): edges crossing the multi-rate
boundary are delayed couplings, not simultaneous loops.  Sub-stepped
sectors always run first using frozen last-known values.  Cycle
detection only operates within the single-rate communication domain.

Cross-sector cycles that are not declared in any sector's
algebraic_loop_hints() raise UndeclaredAlgebraicLoopError at init.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


class UndeclaredAlgebraicLoopError(Exception):
    """Raised when a cross-sector cycle is detected that no sector declared."""


class CircularDependencyError(Exception):
    """Raised when topological sort fails due to unresolved cycles."""


@dataclass
class LoopInfo:
    """Describes a detected algebraic loop in the dependency graph."""

    name: str
    sector_names: list[str]
    variables: list[str]
    declared: bool  # True if matched to a sector's algebraic_loop_hints()
    solver: str = "fixed_point"
    tol: float = 1e-10
    max_iter: int = 100
    damping: float = 1.0  # 1.0 = no damping


@dataclass
class DependencyGraph:
    """Sector-level dependency graph with loop analysis.

    Attributes:
        sectors: list of sector objects
        edges: dict mapping sector_name -> set of sector_names it depends on
        execution_order: topological order (sub-stepped first, then single-rate)
        loops: detected algebraic loops (single-rate domain only)
        variable_to_writer: maps variable name -> sector name that writes it
        variable_to_readers: maps variable name -> list of sector names reading it
    """

    sectors: list[Any] = field(default_factory=list)
    edges: dict[str, set[str]] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    loops: list[LoopInfo] = field(default_factory=list)
    variable_to_writer: dict[str, str] = field(default_factory=dict)
    variable_to_readers: dict[str, list[str]] = field(default_factory=dict)


def build_dependency_graph(
    sectors: list[Any],
    sub_stepped_names: set[str] | None = None,
) -> DependencyGraph:
    """Build the sector dependency graph from declares_reads/writes.

    Args:
        sectors: list of sector objects implementing BaseSector protocol
        sub_stepped_names: set of sector names that are sub-stepped.
            Edges involving sub-stepped sectors are treated as delayed
            couplings per Section 6.4.

    Returns:
        DependencyGraph with edges, execution order, and detected loops.

    Raises:
        UndeclaredAlgebraicLoopError: if a cross-sector cycle is detected
            in the single-rate domain that no sector declared.
    """
    if sub_stepped_names is None:
        sub_stepped_names = set()

    graph = DependencyGraph(sectors=sectors)

    # Build variable -> writer mapping
    for s in sectors:
        for var in s.declares_writes():
            graph.variable_to_writer[var] = s.name

    # Build variable -> readers mapping
    for s in sectors:
        for var in s.declares_reads():
            if var not in graph.variable_to_readers:
                graph.variable_to_readers[var] = []
            graph.variable_to_readers[var].append(s.name)

    # Build full sector-level edges
    for s in sectors:
        graph.edges[s.name] = set()
    for s in sectors:
        for var in s.declares_reads():
            writer = graph.variable_to_writer.get(var)
            if writer is not None and writer != s.name:
                graph.edges[s.name].add(writer)

    # ── Single-rate domain edges (for cycle detection) ───────────────
    # Per Section 6.4: cycles crossing multi-rate boundaries are delayed
    # couplings, not simultaneous loops.  Only detect cycles among
    # single-rate sectors.
    single_rate_names = {s.name for s in sectors} - sub_stepped_names
    sr_edges: dict[str, set[str]] = {}
    for s_name in single_rate_names:
        sr_edges[s_name] = graph.edges[s_name] & single_rate_names

    # Collect declared loop hints
    declared_loops = _collect_declared_loops(sectors)

    # Detect cycles in single-rate domain only
    cycles = _find_cycles(sr_edges)

    # Match detected cycles against declarations
    graph.loops = _match_cycles_to_declarations(cycles, declared_loops, sectors)

    # Check for undeclared cross-sector cycles
    for loop in graph.loops:
        if not loop.declared:
            raise UndeclaredAlgebraicLoopError(
                f"Undeclared cross-sector algebraic loop detected: "
                f"sectors={loop.sector_names}, variables={loop.variables}. "
                f"Add algebraic_loop_hints() to the participating sectors."
            )

    # ── Topological sort ─────────────────────────────────────────────
    # Sub-stepped sectors always execute first (frozen inputs).
    # Single-rate sectors are sorted topologically with loop groups
    # collapsed into single nodes.
    loop_sector_sets = [set(loop.sector_names) for loop in graph.loops]
    graph.execution_order = _build_execution_order(
        all_edges=graph.edges,
        sub_stepped=sub_stepped_names,
        single_rate=single_rate_names,
        loop_groups=loop_sector_sets,
    )

    return graph


def _collect_declared_loops(
    sectors: list[Any],
) -> list[dict[str, Any]]:
    """Collect all algebraic_loop_hints from all sectors, deduplicated by name."""
    seen_names: set[str] = set()
    result: list[dict[str, Any]] = []
    for s in sectors:
        for hint in s.algebraic_loop_hints():
            name = str(hint.get("name", ""))
            if name and name not in seen_names:
                seen_names.add(name)
                hint_copy = dict(hint)
                hint_copy["_sector"] = s.name
                result.append(hint_copy)
    return result


def _find_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Find all simple cycles in the directed graph using DFS."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    on_stack: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> None:
        visited.add(node)
        on_stack.add(node)
        path.append(node)

        for neighbor in edges.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in on_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:]
                cycles.append(list(cycle))

        path.pop()
        on_stack.discard(node)

    for node in sorted(edges.keys()):
        if node not in visited:
            dfs(node)

    return cycles


def _match_cycles_to_declarations(
    cycles: list[list[str]],
    declared_loops: list[dict[str, Any]],
    sectors: list[Any],
) -> list[LoopInfo]:
    """Match detected cycles against sector-declared loop hints."""
    result: list[LoopInfo] = []
    matched_cycle_keys: set[str] = set()

    for cycle in cycles:
        cycle_key = ",".join(sorted(cycle))
        if cycle_key in matched_cycle_keys:
            continue
        matched_cycle_keys.add(cycle_key)

        # Find variables involved in this cycle
        cycle_vars: list[str] = []
        sector_map = {s.name: s for s in sectors}
        for s_name in cycle:
            if s_name not in sector_map:
                continue
            s = sector_map[s_name]
            for var in s.declares_reads():
                for other_s_name in cycle:
                    if other_s_name == s_name:
                        continue
                    if other_s_name not in sector_map:
                        continue
                    other_s = sector_map[other_s_name]
                    if var in other_s.declares_writes():
                        if var not in cycle_vars:
                            cycle_vars.append(var)

        # Try to match to a declaration
        matched = False
        for decl in declared_loops:
            decl_vars = set(decl.get("variables", []))
            if decl_vars & set(cycle_vars):
                result.append(LoopInfo(
                    name=str(decl.get("name", f"loop_{'_'.join(sorted(cycle))}")),
                    sector_names=list(cycle),
                    variables=cycle_vars,
                    declared=True,
                    solver=str(decl.get("solver", "fixed_point")),
                    tol=float(decl.get("tol", 1e-10)),
                    max_iter=int(decl.get("max_iter", 100)),
                ))
                matched = True
                break

        if not matched:
            result.append(LoopInfo(
                name=f"undeclared_loop_{'_'.join(sorted(cycle))}",
                sector_names=list(cycle),
                variables=cycle_vars,
                declared=False,
            ))

    return result


def _build_execution_order(
    all_edges: dict[str, set[str]],
    sub_stepped: set[str],
    single_rate: set[str],
    loop_groups: list[set[str]],
) -> list[str]:
    """Build execution order: sub-stepped first, then single-rate topologically.

    Sub-stepped sectors always execute first (they use frozen inputs from
    the previous master step).  Single-rate sectors are topologically
    sorted with loop groups collapsed into single nodes.
    """
    # Sub-stepped sectors go first (order among them doesn't matter
    # since they all use frozen values)
    order: list[str] = sorted(sub_stepped)

    if not single_rate:
        return order

    # Map single-rate sectors to their loop group (if any)
    sector_to_group: dict[str, int] = {}
    for i, group in enumerate(loop_groups):
        for s in group:
            sector_to_group[s] = i

    # Build collapsed graph for single-rate sectors
    collapsed_nodes: set[str] = set()
    for s_name in single_rate:
        if s_name in sector_to_group:
            collapsed_nodes.add(f"__group_{sector_to_group[s_name]}")
        else:
            collapsed_nodes.add(s_name)

    # collapsed_edges[node] = set of nodes that `node` depends on
    # (only within single-rate domain)
    collapsed_edges: dict[str, set[str]] = {n: set() for n in collapsed_nodes}
    for s_name in single_rate:
        node_key = (
            f"__group_{sector_to_group[s_name]}"
            if s_name in sector_to_group
            else s_name
        )
        for dep in all_edges.get(s_name, set()):
            if dep not in single_rate:
                continue  # Skip cross-rate dependencies
            dep_key = (
                f"__group_{sector_to_group[dep]}"
                if dep in sector_to_group
                else dep
            )
            if node_key != dep_key:
                collapsed_edges[node_key].add(dep_key)

    # Kahn's algorithm
    # Build forward graph: provides[dep] = set of nodes that depend on dep
    provides: dict[str, set[str]] = defaultdict(set)
    in_degree: dict[str, int] = {n: 0 for n in collapsed_nodes}
    for node, deps in collapsed_edges.items():
        for dep in deps:
            provides[dep].add(node)
            in_degree[node] += 1

    queue: deque[str] = deque(
        sorted(n for n in collapsed_nodes if in_degree[n] == 0)
    )
    topo_order: list[str] = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for successor in sorted(provides.get(node, set())):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    if len(topo_order) != len(collapsed_nodes):
        raise CircularDependencyError(
            f"Could not topologically sort single-rate sectors. "
            f"Sorted {len(topo_order)} of {len(collapsed_nodes)} nodes. "
            f"Remaining cycles may not be declared."
        )

    # Expand loop groups back to individual sector names
    for entry in topo_order:
        if entry.startswith("__group_"):
            group_idx = int(entry.replace("__group_", ""))
            order.extend(sorted(loop_groups[group_idx]))
        else:
            order.append(entry)

    return order
