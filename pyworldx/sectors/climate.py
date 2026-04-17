"""Climate module (Phase 2 Task 4, from q62, q63, q70).

Stocks:
  T: temperature anomaly (°C above pre-industrial, initial=0.0)
  A: aerosol concentration index (dimensionless, initial=1.0)

ODEs:
  dT/dt = lambda * [RF_GHG - RF_Aero] - OceanThermalInertia * T
  dA/dt = k_aero * industrial_output - A / tau_aero

RF_GHG = 5.35 * ln(CO2 / CO2_preindustrial)
  CO2 proxied by pollution_generation
RF_Aero = k_aero_rf * A

tau_aero = 0.05 years (~2 weeks)
lambda = climate_sensitivity (°C per W/m²)
OceanThermalInertia = 1 / ocean_response_time

Heat Shock Multiplier to Agriculture:
  heat_shock_multiplier = 1.0 at T=0
  drops non-linearly above threshold (e.g., 2.0°C)
  zero above critical wet-bulb threshold (~35°C anomaly)

Broadcasts energy_demand_climate to CentralRegistrar.
"""

from __future__ import annotations

import math

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Parameters ──────────────────────────────────────────────────────────

_T0 = 0.0               # Pre-industrial temperature anomaly (°C)
_A0 = 1.0               # Pre-industrial aerosol concentration
_LAMBDA = 0.8           # Climate sensitivity (°C per W/m²)
_RF_GHG_COEFF = 5.35    # CO2 radiative forcing coefficient (W/m²)
_CO2_PREINDUSTRIAL = 280.0  # ppm
_RF_AERO_COEFF = 1.0    # Aerosol radiative forcing coefficient
_K_AERO = 1e-12         # Aerosol production rate per industrial output
_TAU_AERO = 0.05        # Aerosol decay constant (~2 weeks)
_OCEAN_THERMAL_INERTIA = 0.02  # Ocean response (per year)
_HEAT_SHOCK_THRESHOLD = 2.0   # °C anomaly before yield declines
_HEAT_SHOCK_CRITICAL = 5.0   # °C anomaly where yield hits zero
_ENERGY_PER_DEGREE = 1.0e10  # Energy units per °C of heating/cooling demand


class ClimateSector:
    """Climate module with GHG/aerosol bifurcation.

    Stocks: T, A
    Reads: industrial_output, pollution_generation,
           supply_multiplier_climate
    Writes: T, A, temperature_anomaly, aerosol_index,
            radiative_forcing_ghg, radiative_forcing_aero,
            heat_shock_multiplier, energy_demand_climate
    """

    name = "climate"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_t: float = _T0,
        initial_a: float = _A0,
        climate_sensitivity: float = _LAMBDA,
        tau_aero: float = _TAU_AERO,
    ) -> None:
        self.initial_t = initial_t
        self.initial_a = initial_a
        self.climate_sensitivity = climate_sensitivity
        self.tau_aero = tau_aero

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "T": Quantity(self.initial_t, "deg_C_anomaly"),
            "A": Quantity(self.initial_a, "dimensionless"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        T = stocks["T"].magnitude
        A = stocks["A"].magnitude

        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        pollution_gen = inputs.get(
            "pollution_generation", Quantity(0.0, "pollution_units")
        ).magnitude
        supply_mult = inputs.get(
            "supply_multiplier_climate", Quantity(1.0, "dimensionless")
        ).magnitude

        # CO2 proxy from pollution generation (normalized)
        co2 = _CO2_PREINDUSTRIAL + pollution_gen * 1e-6

        # Radiative forcing from GHG
        rf_ghg = _RF_GHG_COEFF * math.log(
            max(co2 / _CO2_PREINDUSTRIAL, 1e-10)
        )

        # Radiative forcing from aerosols (cooling, so negative)
        rf_aero = _RF_AERO_COEFF * A

        # Temperature ODE
        dT = (
            self.climate_sensitivity * (rf_ghg - rf_aero)
            - _OCEAN_THERMAL_INERTIA * T
        )

        # Aerosol: tau_aero is ~2 weeks, so aerosol is always at
        # quasi-equilibrium with industrial output. Compute algebraically
        # rather than integrating the stiff ODE.
        # Steady state: dA/dt = 0 → A = k_aero * io * tau_aero
        A = _K_AERO * io * self.tau_aero * supply_mult
        dA = 0.0  # Already at equilibrium

        # Heat Shock Multiplier to Agriculture
        # 1.0 below threshold, drops to 0 at critical threshold (q73)
        if T <= _HEAT_SHOCK_THRESHOLD:
            heat_shock_multiplier = 1.0
        elif T >= _HEAT_SHOCK_CRITICAL:
            heat_shock_multiplier = 0.0
        else:
            # Exponential/quadratic decline between threshold and critical
            ratio = (T - _HEAT_SHOCK_THRESHOLD) / (
                _HEAT_SHOCK_CRITICAL - _HEAT_SHOCK_THRESHOLD
            )
            heat_shock_multiplier = math.exp(-4.6 * ratio * ratio)

        # Energy demand for heating/cooling (proportional to |T|)
        energy_demand = abs(T) * _ENERGY_PER_DEGREE

        return {
            "d_T": Quantity(dT, "deg_C_anomaly"),
            "d_A": Quantity(dA, "dimensionless"),
            "temperature_anomaly": Quantity(T, "deg_C_anomaly"),
            "aerosol_index": Quantity(A, "dimensionless"),
            "radiative_forcing_ghg": Quantity(rf_ghg, "W_per_m2"),
            "radiative_forcing_aero": Quantity(rf_aero, "W_per_m2"),
            "heat_shock_multiplier": Quantity(
                heat_shock_multiplier, "dimensionless"
            ),
            "energy_demand_climate": Quantity(
                energy_demand, "energy_units"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "industrial_output",
            "pollution_generation",
            "supply_multiplier_climate",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "T",
            "A",
            "temperature_anomaly",
            "aerosol_index",
            "radiative_forcing_ghg",
            "radiative_forcing_aero",
            "heat_shock_multiplier",
            "energy_demand_climate",
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
                "CO2 proxied by pollution_generation (not actual CO2 stock)",
                "Single-box energy balance (no deep ocean compartment)",
                "Heat shock multiplier exponential decline from threshold to critical (q73)",
                "Energy demand proportional to |T| (simplified)",
            ],
            "free_parameters": [
                "initial_t",
                "initial_a",
                "climate_sensitivity",
                "tau_aero",
            ],
            "conservation_groups": [],
            "observables": [
                "temperature_anomaly",
                "heat_shock_multiplier",
                "energy_demand_climate",
            ],
            "unit_notes": (
                "T in deg_C_anomaly, A dimensionless, "
                "radiative forcing in W/m²"
            ),
        }
