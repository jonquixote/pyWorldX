"""Comprehensive unit tests for ontology mappings."""

from __future__ import annotations

from pathlib import Path


from data_pipeline.alignment.map import (
    get_mappings,
    get_all_entities,
    get_source_ids_for_entity,
    ONTOLOGY_MAP,
)
from data_pipeline.storage.parquet_store import list_sources


class TestOntologyMapStructure:
    """Test ontology map structure."""

    def test_no_duplicate_keys(self):
        """ONTOLOGY_MAP should have no duplicate keys."""
        keys = list(ONTOLOGY_MAP.keys())
        assert len(keys) == len(set(keys)), f"Duplicate keys found: {[k for k in keys if keys.count(k) > 1]}"

    def test_all_mappings_have_entity(self):
        """All mappings should have a valid entity name."""
        for source_id, mappings in ONTOLOGY_MAP.items():
            for m in mappings:
                assert m.entity, f"{source_id}: missing entity"

    def test_all_mappings_have_year_or_transforms(self):
        """All mappings should have year_col OR transforms that handle year."""
        for source_id, mappings in ONTOLOGY_MAP.items():
            for m in mappings:
                # Some mappings (like IMF, Nebel) use transforms to parse data
                has_parse_transform = any(
                    t.name in ("imf_weo_parse", "nebel_2023_parse")
                    for t in m.transforms
                )
                if not has_parse_transform:
                    assert m.year_col is not None, f"{source_id}/{m.entity}: missing year_col"
                    assert m.value_col is not None, f"{source_id}/{m.entity}: missing value_col"


class TestGetMappings:
    """Test get_mappings function."""

    def test_exact_match(self):
        """Exact source ID should return mappings."""
        mappings = get_mappings("gcp_fossil_co2")
        assert len(mappings) > 0
        assert any(m.entity == "emissions.co2_fossil" for m in mappings)

    def test_prefix_match(self):
        """Prefix source ID should return mappings."""
        mappings = get_mappings("world_bank_SP.POP.TOTL")
        assert len(mappings) > 0
        assert any(m.entity == "population.total" for m in mappings)

    def test_unknown_source_returns_empty(self):
        """Unknown source should return empty list."""
        mappings = get_mappings("unknown_source")
        assert mappings == []

    def test_faostat_mappings(self):
        """FAOSTAT sources should have mappings."""
        for source in [
            "faostat_food_balance",
            "faostat_food_balance_historical",
            "faostat_oa_population",
            "faostat_rl_land_use",
            "faostat_rl_full",
            "faostat_mk_macro",
            "faostat_tcl_trade",
            "faostat_cp_consumer_prices",
            "faostat_fs_food_security",
            "faostat_pd_deflators",
            "faostat_em_emissions",
            "faostat_gt_totals",
            "faostat_gn_energy",
            "faostat_cb_nonfood",
            "faostat_cbh_nonfood",
        ]:
            mappings = get_mappings(source)
            assert len(mappings) > 0, f"Missing mapping for {source}"


class TestGetAllEntities:
    """Test get_all_entities function."""

    def test_returns_sorted_list(self):
        """Should return sorted list of unique entities."""
        entities = get_all_entities()
        assert isinstance(entities, list)
        assert entities == sorted(entities)
        assert len(entities) == len(set(entities))

    def test_key_entities_present(self):
        """Key calibration entities should be present."""
        entities = get_all_entities()
        required = [
            "population.total",
            "emissions.co2_fossil",
            "atmospheric.co2",
            "temperature.anomaly",
            "food.supply.kcal_per_capita",
        ]
        for entity in required:
            assert entity in entities, f"Missing required entity: {entity}"

    def test_emission_entities(self):
        """All emission entities should be present."""
        entities = get_all_entities()
        for prefix in ["emissions.", "energy."]:
            matching = [e for e in entities if e.startswith(prefix)]
            assert len(matching) > 0, f"No entities starting with {prefix}"


class TestGetSourceIdsForEntity:
    """Test get_source_ids_for_entity function."""

    def test_population_sources(self):
        """population.total should have multiple sources."""
        source_ids = get_source_ids_for_entity("population.total")
        assert len(source_ids) >= 1

    def test_co2_fossil_sources(self):
        """emissions.co2_fossil should have multiple sources."""
        source_ids = get_source_ids_for_entity("emissions.co2_fossil")
        assert len(source_ids) >= 1

    def test_unknown_entity_returns_empty(self):
        """Unknown entity should return empty list."""
        source_ids = get_source_ids_for_entity("unknown.entity")
        assert source_ids == []


class TestAllRawSourcesHaveMappings:
    """Ensure all raw sources have ontology mappings."""

    def test_all_raw_sources_mapped(self):
        """All raw sources should have at least one ontology mapping."""
        sources = list_sources(Path("data_pipeline/data/raw"))
        unmapped = [s for s in sources if not get_mappings(s)]
        assert not unmapped, f"Unmapped sources: {unmapped}"


class TestEntityMappingConsistency:
    """Test consistency of EntityMapping objects."""

    def test_all_world_mappings_have_country_col_or_filter(self):
        """World-filtered mappings should have country_col set somewhere."""
        for source_id, mappings in ONTOLOGY_MAP.items():
            for m in mappings:
                if m.country_filter == "world":
                    # Check if country_col is set on mapping or in aggregate_world kwargs
                    has_country_col = m.country_col is not None
                    has_aggregate_with_country_col = any(
                        t.name == "aggregate_world" and t.kwargs.get("country_col")
                        for t in m.transforms
                    )
                    has_filter = any(t.name == "filter_rows" for t in m.transforms)
                    assert has_country_col or has_aggregate_with_country_col or has_filter, (
                        f"{source_id}/{m.entity}: missing country_col for world filter"
                    )

    def test_transform_specs_valid(self):
        """All TransformSpec objects should have valid names."""
        valid_transforms = {
            "interpolate_annual",
            "aggregate_world",
            "unit_conversion",
            "filter_rows",
            "derive_per_capita",
            "imf_weo_parse",
            "nebel_2023_parse",
        }
        for source_id, mappings in ONTOLOGY_MAP.items():
            for m in mappings:
                for t in m.transforms:
                    assert t.name in valid_transforms, (
                        f"{source_id}/{m.entity}: unknown transform '{t.name}'"
                    )
