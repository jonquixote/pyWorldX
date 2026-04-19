"""Task D6: regional_trade emits trade_food_loss; agriculture subtracts it."""
from __future__ import annotations

from pyworldx.sectors.regional_trade import RegionalTradeSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def test_regional_trade_emits_trade_food_loss() -> None:
    sector = RegionalTradeSector()
    ctx = make_ctx()
    result = sector.compute(t=0.0, stocks={}, inputs=base_shared(), ctx=ctx)
    assert "trade_food_loss" in result, f"keys={list(result)}"
    assert result["trade_food_loss"].magnitude >= 0.0


def test_trade_food_loss_in_declares_writes() -> None:
    sector = RegionalTradeSector()
    assert "trade_food_loss" in sector.declares_writes()


def test_agriculture_reads_trade_food_loss() -> None:
    agr = AgricultureSector()
    assert "trade_food_loss" in agr.declares_reads()


def test_nonzero_trade_food_loss_reduces_fpc() -> None:
    """Injecting trade_food_loss into agriculture must reduce food_per_capita."""
    ctx = make_ctx()
    agr = AgricultureSector()
    stocks = agr.init_stocks(ctx)

    s_no_loss = base_shared()
    s_no_loss["trade_food_loss"] = Quantity(0.0, "food_units")

    s_with_loss = base_shared()
    s_with_loss["trade_food_loss"] = Quantity(1e11, "food_units")

    r_no = agr.compute(t=0.0, stocks=stocks, inputs=s_no_loss, ctx=ctx)
    r_loss = agr.compute(t=0.0, stocks=stocks, inputs=s_with_loss, ctx=ctx)

    assert r_loss["food_per_capita"].magnitude < r_no["food_per_capita"].magnitude, (
        f"With loss fpc={r_loss['food_per_capita'].magnitude:.2f} must be < "
        f"no-loss fpc={r_no['food_per_capita'].magnitude:.2f}"
    )


def test_zero_trade_food_loss_unchanged() -> None:
    """trade_food_loss=0 must not change agriculture output."""
    ctx = make_ctx()
    agr = AgricultureSector()
    stocks = agr.init_stocks(ctx)

    s_base = base_shared()
    s_zero = base_shared()
    s_zero["trade_food_loss"] = Quantity(0.0, "food_units")

    r_base = agr.compute(t=0.0, stocks=stocks, inputs=s_base, ctx=ctx)
    r_zero = agr.compute(t=0.0, stocks=stocks, inputs=s_zero, ctx=ctx)

    assert r_base["food_per_capita"].magnitude == r_zero["food_per_capita"].magnitude
