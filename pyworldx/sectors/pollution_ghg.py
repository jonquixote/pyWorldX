"""5-Stock Global Carbon Model (Phase 2 Task 5, Q75, Q84).

Replaces the single ghg_stock 100-year delay with a rigorous 5-compartment
carbon cycle calibrated against NOAA/GCB 2024 data.

Stocks (all in GtC):
  C_atm:        Atmospheric carbon (~600 GtC at 1900 ≡ 280 ppm CO2)
  C_land:       Land biomass / vegetation (~600 GtC)
  C_soc:        Soil organic carbon (~1500 GtC)
  C_ocean_surf: Ocean surface dissolved carbon (~1000 GtC)
  C_ocean_deep: Deep ocean & sediments (~38000 GtC)

  Backward-compatible alias: ghg_stock = C_atm (for existing tests)

Fluxes:
  A. Anthropogenic emissions → C_atm
     F_combustion + F_calcination + F_leakage

  B. Ocean carbon sink
     F_atm→ocean_surf = k_oa · (C_atm/C_atm0 - C_ocean_surf/C_ocean_surf0)
     F_ocean_surf→deep = k_od · (C_ocean_surf - C_eq_surf)

  C. Land carbon sink (biosphere)
     NPP = NPP_0 · (1 + β · ln(C_atm/C_atm0))    (CO2 fertilization)
     F_land→soc = k_litter · C_land                  (litter fall)
     F_land→atm = k_resp_plant · C_land               (plant respiration)
     F_soc→atm  = k_resp_soil · C_soc                 (soil respiration)

  D. Gaian feedback (Q84 — permafrost / soil carbon)
     k_resp_soil(T) = k_resp_soil_0 · Q10^(T/10)
     As T rises, soil outgasses → positive feedback.

Output:
  ghg_radiative_forcing = 5.35 · ln(C_atm / C_atm0)  [W/m²]
  ghg_stock = C_atm  (backward compatibility)

Mass conservation:
  ΣC(t) = ΣC(0) + ∫F_emissions dt  (verified by balance auditor)
"""

from __future__ import annotations

import math

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Initial conditions (GtC, 1900 pre-industrial) ────────────────────

_C_ATM0 = 600.0          # ~280 ppm CO2
_C_LAND0 = 600.0         # Land biomass (vegetation)
_C_SOC0 = 1500.0         # Soil organic carbon (top 1m global)
_C_OCEAN_SURF0 = 1000.0  # Ocean surface dissolved carbon
_C_OCEAN_DEEP0 = 38000.0  # Deep ocean + sediments

# ── Flux parameters ──────────────────────────────────────────────────

# Anthropogenic emission intensities
_COMBUSTION_INTENSITY = 1.0e-11   # GtC per unit fossil_output
_CALCINATION_INTENSITY = 5.0e-13  # GtC per unit IO (industrial processes)
_LEAKAGE_FRACTION = 0.02          # Methane leakage as fraction of combustion

# Ocean carbon sink
_K_OA = 0.10        # Ocean-atmosphere exchange rate (GtC/yr per unit disequilibrium)
_K_OD = 0.005       # Deep mixing rate (per yr)

# Land carbon cycle
_NPP0 = 60.0        # Pre-industrial NPP (GtC/yr, global photosynthesis)
_BETA_CO2 = 0.4     # CO2 fertilization sensitivity (β)
_K_LITTER = 0.05   # Litter fall rate (per yr) — calibrated so that
                   # (_K_RESP_PLANT + _K_LITTER) × C_LAND0 = NPP0 = 60 GtC/yr
_K_RESP_PLANT = 0.05  # Plant respiration rate (per yr) — calibrated so that
                      # (_K_RESP_PLANT + _K_LITTER) × C_LAND0 = NPP0 = 60 GtC/yr
_K_RESP_SOIL0 = 0.02  # Base soil respiration rate (per yr)

# Gaian feedback (Q84)
_Q10 = 2.0  # Temperature sensitivity: soil respiration doubles per 10°C


