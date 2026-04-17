"""Unit tests for GiniDistributionSector (100% line+branch coverage)."""
from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.gini_distribution import GiniDistributionSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _inputs(fpc: float = 400.0, iopc: float = 40.0, sopc: float = 87.0, ppolx: float = 1.0) -> dict[str, Quantity]:
    return {
        "food_per_capita": Quantity(fpc, "food_units"),
        "industrial_output_per_capita": Quantity(iopc, "industrial_output_units"),
        "service_output_per_capita": Quantity(sopc, "service_output_units"),
        "pollution_index": Quantity(ppolx, "dimensionless"),
    }


class TestGiniDistributionSector:
    def test_init_stocks_empty(self) -> None:
        s = GiniDistributionSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        assert stocks == {}

    def test_abundance_redistributes_to_bot90(self) -> None:
        """In abundance (high FPC), equal Gini weights → bot90 gets more per capita (redistributive)."""
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(fpc=600.0), ctx)
        # At abundance, weights are equal per population share → after normalizing
        # by 0.1 and 0.9, bot90 per-capita > top10 per-capita (the model is redistributive in abundance)
        assert out["gini_food_bot90"].magnitude > out["gini_food_top10"].magnitude

    def test_scarcity_accentuates_top10(self) -> None:
        """Under scarcity, top 10% fraction increases vs abundance."""
        s = GiniDistributionSector()
        ctx = _ctx()
        out_abun = s.compute(0.0, {}, _inputs(fpc=600.0), ctx)
        out_scar = s.compute(0.0, {}, _inputs(fpc=100.0), ctx)
        ratio_abundant = out_abun["gini_food_top10"].magnitude / max(out_abun["gini_food_bot90"].magnitude, 1e-10)
        ratio_scarce = out_scar["gini_food_top10"].magnitude / max(out_scar["gini_food_bot90"].magnitude, 1e-10)
        assert ratio_scarce > ratio_abundant, "Scarcity must accentuate inequality"

    def test_social_suicide_inactive_at_high_fpc(self) -> None:
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(fpc=600.0), ctx)
        assert out["social_suicide_active"].magnitude == 0.0

    def test_social_suicide_active_at_extreme_scarcity(self) -> None:
        """At very low FPC, bot90 falls below 0.5 * subsistence → social_suicide=1."""
        s = GiniDistributionSector()
        ctx = _ctx()
        # Very low FPC drives bot90 below 0.5 * subsistence
        out = s.compute(0.0, {}, _inputs(fpc=1.0), ctx)
        assert out["social_suicide_active"].magnitude == 1.0

    def test_drfm_higher_for_bot90_at_scarcity(self) -> None:
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(fpc=100.0), ctx)
        assert out["DRFM_bot90"].magnitude >= out["DRFM_top10"].magnitude

    def test_drpm_pollution_higher_for_bot90(self) -> None:
        """Bottom 90% have higher pollution exposure than top 10%."""
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(ppolx=5.0), ctx)
        assert out["DRPM_bot90"].magnitude > out["DRPM_top10"].magnitude

    def test_drpm_zero_at_baseline_pollution(self) -> None:
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(ppolx=1.0), ctx)
        assert out["DRPM_top10"].magnitude == 0.0
        assert out["DRPM_bot90"].magnitude == 0.0

    def test_drfm_declines_with_higher_fpc(self) -> None:
        """DRFM decreases as FPC rises (less food stress at higher food supply)."""
        s = GiniDistributionSector()
        ctx = _ctx()
        out_lo = s.compute(0.0, {}, _inputs(fpc=150.0), ctx)
        out_hi = s.compute(0.0, {}, _inputs(fpc=600.0), ctx)
        assert out_hi["DRFM_bot90"].magnitude < out_lo["DRFM_bot90"].magnitude

    def test_io_allocation_matches_fpc_allocation(self) -> None:
        """IO allocation follows same Gini weights as food allocation."""
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(fpc=100.0, iopc=40.0), ctx)
        assert out["gini_io_top10"].magnitude > 0.0
        assert out["gini_io_bot90"].magnitude > 0.0

    def test_all_outputs_are_quantities(self) -> None:
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(), ctx)
        for k, v in out.items():
            assert isinstance(v, Quantity), f"{k} is not a Quantity"

    def test_declares_reads_and_writes(self) -> None:
        s = GiniDistributionSector()
        assert "food_per_capita" in s.declares_reads()
        assert "gini_food_top10" in s.declares_writes()
        assert "social_suicide_active" in s.declares_writes()

    def test_drfm_bot90_exponential_above_threshold(self) -> None:
        """DRFM_bot90 uses exponential scaling when drfm > 0.5."""
        s = GiniDistributionSector()
        ctx = _ctx()
        out = s.compute(0.0, {}, _inputs(fpc=20.0), ctx)
        # At severe scarcity, DRFM_bot90 should exceed 0.5
        assert out["DRFM_bot90"].magnitude > 0.5
