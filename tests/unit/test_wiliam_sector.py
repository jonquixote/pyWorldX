"""Tests for WILIAM economy sector."""

from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.wiliam.economy import (
    WiliamAdapterConfig,
    WiliamEconomySector,
)


def _make_ctx() -> RunContext:
    return RunContext()


class TestWiliamAdapterConfig:
    def test_defaults(self) -> None:
        config = WiliamAdapterConfig()
        assert config.substep_ratio == 4
        assert config.price_base_year == 2015
        assert config.price_base_currency == "EUR"

    def test_custom_values(self) -> None:
        config = WiliamAdapterConfig(
            substep_ratio=8,
            price_base_year=2020,
            price_base_currency="USD",
        )
        assert config.substep_ratio == 8
        assert config.price_base_year == 2020
        assert config.price_base_currency == "USD"


class TestWiliamEconomySectorTimestep:
    def test_timestep_hint_none_before_set(self) -> None:
        sector = WiliamEconomySector()
        assert sector.timestep_hint is None

    def test_timestep_hint_after_set(self) -> None:
        sector = WiliamEconomySector()
        sector.set_master_dt(1.0)
        expected = 1.0 / 4  # default substep_ratio = 4
        assert sector.timestep_hint == expected

    def test_timestep_hint_custom_ratio(self) -> None:
        config = WiliamAdapterConfig(substep_ratio=2)
        sector = WiliamEconomySector(config=config)
        sector.set_master_dt(1.0)
        assert sector.timestep_hint == 0.5


class TestWiliamEconomySectorStocks:
    def test_init_stocks_returns_wiliam_k(self) -> None:
        sector = WiliamEconomySector()
        stocks = sector.init_stocks(_make_ctx())
        assert "wiliam_K" in stocks
        assert isinstance(stocks["wiliam_K"], Quantity)
        assert stocks["wiliam_K"].magnitude == 5000.0


class TestWiliamEconomySectorCompute:
    def test_produces_d_wiliam_k(self) -> None:
        sector = WiliamEconomySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        result = sector.compute(0.0, stocks, {}, ctx)
        assert "d_wiliam_K" in result

    def test_produces_wiliam_output(self) -> None:
        sector = WiliamEconomySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        result = sector.compute(0.0, stocks, {}, ctx)
        assert "wiliam_output" in result
        assert result["wiliam_output"].magnitude > 0

    def test_produces_investment_and_military(self) -> None:
        sector = WiliamEconomySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        result = sector.compute(0.0, stocks, {}, ctx)
        assert "wiliam_investment" in result
        assert "wiliam_military_fraction" in result

    def test_all_outputs_are_quantities(self) -> None:
        sector = WiliamEconomySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        result = sector.compute(0.0, stocks, {}, ctx)
        for name, val in result.items():
            assert isinstance(val, Quantity), f"{name} is not a Quantity"


class TestWiliamEconomySectorMetadata:
    def test_has_preferred_substep_integrator(self) -> None:
        sector = WiliamEconomySector()
        meta = sector.metadata()
        assert "preferred_substep_integrator" in meta
        assert meta["preferred_substep_integrator"] == "rk4"

    def test_metadata_completeness(self) -> None:
        sector = WiliamEconomySector()
        meta = sector.metadata()
        required = [
            "validation_status",
            "equation_source",
            "world7_alignment",
            "approximations",
            "free_parameters",
            "conservation_groups",
            "observables",
            "unit_notes",
        ]
        for field in required:
            assert field in meta, f"Missing metadata field: {field}"
