"""Tests for adapter modules."""

from __future__ import annotations

import pytest

from pyworldx.adapters.base import VariableMapping
from pyworldx.adapters.wiliam_adapter import (
    WiliamAdapterConfig,
    WiliamEconomyAdapter,
)
from pyworldx.adapters.world3_adapter import World3Adapter


class TestWorld3AdapterTranslateName:
    def test_known_variable(self) -> None:
        adapter = World3Adapter()
        assert adapter.translate_name("Population") == "population.total"

    def test_another_known_variable(self) -> None:
        adapter = World3Adapter()
        assert (
            adapter.translate_name("Nonrenewable_Resources")
            == "resources.nonrenewable_stock"
        )

    def test_unknown_variable_raises(self) -> None:
        adapter = World3Adapter()
        with pytest.raises(KeyError, match="No mapping"):
            adapter.translate_name("Nonexistent_Variable")


class TestWorld3AdapterMappings:
    def test_get_mappings_returns_list(self) -> None:
        adapter = World3Adapter()
        mappings = adapter.get_mappings()
        assert isinstance(mappings, list)
        assert len(mappings) > 0
        assert all(isinstance(m, VariableMapping) for m in mappings)

    def test_nr_weight_fn_sums_to_one(self) -> None:
        state = {"NR": 7e11, "extraction_rate": 3e11}
        weights = World3Adapter._nr_weight_fn(state, 0.0)
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 1e-9

    def test_nr_weight_fn_zero_state(self) -> None:
        state = {"NR": 0.0, "extraction_rate": 0.0}
        weights = World3Adapter._nr_weight_fn(state, 0.0)
        assert weights == [1.0, 0.0]

    def test_validate_returns_list(self) -> None:
        adapter = World3Adapter()
        issues = adapter.validate()
        assert isinstance(issues, list)


class TestWiliamAdapterConfig:
    def test_defaults(self) -> None:
        config = WiliamAdapterConfig()
        assert config.substep_ratio == 4
        assert config.price_base_year == 2015
        assert config.price_base_currency == "EUR"


class TestWiliamEconomyAdapter:
    def test_timestep_hint_before_set(self) -> None:
        adapter = WiliamEconomyAdapter()
        assert adapter.timestep_hint is None

    def test_timestep_hint_after_set(self) -> None:
        adapter = WiliamEconomyAdapter()
        adapter.set_master_dt(1.0)
        assert adapter.timestep_hint == 0.25  # 1.0 / 4

    def test_timestep_hint_custom_ratio(self) -> None:
        config = WiliamAdapterConfig(substep_ratio=2)
        adapter = WiliamEconomyAdapter(config=config)
        adapter.set_master_dt(1.0)
        assert adapter.timestep_hint == 0.5

    def test_translate_name_known(self) -> None:
        adapter = WiliamEconomyAdapter()
        assert adapter.translate_name("GDP") == "capital.industrial_output"

    def test_translate_name_unknown_raises(self) -> None:
        adapter = WiliamEconomyAdapter()
        with pytest.raises(KeyError, match="No mapping for WILIAM"):
            adapter.translate_name("nonexistent")

    def test_get_mappings(self) -> None:
        adapter = WiliamEconomyAdapter()
        mappings = adapter.get_mappings()
        assert len(mappings) == len(adapter.NAME_MAP)
