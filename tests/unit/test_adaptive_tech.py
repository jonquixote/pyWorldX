"""Tests for the adaptive technology sector (pyWorldX extension)."""

from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.adaptive_technology import AdaptiveTechnologySector
from pyworldx.sectors.base import RunContext


def _make_ctx() -> RunContext:
    return RunContext()


def _default_inputs() -> dict[str, Quantity]:
    return {
        "industrial_output": Quantity(5e10, "industrial_output_units"),
        "nr_fraction_remaining": Quantity(0.8, "dimensionless"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "food_per_capita": Quantity(2.0, "food_units_per_person"),
    }


class TestAdaptiveTechInitStocks:
    def test_returns_tech_stock(self) -> None:
        sector = AdaptiveTechnologySector()
        stocks = sector.init_stocks(_make_ctx())
        assert "TECH" in stocks
        assert stocks["TECH"].magnitude == 1.0

    def test_tech_stock_is_quantity(self) -> None:
        sector = AdaptiveTechnologySector()
        stocks = sector.init_stocks(_make_ctx())
        assert isinstance(stocks["TECH"], Quantity)


class TestAdaptiveTechCompute:
    def test_returns_multipliers(self) -> None:
        sector = AdaptiveTechnologySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        assert "resource_tech_mult" in result
        assert "pollution_tech_mult" in result
        assert "agriculture_tech_mult" in result

    def test_returns_d_tech(self) -> None:
        sector = AdaptiveTechnologySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        assert "d_TECH" in result

    def test_inert_before_policy_year(self) -> None:
        """Before POLICY_YEAR (default 4000), all multipliers = 1.0."""
        sector = AdaptiveTechnologySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(2000.0, stocks, inputs, ctx)
        assert result["resource_tech_mult"].magnitude == 1.0
        assert result["pollution_tech_mult"].magnitude == 1.0
        assert result["agriculture_tech_mult"].magnitude == 1.0
        assert result["d_TECH"].magnitude == 0.0

    def test_active_after_policy_year(self) -> None:
        """After POLICY_YEAR, tech multipliers should be >= 1.0."""
        sector = AdaptiveTechnologySector()
        sector.policy_year = 2000.0  # activate early
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(2050.0, stocks, inputs, ctx)
        assert result["resource_tech_mult"].magnitude >= 1.0
        assert result["pollution_tech_mult"].magnitude >= 1.0
        assert result["agriculture_tech_mult"].magnitude >= 1.0

    def test_all_outputs_are_quantities(self) -> None:
        sector = AdaptiveTechnologySector()
        ctx = _make_ctx()
        stocks = sector.init_stocks(ctx)
        inputs = _default_inputs()
        result = sector.compute(0.0, stocks, inputs, ctx)
        for name, val in result.items():
            assert isinstance(val, Quantity), f"{name} is not a Quantity"


class TestAdaptiveTechMetadata:
    def test_metadata_completeness(self) -> None:
        sector = AdaptiveTechnologySector()
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

    def test_marked_as_experimental(self) -> None:
        """Should be EXPERIMENTAL, not REFERENCE_MATCHED."""
        from pyworldx.core.metadata import ValidationStatus
        sector = AdaptiveTechnologySector()
        meta = sector.metadata()
        assert meta["validation_status"] == ValidationStatus.EXPERIMENTAL

    def test_declares_reads_and_writes(self) -> None:
        sector = AdaptiveTechnologySector()
        reads = sector.declares_reads()
        writes = sector.declares_writes()
        assert isinstance(reads, list)
        assert isinstance(writes, list)
        assert len(reads) > 0
        assert len(writes) > 0