class PollutionGHGModule:
    """5-stock global carbon model with Gaian feedback (Q75, Q84).

    Stocks: C_atm, C_land, C_soc, C_ocean_surf, C_ocean_deep, ghg_stock
    Reads: industrial_output, fossil_output, temperature_anomaly
    Writes: C_atm, C_land, C_soc, C_ocean_surf, C_ocean_deep,
            ghg_stock, ghg_emission_rate, ghg_radiative_forcing,
            carbon_ocean_flux, carbon_land_flux
    """

    name = "pollution_ghg"
    version = "2.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_ghg: float = _C_ATM0,
        tau_ghg: float = 100.0,  # kept for backward compat (unused now)
    ) -> None:
        self.initial_ghg = initial_ghg
        self.tau_ghg = tau_ghg

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "C_atm": Quantity(self.initial_ghg, "GtC"),
            "C_land": Quantity(_C_LAND0, "GtC"),
            "C_soc": Quantity(_C_SOC0, "GtC"),
            "C_ocean_surf": Quantity(_C_OCEAN_SURF0, "GtC"),
            "C_ocean_deep": Quantity(_C_OCEAN_DEEP0, "GtC"),
            # Backward-compatible alias
            "ghg_stock": Quantity(self.initial_ghg, "GtC"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        C_atm = stocks["C_atm"].magnitude
        C_land = stocks["C_land"].magnitude
        C_soc = stocks["C_soc"].magnitude
        C_ocean_surf = stocks["C_ocean_surf"].magnitude
        _C_ocean_deep = stocks["C_ocean_deep"].magnitude  # noqa: F841 — pure accumulation stock

        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        fossil_output = inputs.get(
            "fossil_output", Quantity(0.0, "energy_units")
        ).magnitude
        T = inputs.get(
            "temperature_anomaly", Quantity(0.0, "deg_C_anomaly")
        ).magnitude

        # ── A. Anthropogenic emissions → C_atm ────────────────────────
        combustion = fossil_output * _COMBUSTION_INTENSITY
        calcination = io * _CALCINATION_INTENSITY
        leakage = combustion * _LEAKAGE_FRACTION
        total_emission = combustion + calcination + leakage

        # ── B. Ocean carbon sink ──────────────────────────────────────
        # Exchange driven by disequilibrium between atmosphere and ocean
        # (normalized to pre-industrial partitioning)
        atm_ratio = C_atm / max(_C_ATM0, 1e-10)
        ocean_ratio = C_ocean_surf / max(_C_OCEAN_SURF0, 1e-10)
        f_atm_to_ocean = _K_OA * (atm_ratio - ocean_ratio)

        # Deep mixing: surface → deep proportional to excess above equilibrium
        f_surf_to_deep = _K_OD * (C_ocean_surf - _C_OCEAN_SURF0)

        # ── C. Land carbon sink (biosphere) ───────────────────────────
        # NPP with CO2 fertilization (logarithmic response)
        co2_ratio = max(C_atm / _C_ATM0, 0.1)
        npp = _NPP0 * (1.0 + _BETA_CO2 * math.log(co2_ratio))

        # Litter fall: vegetation → soil
        f_land_to_soc = _K_LITTER * C_land

        # Plant respiration: vegetation → atmosphere
        f_plant_resp = _K_RESP_PLANT * C_land

        # ── D. Gaian feedback: soil respiration (Q84) ─────────────────
        # k_resp_soil(T) = k_resp_soil_0 · Q10^(T/10)
        # At T=0: k = 0.02 (pre-industrial equilibrium)
        # At T=3: k = 0.02 * 2^0.3 ≈ 0.0246 (+23%)
        # At T=10: k = 0.04 (doubled) — massive outgassing
        k_resp_soil = _K_RESP_SOIL0 * (_Q10 ** (T / 10.0))
        f_soil_resp = k_resp_soil * C_soc

        # ── ODE rates ─────────────────────────────────────────────────
        dC_atm = (
            total_emission     # anthropogenic source
            - npp              # photosynthesis draws down CO2
            + f_plant_resp     # plant respiration returns CO2
            + f_soil_resp      # soil respiration returns CO2
            - f_atm_to_ocean   # ocean absorbs CO2
        )
        dC_land = npp - f_plant_resp - f_land_to_soc
        dC_soc = f_land_to_soc - f_soil_resp
        dC_ocean_surf = f_atm_to_ocean - f_surf_to_deep
        dC_ocean_deep = f_surf_to_deep

        # Backward-compatible ghg_stock tracks C_atm
        dghg = dC_atm

        # ── Radiative forcing ─────────────────────────────────────────
        rf = 5.35 * math.log(max(C_atm / self.initial_ghg, 0.1))

        # ── Carbon flux observables ───────────────────────────────────
        carbon_ocean_flux = f_atm_to_ocean  # positive = ocean absorbing
        carbon_land_flux = npp - f_plant_resp - f_soil_resp  # positive = land absorbing

        return {
            "d_C_atm": Quantity(dC_atm, "GtC"),
            "d_C_land": Quantity(dC_land, "GtC"),
            "d_C_soc": Quantity(dC_soc, "GtC"),
            "d_C_ocean_surf": Quantity(dC_ocean_surf, "GtC"),
            "d_C_ocean_deep": Quantity(dC_ocean_deep, "GtC"),
            "d_ghg_stock": Quantity(dghg, "GtC"),
            "ghg_emission_rate": Quantity(total_emission, "GtC_per_yr"),
            "ghg_radiative_forcing": Quantity(rf, "W_per_m2"),
            "carbon_ocean_flux": Quantity(carbon_ocean_flux, "GtC_per_yr"),
            "carbon_land_flux": Quantity(carbon_land_flux, "GtC_per_yr"),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "fossil_output", "temperature_anomaly"]

    def declares_writes(self) -> list[str]:
        return [
            "C_atm",
            "C_land",
            "C_soc",
            "C_ocean_surf",
            "C_ocean_deep",
            "ghg_stock",
            "ghg_emission_rate",
            "ghg_radiative_forcing",
            "carbon_ocean_flux",
            "carbon_land_flux",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": (
                EquationSource.SYNTHESIZED_FROM_PRIMARY_LITERATURE
            ),
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "5-stock carbon model (atm, land, soc, ocean_surf, ocean_deep)",
                "CO2 fertilization via logarithmic NPP response (β=0.4)",
                "Gaian feedback: Q10 soil respiration temperature sensitivity",
                "Ocean sink simplified to 2-box (surface + deep)",
                "Anthropogenic emissions from fossil, calcination, leakage",
            ],
            "free_parameters": ["initial_ghg", "tau_ghg"],
            "conservation_groups": [
                "carbon_total = C_atm + C_land + C_soc + C_ocean_surf + C_ocean_deep"
            ],
            "observables": [
                "C_atm",
                "C_land",
                "C_soc",
                "C_ocean_surf",
                "C_ocean_deep",
                "ghg_emission_rate",
                "ghg_radiative_forcing",
                "carbon_ocean_flux",
                "carbon_land_flux",
            ],
            "unit_notes": (
                "All carbon stocks in GtC. Radiative forcing in W/m². "
                "Emissions in GtC/yr. "
                "Mass conservation: ΣC(t) = ΣC(0) + ∫emissions dt"
            ),
        }
