"""Task A4: CentralRegistrar broadcasts global energy_supply_factor."""
from __future__ import annotations

from pyworldx.core.central_registrar import CentralRegistrar
from pyworldx.core.quantities import Quantity


def test_registrar_writes_energy_supply_factor_when_constrained() -> None:
    registrar = CentralRegistrar()
    shared: dict = {
        "fossil_output": Quantity(1e11, "energy_units"),
        "sustainable_output": Quantity(0.0, "energy_units"),
        "technology_output": Quantity(0.0, "energy_units"),
        "energy_demand_test": Quantity(2e11, "energy_units"),
    }
    registrar.resolve(shared)
    assert "energy_supply_factor" in shared
    esf = shared["energy_supply_factor"].magnitude
    assert 0.0 < esf < 1.0, f"ESF={esf:.4f} should be <1 when demand exceeds supply"


def test_registrar_writes_energy_supply_factor_unconstrained() -> None:
    registrar = CentralRegistrar()
    shared: dict = {
        "fossil_output": Quantity(1e12, "energy_units"),
        "sustainable_output": Quantity(0.0, "energy_units"),
        "technology_output": Quantity(0.0, "energy_units"),
        "energy_demand_test": Quantity(1e10, "energy_units"),
    }
    registrar.resolve(shared)
    assert "energy_supply_factor" in shared
    esf = shared["energy_supply_factor"].magnitude
    assert esf == 1.0, f"ESF should be 1.0 when supply exceeds demand; got {esf}"
