"""Shared Phase 2 test helpers — DO NOT import outside tests/."""
from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


def make_phase2_sectors() -> list[object]:
    """Return the full set of Phase 2 sector instances for integration tests."""
    from pyworldx.sectors.population import PopulationSector
    from pyworldx.sectors.capital import CapitalSector
    from pyworldx.sectors.agriculture import AgricultureSector
    from pyworldx.sectors.resources import ResourcesSector
    from pyworldx.sectors.pollution import PollutionSector
    from pyworldx.sectors.climate import ClimateSector
    from pyworldx.sectors.ecosystem_services import EcosystemServicesSector
    from pyworldx.sectors.finance import FinanceSector
    from pyworldx.sectors.human_capital import HumanCapitalSector
    from pyworldx.sectors.welfare import WelfareSector
    from pyworldx.sectors.phosphorus import PhosphorusSector
    from pyworldx.sectors.energy_fossil import EnergyFossilSector
    from pyworldx.sectors.energy_technology import EnergyTechnologySector
    from pyworldx.sectors.energy_sustainable import EnergySustainableSector
    from pyworldx.sectors.seir import SEIRModule
    from pyworldx.sectors.regional_trade import RegionalTradeSector
    return [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        ClimateSector(),
        EcosystemServicesSector(),
        FinanceSector(),
        HumanCapitalSector(),
        WelfareSector(),
        PhosphorusSector(),
        EnergyFossilSector(),
        EnergyTechnologySector(),
        EnergySustainableSector(),
        SEIRModule(),
        RegionalTradeSector(),
    ]


def make_ctx(master_dt: float = 1.0) -> RunContext:
    """Return a minimal RunContext using relative time (t=0→200, 1900→2100)."""
    # IMPORTANT: use t_start=0.0, NOT 1900.0. The engine runs in relative time.
    return RunContext(master_dt=master_dt, t_start=0.0, t_end=200.0, shared_state={})


def base_shared(year: int = 2020, **overrides: float) -> dict[str, Quantity]:
    """Build a default shared-state dict for sector compute() tests.

    All values are physically plausible defaults for a mid-21st-century world.
    Callers pass relative t (0-200) to sector.compute(); this dict supplies inputs.

    The ``year`` parameter exists for human readability only and is not used
    to drive any internal logic.
    """
    defaults: dict[str, tuple[float, str]] = {
        "industrial_output": (1.0e11, "industrial_output_units"),
        "POP": (7.8e9, "people"),
        "IC": (2.0e11, "capital_units"),
        "SC": (1.0e11, "capital_units"),
        "AL": (1.4e9, "hectares"),
        "L": (1.0e10, "capital_units"),
        "D_g": (0.0, "capital_units"),
        "D_s": (0.0, "capital_units"),
        "D_p": (0.0, "capital_units"),
        "service_output_per_capita": (500.0, "service_units_per_capita"),
        "food_per_capita": (400.0, "food_units_per_capita"),
        "temperature_anomaly": (1.0, "deg_C_anomaly"),
        "labor_force_multiplier": (1.0, "dimensionless"),
        "energy_supply_factor": (1.0, "dimensionless"),
        "financial_resilience": (1.5, "dimensionless"),
        "C_atm": (850.0, "GtC"),
        "tnds_aes": (0.0, "capital_units"),
        "education_tnds": (0.0, "capital_units"),
        "damages_tnds": (0.0, "capital_units"),
        "disease_death_rate": (0.0, "per_year"),
        "ghg_radiative_forcing": (2.5, "W_per_m2"),
        "tech_metals_demand": (0.0, "dimensionless"),
        "tech_cost_fraction": (0.0, "dimensionless"),
        "resource_tech_mult": (1.0, "dimensionless"),
        "pollution_tech_mult": (1.0, "dimensionless"),
        "toxin_health_multiplier": (1.0, "dimensionless"),
        "toxin_fertility_multiplier": (1.0, "dimensionless"),
        "trade_food_loss": (0.0, "food_units"),
        "trapped_capital": (0.0, "capital_units"),
        "tech_sector_investment": (0.0, "capital_units"),
        "sustainable_sector_investment": (0.0, "capital_units"),
        "fossil_sector_investment": (0.0, "capital_units"),
    }
    d: dict[str, Quantity] = {k: Quantity(v, u) for k, (v, u) in defaults.items()}
    for k, v in overrides.items():
        unit = defaults.get(k, (0.0, "dimensionless"))[1]
        d[k] = Quantity(float(v), unit)
    return d
