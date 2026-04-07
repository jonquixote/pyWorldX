"""Tests for ontology registry."""

from __future__ import annotations

import pytest

from pyworldx.ontology.registry import (
    DuplicateWriteError,
    OntologyRegistry,
    UnknownVariableError,
    VariableEntry,
    VariableRole,
    build_world3_registry,
)


class TestOntologyRegistry:
    def test_register_and_lookup(self) -> None:
        reg = OntologyRegistry()
        entry = VariableEntry(
            "test.var", "meters", VariableRole.STOCK, "test_sector"
        )
        reg.register(entry)
        result = reg.lookup("test.var")
        assert result.name == "test.var"
        assert result.unit_family == "meters"

    def test_duplicate_write_different_sector_raises(self) -> None:
        reg = OntologyRegistry()
        reg.register(
            VariableEntry("x", "m", VariableRole.STOCK, "sector_a")
        )
        with pytest.raises(DuplicateWriteError):
            reg.register(
                VariableEntry("x", "m", VariableRole.STOCK, "sector_b")
            )

    def test_duplicate_write_same_sector_ok(self) -> None:
        reg = OntologyRegistry()
        reg.register(
            VariableEntry("x", "m", VariableRole.STOCK, "sector_a")
        )
        reg.register(
            VariableEntry("x", "m", VariableRole.STOCK, "sector_a")
        )
        assert reg.size == 1

    def test_unknown_variable_raises(self) -> None:
        reg = OntologyRegistry()
        with pytest.raises(UnknownVariableError):
            reg.lookup("nonexistent")

    def test_lookup_by_world3(self) -> None:
        reg = OntologyRegistry()
        reg.register(
            VariableEntry(
                "resources.nonrenewable",
                "resource_units",
                VariableRole.STOCK,
                "resources",
                world3_name="nonrenewable_resources",
            )
        )
        result = reg.lookup_by_world3("nonrenewable_resources")
        assert result is not None
        assert result.name == "resources.nonrenewable"

    def test_lookup_by_world3_missing(self) -> None:
        reg = OntologyRegistry()
        assert reg.lookup_by_world3("missing") is None

    def test_get_sector_variables(self) -> None:
        reg = OntologyRegistry()
        reg.register(VariableEntry("a", "m", VariableRole.STOCK, "s1"))
        reg.register(VariableEntry("b", "m", VariableRole.FLOW, "s1"))
        reg.register(VariableEntry("c", "m", VariableRole.STOCK, "s2"))
        vars_s1 = reg.get_sector_variables("s1")
        assert len(vars_s1) == 2
        assert all(v.sector_owner == "s1" for v in vars_s1)

    def test_build_world3_registry(self) -> None:
        reg = build_world3_registry()
        assert reg.size > 10

        # Spot-check key variables
        pop = reg.lookup("population.total")
        assert pop.role == VariableRole.STOCK
        assert pop.sector_owner == "population"

        nr = reg.lookup("resources.nonrenewable")
        assert nr.world3_name == "nonrenewable_resources"

    def test_validate_sector(self) -> None:
        """validate_sector should return warnings for unregistered writes."""
        reg = OntologyRegistry()
        reg.register(VariableEntry("x", "m", VariableRole.STOCK, "s1"))

        class FakeSector:
            name = "s1"
            def declares_writes(self) -> list[str]:
                return ["x", "unregistered_var"]

        warnings = reg.validate_sector(FakeSector())
        assert len(warnings) == 1
        assert "unregistered_var" in warnings[0]

    def test_register_mapping(self) -> None:
        reg = OntologyRegistry()
        reg.register_mapping(
            source_var="capital.total",
            target_vars=["capital.industrial", "capital.service"],
            weight_fn=lambda s, t: [0.6, 0.4],
            equation_source="test",
            notes="test mapping",
        )
        assert len(reg._mappings) == 1
