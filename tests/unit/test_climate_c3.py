"""Task C3: climate.py must read ghg_radiative_forcing from pollution_ghg, not re-derive."""
from __future__ import annotations

from pyworldx.sectors.climate import ClimateSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _stocks() -> dict:
    return {
        "T": Quantity(0.0, "deg_C_anomaly"),
        "A": Quantity(0.0, "dimensionless"),
    }


def test_climate_reads_ghg_radiative_forcing() -> None:
    """climate.py must declare read for ghg_radiative_forcing."""
    sector = ClimateSector()
    assert "ghg_radiative_forcing" in sector.declares_reads()


def test_injected_rf_changes_temperature_derivative() -> None:
    """Changing ghg_radiative_forcing in shared state must affect dT."""
    ctx = make_ctx()
    sector = ClimateSector()

    shared_low = base_shared()
    shared_low["ghg_radiative_forcing"] = Quantity(1.0, "W_per_m2")

    shared_high = base_shared()
    shared_high["ghg_radiative_forcing"] = Quantity(5.0, "W_per_m2")

    r_low = sector.compute(t=0.0, stocks=_stocks(), inputs=shared_low, ctx=ctx)
    r_high = sector.compute(t=0.0, stocks=_stocks(), inputs=shared_high, ctx=ctx)

    assert r_high["d_T"].magnitude > r_low["d_T"].magnitude, (
        f"Higher RF must give larger dT: low={r_low['d_T'].magnitude:.4f}, "
        f"high={r_high['d_T'].magnitude:.4f}"
    )


def test_zero_rf_gives_cooling_or_equilibrium() -> None:
    """At RF=0 and current T=0, dT should be near zero (equilibrium)."""
    ctx = make_ctx()
    sector = ClimateSector()
    shared = base_shared()
    shared["ghg_radiative_forcing"] = Quantity(0.0, "W_per_m2")
    result = sector.compute(t=0.0, stocks=_stocks(), inputs=shared, ctx=ctx)
    # With T=0 and RF=0, dT should be close to 0
    assert abs(result["d_T"].magnitude) < 1.0, (
        f"dT={result['d_T'].magnitude:.4f} should be near 0 at RF=0, T=0"
    )
