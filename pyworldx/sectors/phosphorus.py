"""Phosphorus sector with Soil Organic Carbon (Phase 2 Task 2+4, q65-q66, q70, q84).

Stocks:
  P_soc: soil phosphorus (megatonnes P)
  PRR: phosphorus recycling rate (0-1 dimensionless)
  SOC: soil organic carbon (Gt C, "living matrix")

ODEs:
  dP_soc/dt = P_mining + P_recycling - P_loss - P_waste
  dPRR/dt = ProfitabilityFactor * TechnologyFactor - DissipationDelay
  dSOC/dt = litter_input - microbial_respiration - erosion_loss

Phase 2.4 addition — Soil Organic Carbon "Living Matrix" (Q84):
  SOC represents the biological soil matrix that provides moisture retention,
  root structure, and nutrient cycling. When SOC drops below SOC_critical
  (the "rooting depth resilience threshold"), the Land Yield Multiplier
  collapses non-linearly regardless of chemical phosphorus availability.

  SOC degradation drivers:
    - High pollution_index accelerates microbial die-off
    - Intensive farming (high FIOAA → high agricultural input) depletes humus
  SOC recovery:
    - Litter input from vegetation (proportional to food production proxy)

  Output: soc_resilience_multiplier (0-1) read by Agriculture sector.

Broadcasts energy_demand_phosphorus to CentralRegistrar.
Reads supply_multiplier_phosphorus from CentralRegistrar.
"""

from __future__ import annotations

import math

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup


# ── Parameters ──────────────────────────────────────────────────────────

_P_SOC0 = 14000.0       # Initial soil phosphorus (Mt P, rough global estimate)
_PRR0 = 0.12            # Initial recycling rate (~12% globally)
_BASE_MINING_RATE = 22.0  # Mt P/yr (current global mining)
_WEATHERING_RATE = 0.001  # per year (slow, geologic)
_WASTE_FRACTION = 0.001   # fraction of ag demand lost as waste
_ENERGY_PER_TONNE = 1.0   # energy units per tonne mined
_ENERGY_PER_TONNE_RECYCLED = 2.0  # recycling is more energy-intensive
_SEDIMENTATION_RATE = 0.002  # per year (lost to ocean)
_P_MIN_FOOD = 0.5       # minimum phosphorus availability for food production

# Technology factor learning curve (cumulative IO -> efficiency gain)
_TECH_LEARN_X = (0.0, 1e12, 5e12, 1e13, 5e13, 1e14)
_TECH_LEARN_Y = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# ── Soil Organic Carbon (SOC) parameters (Q84, USDA SSURGO) ──────────
#
# Global SOC stock ~1500 Gt C in top 1m (IPCC AR6, Batjes 2016).
# SOC_critical = 750 Gt C — below this, rooting depth degrades enough
# to trigger non-linear yield collapse even with adequate P/water.
_SOC0 = 1500.0             # Initial global SOC (Gt C)
_SOC_CRITICAL = 750.0      # Rooting depth resilience threshold (Gt C)
_SOC_LITTER_RATE = 0.04    # Fraction of SOC replenished by litter per yr
_SOC_RESPIRATION = 0.03    # Base microbial respiration rate per yr
_SOC_EROSION = 0.002       # Erosion/runoff loss rate per yr
_SOC_POLLUTION_SENS = 0.005  # Extra respiration per pollution index unit
_SOC_FARMING_SENS = 0.001  # Extra depletion per unit FIOAA proxy


