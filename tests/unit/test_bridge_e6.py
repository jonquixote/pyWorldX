"""Task E6: bridge.py must map all Phase 2 entities to engine variable names."""
from __future__ import annotations

from pyworldx.data.bridge import ENTITY_TO_ENGINE_MAP


_PHASE2_ENTITIES = {
    "carbon.atmospheric_gtc",
    "carbon.land_gtc",
    "carbon.soil_gtc",
    "carbon.ocean_surface_gtc",
    "carbon.ocean_deep_gtc",
    "finance.resilience",
    "minerals.tech_metals_availability",
    "climate.temperature_anomaly",
    "epidemiology.labor_force_multiplier",
    "energy.supply_factor",
}


def test_bridge_resolves_all_phase2_entities() -> None:
    mapped = set(ENTITY_TO_ENGINE_MAP.keys())
    missing = _PHASE2_ENTITIES - mapped
    assert not missing, f"bridge missing Phase 2 entities: {missing}"


def test_phase2_carbon_entities_map_correctly() -> None:
    assert ENTITY_TO_ENGINE_MAP["carbon.atmospheric_gtc"] == "C_atm"
    assert ENTITY_TO_ENGINE_MAP["carbon.soil_gtc"] == "C_soc"
    assert ENTITY_TO_ENGINE_MAP["carbon.ocean_deep_gtc"] == "C_ocean_deep"


def test_phase2_coupling_entities_map_correctly() -> None:
    assert ENTITY_TO_ENGINE_MAP["finance.resilience"] == "financial_resilience"
    assert ENTITY_TO_ENGINE_MAP["energy.supply_factor"] == "energy_supply_factor"
    assert ENTITY_TO_ENGINE_MAP["climate.temperature_anomaly"] == "temperature_anomaly"
