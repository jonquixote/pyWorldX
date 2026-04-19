"""Task C4: pollution_ghg is SOC-authoritative; phosphorus reads C_soc."""
from __future__ import annotations

import copy

from pyworldx.sectors.pollution_ghg import PollutionGHGModule as PollutionGHGSector
from pyworldx.sectors.phosphorus import PhosphorusSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx


def test_5_stock_carbon_mass_conservation() -> None:
    """Zero emissions for 200 years → total C conserved to <1e-4 relative."""
    ghg = PollutionGHGSector()
    ctx = make_ctx()
    stocks = ghg.init_stocks(ctx)
    compartments = [k for k in ("C_atm", "C_land", "C_soc", "C_ocean_surf", "C_ocean_deep") if k in stocks]
    assert len(compartments) == 5, f"expected 5 compartments, got {compartments}"
    initial_total = sum(stocks[k].magnitude for k in compartments)

    shared: dict[str, Quantity] = {
        "pollution_gen": Quantity(0.0, "pollution_units"),
        "industrial_output": Quantity(0.0, "industrial_output_units"),
        "fossil_output": Quantity(0.0, "energy_units"),
    }
    stocks_running = copy.deepcopy(stocks)
    for year in range(200):
        d = ghg.compute(float(year), stocks_running, shared, ctx)
        for k in compartments:
            stocks_running[k] = Quantity(
                stocks_running[k].magnitude + d[f"d_{k}"].magnitude,
                stocks_running[k].unit,
            )
    final_total = sum(stocks_running[k].magnitude for k in compartments)
    drift = abs(final_total - initial_total) / max(initial_total, 1e-10)
    assert drift < 1e-4, f"carbon mass drifted {drift:.2e} (>{1e-4:.0e})"


def test_c_soc_in_pollution_ghg_declares_writes() -> None:
    """pollution_ghg must declare it writes C_soc."""
    ghg = PollutionGHGSector()
    assert "C_soc" in ghg.declares_writes()


def test_phosphorus_reads_unified_c_soc() -> None:
    """phosphorus must declare it reads C_soc from pollution_ghg."""
    phos = PhosphorusSector()
    assert "C_soc" in phos.declares_reads(), (
        "phosphorus must read C_soc from pollution_ghg"
    )


def test_phosphorus_has_no_own_soc_stock() -> None:
    """phosphorus must not track its own SOC stock."""
    phos = PhosphorusSector()
    stocks = phos.init_stocks(make_ctx())
    assert "SOC" not in stocks, "phosphorus must not track its own SOC stock"


def test_injected_c_soc_affects_soc_resilience() -> None:
    """Changing C_soc injected into phosphorus changes soc_resilience_multiplier."""
    phos = PhosphorusSector()
    ctx = make_ctx()
    base_stocks = phos.init_stocks(ctx)

    shared_high = {"C_soc": Quantity(1500.0, "GtC")}
    shared_low = {"C_soc": Quantity(500.0, "GtC")}

    r_high = phos.compute(t=0.0, stocks=base_stocks, inputs=shared_high, ctx=ctx)
    r_low = phos.compute(t=0.0, stocks=base_stocks, inputs=shared_low, ctx=ctx)

    assert r_high["soc_resilience_multiplier"].magnitude > r_low["soc_resilience_multiplier"].magnitude, (
        f"Higher C_soc must give higher resilience: "
        f"high={r_high['soc_resilience_multiplier'].magnitude:.4f}, "
        f"low={r_low['soc_resilience_multiplier'].magnitude:.4f}"
    )