class PhosphorusSector:
    """Phosphorus mass-balance with SOC living matrix (Q84).

    Stocks: P_soc, PRR, SOC
    Reads: industrial_output, food_per_capita, nr_fraction_remaining,
           supply_multiplier_phosphorus, pollution_index,
           frac_io_to_agriculture
    Writes: P_soc, PRR, SOC, phosphorus_mining_rate,
            phosphorus_recycling_rate, energy_demand_phosphorus,
            phosphorus_availability, soc_resilience_multiplier
    """

    name = "phosphorus"
    version = "2.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        initial_p_soc: float = _P_SOC0,
        initial_prr: float = _PRR0,
        initial_soc: float = _SOC0,
        weathering_rate: float = _WEATHERING_RATE,
        sedimentation_rate: float = _SEDIMENTATION_RATE,
    ) -> None:
        self.initial_p_soc = initial_p_soc
        self.initial_prr = initial_prr
        self.initial_soc = initial_soc
        self.weathering_rate = weathering_rate
        self.sedimentation_rate = sedimentation_rate

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "P_soc": Quantity(self.initial_p_soc, "megatonnes_P"),
            "PRR": Quantity(self.initial_prr, "dimensionless"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        P_soc = stocks["P_soc"].magnitude
        PRR = stocks["PRR"].magnitude
        # SOC is now authoritative from pollution_ghg.py (C_soc stock).
        # Fall back to initial value when running without that sector.
        SOC = inputs.get("C_soc", Quantity(self.initial_soc, "GtC")).magnitude

        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        fpc = inputs.get(
            "food_per_capita", Quantity(300.0, "food_units_per_person")
        ).magnitude
        nrfr = inputs.get(
            "nr_fraction_remaining", Quantity(1.0, "dimensionless")
        ).magnitude
        supply_mult = inputs.get(
            "supply_multiplier_phosphorus", Quantity(1.0, "dimensionless")
        ).magnitude
        ppolx = inputs.get(
            "pollution_index", Quantity(1.0, "dimensionless")
        ).magnitude
        fioaa = inputs.get(
            "frac_io_to_agriculture", Quantity(0.1, "dimensionless")
        ).magnitude

        # ── Phosphorus mass-balance ────────────────────────────────────
        # Mining rate declines with NRFR depletion
        p_mining = _BASE_MINING_RATE * nrfr * supply_mult

        # Waste is proportional to agricultural demand (proxied by food_per_capita)
        p_waste = fpc * _WASTE_FRACTION

        # Recycling
        p_recycling = p_waste * PRR

        # Loss: weathering (slow, geologic)
        p_loss = P_soc * self.weathering_rate

        # PRR dynamics
        energy_cost_mining = p_mining * _ENERGY_PER_TONNE
        energy_cost_recycling = p_recycling * _ENERGY_PER_TONNE_RECYCLED
        profitability_factor = min(
            energy_cost_mining / max(energy_cost_recycling, 1e-10), 2.0
        )

        technology_factor = table_lookup(
            io, _TECH_LEARN_X, _TECH_LEARN_Y
        )

        dissipation = P_soc * self.sedimentation_rate
        dPRR = profitability_factor * technology_factor - dissipation

        # Clamp PRR to [0, 1]
        if PRR <= 0.0 and dPRR < 0:
            dPRR = 0.0
        elif PRR >= 1.0 and dPRR > 0:
            dPRR = 0.0

        dP_soc = p_mining + p_recycling - p_loss - p_waste

        p_availability = min(P_soc / max(self.initial_p_soc, 1e-10), 1.0)

        # ── Soil Organic Carbon (SOC) dynamics (Q84) ──────────────────
        # Litter input: vegetation returns carbon to soil
        # Proportional to current SOC and food productivity proxy
        litter_input = SOC * _SOC_LITTER_RATE

        # Microbial respiration: accelerated by pollution (toxic soil effect)
        pollution_boost = max(ppolx - 1.0, 0.0) * _SOC_POLLUTION_SENS
        respiration = SOC * (_SOC_RESPIRATION + pollution_boost)

        # Intensive farming depletion: high FIOAA means heavy mechanized
        # agriculture that depletes humus faster
        farming_depletion = SOC * fioaa * _SOC_FARMING_SENS

        # Erosion/runoff (geologic)
        erosion = SOC * _SOC_EROSION

        dSOC = litter_input - respiration - farming_depletion - erosion

        # Clamp SOC >= 0
        if SOC <= 0.0 and dSOC < 0:
            dSOC = 0.0

        # ── SOC Resilience Multiplier (rooting depth threshold) ───────
        # When SOC > SOC_critical: multiplier = 1.0 (healthy soil)
        # When SOC < SOC_critical: exponential collapse
        #   mult = exp(-4.6 * ((SOC_crit - SOC) / SOC_crit)^2)
        # At SOC = 0: mult ≈ exp(-4.6) ≈ 0.01 (near-total collapse)
        if SOC >= _SOC_CRITICAL:
            soc_resilience = 1.0
        else:
            deficit = (_SOC_CRITICAL - SOC) / max(_SOC_CRITICAL, 1e-10)
            soc_resilience = math.exp(-4.6 * deficit * deficit)

        # Energy demand broadcast to CentralRegistrar
        energy_demand = (
            p_mining * _ENERGY_PER_TONNE
            + p_recycling * _ENERGY_PER_TONNE_RECYCLED
        )

        return {
            "d_P_soc": Quantity(dP_soc, "megatonnes_P"),
            "d_PRR": Quantity(dPRR, "dimensionless"),
            "phosphorus_mining_rate": Quantity(p_mining, "megatonnes_P_per_yr"),
            "phosphorus_recycling_rate": Quantity(
                p_recycling, "megatonnes_P_per_yr"
            ),
            "energy_demand_phosphorus": Quantity(
                energy_demand, "energy_units"
            ),
            "phosphorus_availability": Quantity(
                p_availability, "dimensionless"
            ),
            "soc_resilience_multiplier": Quantity(
                soc_resilience, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "industrial_output",
            "food_per_capita",
            "nr_fraction_remaining",
            "supply_multiplier_phosphorus",
            "pollution_index",
            "frac_io_to_agriculture",
            "C_soc",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "P_soc",
            "PRR",
            "phosphorus_mining_rate",
            "phosphorus_recycling_rate",
            "energy_demand_phosphorus",
            "phosphorus_availability",
            "soc_resilience_multiplier",
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
                "Mining rate scaled by NRFR (not independent depletion curve)",
                "Technology factor proxied by current IO (not cumulative)",
                "P_availability simplified as P_soc / P_soc_initial",
                "SOC uses exponential collapse below critical threshold (Q84)",
                "SOC degradation from pollution and farming intensity",
            ],
            "free_parameters": [
                "initial_p_soc",
                "initial_prr",
                "initial_soc",
                "weathering_rate",
                "sedimentation_rate",
            ],
            "conservation_groups": [],
            "observables": [
                "phosphorus_availability",
                "energy_demand_phosphorus",
                "soc_resilience_multiplier",
            ],
            "unit_notes": (
                "P_soc in megatonnes P, PRR dimensionless 0-1, "
                "SOC read from pollution_ghg C_soc (GtC), energy in energy_units"
            ),
        }
