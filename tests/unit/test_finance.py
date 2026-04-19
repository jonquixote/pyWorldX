"""Unit tests for FinanceSector (100% line+branch coverage)."""
from __future__ import annotations

import pytest

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.finance import FinanceSector, governance_multiplier


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _inputs(**overrides: float) -> dict[str, Quantity]:
    base: dict[str, tuple[float, str]] = {
        "industrial_output": (7.9e11, "industrial_output_units"),
        "IC": (2.1e11, "capital_units"),
        "SC": (1.44e11, "capital_units"),
        "AL": (0.9e9, "hectares"),
        "POP": (1.65e9, "persons"),
        "tnds_aes": (0.0, "capital_units"),
        "education_tnds": (0.0, "capital_units"),
        "damages_tnds": (0.0, "capital_units"),
    }
    result = {k: Quantity(v, u) for k, (v, u) in base.items()}
    for k, v in overrides.items():
        unit = base.get(k, (0.0, "capital_units"))[1]
        result[k] = Quantity(float(v), unit)
    return result


class TestGovernanceMultiplier:
    def test_zero_debt(self) -> None:
        assert governance_multiplier(0.0) == 1.0

    def test_negative_debt(self) -> None:
        assert governance_multiplier(-1.0) == 1.0

    def test_at_ceiling(self) -> None:
        assert governance_multiplier(1.5) == 0.0

    def test_above_ceiling(self) -> None:
        assert governance_multiplier(2.0) == 0.0

    def test_mid_range_decreasing(self) -> None:
        g_low = governance_multiplier(0.3)
        g_high = governance_multiplier(1.2)
        assert g_low > g_high > 0.0


class TestFinanceSector:
    def test_init_stocks(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        assert "L" in stocks
        assert "D_g" in stocks
        assert "D_s" in stocks
        assert "D_p" in stocks
        assert stocks["L"].magnitude == 1.0e11

    def test_compute_basic(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert "financial_resilience" in out
        assert "debt_to_gdp" in out
        assert "maintenance_ratio" in out
        assert "military_spending" in out
        assert "liquid_funds" in out

    def test_military_spending_proportional_to_io(self) -> None:
        s = FinanceSector(military_fraction=0.02)
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        expected = 0.02 * 7.9e11
        assert abs(out["military_spending"].magnitude - expected) < 1.0

    def test_debt_to_gdp_at_zero_debt(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        stocks["D_g"] = Quantity(0.0, "capital_units")
        stocks["D_s"] = Quantity(0.0, "capital_units")
        stocks["D_p"] = Quantity(0.0, "capital_units")
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["debt_to_gdp"].magnitude == pytest.approx(0.0, abs=1e-10)

    def test_financial_resilience_positive(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["financial_resilience"].magnitude > 0.0

    def test_tnds_aggregation(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_no_tnds = s.compute(0.0, stocks, _inputs(), ctx)
        out_with_tnds = s.compute(0.0, stocks, _inputs(tnds_aes=1e10), ctx)
        assert out_with_tnds["d_L"].magnitude < out_no_tnds["d_L"].magnitude

    def test_collateral_value_includes_al(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_lo = s.compute(0.0, stocks, _inputs(AL=1e8), ctx)
        out_hi = s.compute(0.0, stocks, _inputs(AL=5e9), ctx)
        assert out_hi["collateral_value"].magnitude > out_lo["collateral_value"].magnitude

    def test_all_outputs_are_quantities(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        for k, v in out.items():
            assert isinstance(v, Quantity), f"{k} is not a Quantity"

    def test_declares_reads_includes_tnds(self) -> None:
        s = FinanceSector()
        reads = s.declares_reads()
        assert "tnds_aes" in reads
        assert "education_tnds" in reads
        assert "damages_tnds" in reads

    def test_declares_writes_complete(self) -> None:
        s = FinanceSector()
        writes = s.declares_writes()
        assert "financial_resilience" in writes
        assert "liquid_funds" in writes
        assert "total_debt" in writes

    def test_high_debt_reduces_loan_availability(self) -> None:
        s = FinanceSector()
        ctx = _ctx()
        # At ceiling debt, governance multiplier → 0, loan_availability → 0
        stocks_hi_debt = {
            "L": Quantity(-1e10, "capital_units"),  # negative to trigger borrowing
            "D_g": Quantity(1.185e12, "capital_units"),  # ~1.5× IO
            "D_s": Quantity(0.0, "capital_units"),
            "D_p": Quantity(0.0, "capital_units"),
        }
        out = s.compute(0.0, stocks_hi_debt, _inputs(), ctx)
        assert out["loan_availability"].magnitude == pytest.approx(0.0, abs=1e-6)
