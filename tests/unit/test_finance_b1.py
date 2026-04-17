"""Task B1: finance.py military_fraction copy-paste bug.

Line 181 of finance.py computes investments = profit * self.military_fraction
but the comment says 're-investment fraction'. These are independent concepts.
Fix: add investment_fraction attribute (default 0.25) and use it for investments.
"""
from __future__ import annotations

from pyworldx.sectors.finance import FinanceSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def test_finance_has_investment_fraction_attribute() -> None:
    """FinanceSector must expose investment_fraction distinct from military_fraction."""
    fs = FinanceSector()
    assert hasattr(fs, "investment_fraction"), "investment_fraction attribute missing"
    assert hasattr(fs, "military_fraction"), "military_fraction attribute still present"
    assert fs.investment_fraction != fs.military_fraction, (
        f"investment_fraction={fs.investment_fraction} must differ from "
        f"military_fraction={fs.military_fraction}"
    )


def test_changing_military_fraction_does_not_change_investments() -> None:
    """investments must use investment_fraction, not military_fraction."""
    ctx = make_ctx()
    shared = base_shared()

    fs_low_mil = FinanceSector(military_fraction=0.001)
    fs_high_mil = FinanceSector(military_fraction=0.10)

    stocks = {
        "L": Quantity(1e11, "capital_units"),
        "D_g": Quantity(0.0, "capital_units"),
        "D_s": Quantity(0.0, "capital_units"),
        "D_p": Quantity(0.0, "capital_units"),
    }

    result_low = fs_low_mil.compute(t=50.0, stocks=stocks, inputs=shared, ctx=ctx)
    result_high = fs_high_mil.compute(t=50.0, stocks=stocks, inputs=shared, ctx=ctx)

    # dL differs because military_spending differs ...
    # but investments term should be the same (both use investment_fraction not military)
    # The military_spending is subtracted separately, so isolate by checking
    # that two sectors with SAME investment_fraction but different military produce
    # the same investment-related delta (dL should differ only by delta military).
    dL_low = result_low["d_L"].magnitude
    dL_high = result_high["d_L"].magnitude

    # low_mil subtracts less military → dL_low > dL_high → diff = (high_mil - low_mil)*io
    io = shared["industrial_output"].magnitude
    expected_dL_diff = (0.10 - 0.001) * io
    actual_dL_diff = dL_low - dL_high

    assert abs(actual_dL_diff - expected_dL_diff) < abs(expected_dL_diff) * 0.05, (
        f"dL diff={actual_dL_diff:.4g} expected≈{expected_dL_diff:.4g}; "
        "investments term must not scale with military_fraction"
    )
