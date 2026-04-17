"""Task A3: CentralRegistrar demand-weighted fallback when weights default to 1.0."""
from __future__ import annotations

import pytest

from pyworldx.core.central_registrar import CentralRegistrar, EJ_SCALE
from pyworldx.core.quantities import Quantity


def _make_shared(supply_ej: float, big_demand_ej: float, small_demand_ej: float) -> dict:
    return {
        "fossil_output": Quantity(supply_ej / EJ_SCALE, "energy_units"),
        "sustainable_output": Quantity(0.0, "energy_units"),
        "technology_output": Quantity(0.0, "energy_units"),
        "energy_demand_big": Quantity(big_demand_ej / EJ_SCALE, "energy_units"),
        "energy_demand_small": Quantity(small_demand_ej / EJ_SCALE, "energy_units"),
    }


def test_demand_weighted_fallback_gives_same_multiplier() -> None:
    """Under default weights (all 1.0), both sectors get the same multiplier."""
    registrar = CentralRegistrar(energy_ceiling=1.0)  # ceiling off: supply == total
    shared = _make_shared(supply_ej=50.0, big_demand_ej=90.0, small_demand_ej=10.0)
    registrar.resolve(shared)

    mb = shared["supply_multiplier_big"].magnitude
    ms = shared["supply_multiplier_small"].magnitude

    # Demand-weighted: each sector gets supply proportional to demand
    # Both ratios = 50/100 = 0.5, so multipliers must be equal
    assert abs(mb - ms) < 0.01, f"mb={mb:.4f} ms={ms:.4f} differ by more than 1%"
    # And around 0.5^1.5 ≈ 0.354 (super-linear decline in 50-100 zone)
    assert 0.30 <= mb <= 0.40, f"mb={mb:.4f} outside expected range for 50% supply ratio"


def test_weighted_allocation_differs_when_weights_set() -> None:
    """When sectors explicitly write different weights, allocation IS unequal."""
    registrar = CentralRegistrar(energy_ceiling=1.0)
    shared = _make_shared(supply_ej=50.0, big_demand_ej=50.0, small_demand_ej=50.0)
    # Big sector has 10x the liquid funds
    shared["liquid_funds_big"] = Quantity(10.0, "dimensionless")
    shared["liquid_funds_small"] = Quantity(1.0, "dimensionless")
    shared["security_value_big"] = Quantity(1.0, "dimensionless")
    shared["security_value_small"] = Quantity(1.0, "dimensionless")
    registrar.resolve(shared)

    mb = shared["supply_multiplier_big"].magnitude
    ms = shared["supply_multiplier_small"].magnitude
    assert mb > ms, "big sector with higher liquid_funds must get bigger multiplier"
