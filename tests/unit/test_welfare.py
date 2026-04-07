"""Tests for the welfare sector."""

from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.welfare import WelfareSector


def _make_ctx() -> RunContext:
    return RunContext()


def _default_inputs() -> dict[str, Quantity]:
    """Provide realistic inputs for a baseline test."""
    return {
        "life_expectancy": Quantity(70.0, "years"),
        "industrial_output": Quantity(5e10, "industrial_output_units"),
        "service_output_per_capita": Quantity(200.0, "service_output_units"),
        "food_per_capita": Quantity(2.0, "food_units_per_person"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "POP": Quantity(5e9, "persons"),
    }


class TestWelfareSectorInitStocks:
    def test_returns_empty_dict(self) -> None:
        sector = WelfareSector()
        stocks = sector.init_stocks(_make_ctx())
        assert stocks == {}


class TestWelfareSectorCompute:
    def test_returns_required_keys(self) -> None:
        sector = WelfareSector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        assert "human_welfare_index" in result
        assert "ecological_footprint" in result

    def test_hwi_in_range(self) -> None:
        sector = WelfareSector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        hwi = result["human_welfare_index"].magnitude
        assert 0.0 <= hwi <= 1.0

    def test_hwi_components_returned(self) -> None:
        sector = WelfareSector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        assert "hwi_life_exp_component" in result
        assert "hwi_income_component" in result
        assert "hwi_education_component" in result

    def test_all_outputs_are_quantities(self) -> None:
        sector = WelfareSector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        for name, val in result.items():
            assert isinstance(val, Quantity), f"{name} is not a Quantity"


class TestWelfareSectorMetadata:
    def test_metadata_completeness(self) -> None:
        sector = WelfareSector()
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

    def test_declares_reads_and_writes(self) -> None:
        sector = WelfareSector()
        reads = sector.declares_reads()
        writes = sector.declares_writes()
        assert isinstance(reads, list)
        assert isinstance(writes, list)
        assert len(reads) > 0
        assert len(writes) > 0
