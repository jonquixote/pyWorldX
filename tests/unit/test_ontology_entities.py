"""Tests for ontology entities."""

from __future__ import annotations

from pyworldx.ontology.entities import (
    AggregationSemantic,
    CANONICAL_ENTITIES,
    Dimension,
    OntologyEntity,
)


class TestCanonicalEntities:
    def test_populated(self) -> None:
        assert len(CANONICAL_ENTITIES) >= 15

    def test_required_fields(self) -> None:
        for name, entity in CANONICAL_ENTITIES.items():
            assert entity.name == name
            assert isinstance(entity.dimension, Dimension)
            assert isinstance(entity.unit_family, str) and entity.unit_family
            assert isinstance(entity.role, str) and entity.role
            assert isinstance(entity.description, str) and entity.description

    def test_known_entities_exist(self) -> None:
        assert "population.total" in CANONICAL_ENTITIES
        assert "resources.nonrenewable_stock" in CANONICAL_ENTITIES
        assert "welfare.index" in CANONICAL_ENTITIES

    def test_population_total(self) -> None:
        e = CANONICAL_ENTITIES["population.total"]
        assert e.dimension == Dimension.PEOPLE
        assert e.unit_family == "people"
        assert e.role == "stock"

    def test_welfare_index(self) -> None:
        e = CANONICAL_ENTITIES["welfare.index"]
        assert e.dimension == Dimension.WELFARE
        assert e.aggregation == AggregationSemantic.WEIGHTED_MEAN

    def test_entity_is_frozen(self) -> None:
        e = CANONICAL_ENTITIES["population.total"]
        try:
            e.name = "changed"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestDimensionEnum:
    def test_members_exist(self) -> None:
        assert Dimension.PEOPLE.value == "people"
        assert Dimension.CAPITAL.value == "capital"
        assert Dimension.RESOURCE.value == "resource"
        assert Dimension.POLLUTION.value == "pollution"
        assert Dimension.FOOD.value == "food"
        assert Dimension.DIMENSIONLESS.value == "dimensionless"

    def test_all_members_are_strings(self) -> None:
        for member in Dimension:
            assert isinstance(member.value, str)


class TestAggregationSemanticEnum:
    def test_members_exist(self) -> None:
        assert AggregationSemantic.SUM.value == "sum"
        assert AggregationSemantic.MEAN.value == "mean"
        assert AggregationSemantic.WEIGHTED_MEAN.value == "weighted_mean"
        assert AggregationSemantic.NOT_AGGREGABLE.value == "not_aggregable"
