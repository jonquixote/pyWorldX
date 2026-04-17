"""Task C5: ecosystem_services.py temperature constants must use anomaly scale."""
from __future__ import annotations

from pyworldx.sectors.ecosystem_services import EcosystemServicesSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx


def _compute(temp_anomaly: float = 0.0, esp: float = 0.8) -> dict:
    sector = EcosystemServicesSector()
    ctx = make_ctx()
    stocks = {"ESP": Quantity(esp, "dimensionless")}
    inputs = {
        "temperature_anomaly": Quantity(temp_anomaly, "deg_C_anomaly"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "AL": Quantity(0.9e9, "hectares"),
    }
    return sector.compute(t=0.0, stocks=stocks, inputs=inputs, ctx=ctx)


def test_zero_anomaly_gives_full_temp_factor() -> None:
    """At T_anomaly=0 (pre-industrial), regeneration should not be suppressed."""
    r0 = _compute(temp_anomaly=0.0)
    r_hot = _compute(temp_anomaly=4.0)
    # At T=0 the regeneration rate must be higher than at T=4°C
    # (we infer this indirectly: d_ESP at T=0 > d_ESP at T=4 for same ESP)
    assert r0["d_ESP"].magnitude > r_hot["d_ESP"].magnitude, (
        f"dESP at T=0 ({r0['d_ESP'].magnitude:.6f}) should exceed "
        f"dESP at T=4 ({r_hot['d_ESP'].magnitude:.6f})"
    )


def test_four_degree_anomaly_suppresses_regeneration() -> None:
    """At T_anomaly=4°C (IPCC critical), temp_factor must be < 1."""
    r0 = _compute(temp_anomaly=0.0, esp=0.5)
    r4 = _compute(temp_anomaly=4.0, esp=0.5)
    # With T_crit=4.0, at exactly 4°C temp_factor=0, so dESP must be lower
    assert r4["d_ESP"].magnitude < r0["d_ESP"].magnitude, (
        f"At 4°C anomaly dESP={r4['d_ESP'].magnitude:.6f} must be < "
        f"dESP at 0°C={r0['d_ESP'].magnitude:.6f}"
    )


def test_realistic_anomaly_range_affects_temp_factor() -> None:
    """Anomalies in 0-4°C range must monotonically reduce regeneration."""
    prev = _compute(temp_anomaly=0.0, esp=0.6)["d_ESP"].magnitude
    for t_anom in (0.5, 1.0, 2.0, 3.0):
        cur = _compute(temp_anomaly=t_anom, esp=0.6)["d_ESP"].magnitude
        assert cur <= prev, (
            f"dESP at T={t_anom} ({cur:.6f}) must be <= dESP at lower T ({prev:.6f})"
        )
        prev = cur
