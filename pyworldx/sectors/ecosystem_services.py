"""Ecosystem Services sector (Phase 2 Task 3, from q67, q68, q70).

Stock:
  ESP: ecosystem services proxy (0-1 scale, initial=1.0)

ODE:
  dESP/dt = r(T) * ESP * (1 - ESP) - DegradationRate

r(T) = r0 * f(T)  # temperature-dependent regeneration rate
  DegradationRate = pollution_degradation + land_use_degradation
  pollution_degradation = pollution_index * pollution_sensitivity
  land_use_degradation = (PAL - AL) / PAL * land_use_sensitivity

Service Deficit = 1.0 - ESP
TNDS_AES = c_AES * (Service Deficit)^exponent  # exponential scaling

AES investment drains Liquid Funds from FinanceSector (dL/dt -= TNDS_AES).

Broadcasts energy_demand_aes to CentralRegistrar.
Reads supply_multiplier_aes from CentralRegistrar.
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Parameters ──────────────────────────────────────────────────────────

_ESP0 = 1.0               # Pre-industrial optimal ESP
_R0 = 0.05               # Base regeneration rate (per year)
_POLLUTION_SENSITIVITY = 0.001  # ESP degradation per pollution index unit
_LAND_USE_SENSITIVITY = 0.1     # ESP degradation per land-use fraction
_C_AES = 6.7e11          # AES cost intensity (capital units per deficit unit)
_AES_EXPONENT = 2.5      # Exponential scaling (super-linear, q76)
_ENERGY_PER_AES = 1.0    # Energy units per TNDS_AES unit
_PAL = 6.0e9            # Potential arable land (hectares), global max


class EcosystemServicesSector:
    """Ecosystem Services Proxy with AES replacement cost.

    Stock: ESP (0-1, initial=1.0)
    Reads: pollution_index, AL, temperature_anomaly,
           supply_multiplier_aes
    Writes: ESP, tnds_aes, service_deficit, energy_demand_aes,
            esp_multiplier
    """

    name = "ecosystem_services"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_esp: float = _ESP0,
        r0: float = _R0,
        pollution_sensitivity: float = _POLLUTION_SENSITIVITY,
        land_use_sensitivity: float = _LAND_USE_SENSITIVITY,
        c_aes: float = _C_AES,
        aes_exponent: float = _AES_EXPONENT,
    ) -> None:
        self.initial_esp = initial_esp
        self.r0 = r0
        self.pollution_sensitivity = pollution_sensitivity
        self.land_use_sensitivity = land_use_sensitivity
        self.c_aes = c_aes
        self.aes_exponent = aes_exponent

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"ESP": Quantity(self.initial_esp, "dimensionless")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        ESP = stocks["ESP"].magnitude

        ppolx = inputs.get(
            "pollution_index", Quantity(1.0, "dimensionless")
        ).magnitude
        al = inputs.get(
            "AL", Quantity(0.9e9, "hectares")
        ).magnitude
        temp_anomaly = inputs.get(
            "temperature_anomaly", Quantity(0.0, "deg_C_anomaly")
        ).magnitude
        supply_mult = inputs.get(
            "supply_multiplier_aes", Quantity(1.0, "dimensionless")
        ).magnitude

        # Temperature-dependent regeneration rate (piecewise quadratic, q72)
        T_opt = 15.0  # optimal temp anomaly (°C)
        T_crit = 35.0  # critical temp anomaly (°C)
        if temp_anomaly <= T_opt:
            temp_factor = 1.0
        elif temp_anomaly >= T_crit:
            temp_factor = 0.0
        else:
            ratio = (temp_anomaly - T_opt) / (T_crit - T_opt)
            temp_factor = 1.0 - ratio * ratio
        r_t = self.r0 * temp_factor * supply_mult

        # Logistic regeneration: r(T) * ESP * (1 - ESP)
        regeneration = r_t * ESP * max(1.0 - ESP, 0.0)

        # Degradation from pollution
        pollution_degradation = ppolx * self.pollution_sensitivity

        # Degradation from land use change
        land_use_frac = 1.0 - al / max(_PAL, 1e-10)
        land_use_degradation = max(land_use_frac, 0.0) * self.land_use_sensitivity

        degradation_rate = pollution_degradation + land_use_degradation

        # Net change
        dESP = regeneration - degradation_rate

        # Clamp ESP to [0, 1]
        if ESP <= 0.0 and dESP < 0:
            dESP = 0.0
        elif ESP >= 1.0 and dESP > 0:
            dESP = 0.0

        # Service deficit and AES cost (TNDS)
        service_deficit = max(1.0 - ESP, 0.0)
        tnds_aes = self.c_aes * (service_deficit ** self.aes_exponent)

        # Energy demand for AES deployment
        energy_demand = tnds_aes * _ENERGY_PER_AES

        # ESP multiplier for other sectors (1.0 = full ecosystem services)
        esp_multiplier = max(ESP, 0.0)

        return {
            "d_ESP": Quantity(dESP, "dimensionless"),
            "tnds_aes": Quantity(tnds_aes, "capital_units"),
            "service_deficit": Quantity(service_deficit, "dimensionless"),
            "energy_demand_aes": Quantity(energy_demand, "energy_units"),
            "esp_multiplier": Quantity(esp_multiplier, "dimensionless"),
        }

    def declares_reads(self) -> list[str]:
        return [
            "pollution_index",
            "AL",
            "temperature_anomaly",
            "supply_multiplier_aes",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "ESP",
            "tnds_aes",
            "service_deficit",
            "energy_demand_aes",
            "esp_multiplier",
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
                "Temperature suppression of r(T) is piecewise quadratic (q72)",
                "Land-use degradation uses simple fraction (PAL - AL) / PAL",
                "AES cost scales as deficit^2.5 (exponent from q76)",
                "Energy demand proportional to TNDS_AES",
            ],
            "free_parameters": [
                "initial_esp",
                "r0",
                "pollution_sensitivity",
                "land_use_sensitivity",
                "c_aes",
                "aes_exponent",
            ],
            "conservation_groups": [],
            "observables": ["ESP", "tnds_aes", "service_deficit"],
            "unit_notes": (
                "ESP dimensionless 0-1, TNDS_AES in capital_units, "
                "energy_demand in energy_units"
            ),
        }
