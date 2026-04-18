"""CentralRegistrar — Pre-Derivative Resolution Pass (Phase 1 Task 1).

Enforces the 65% Energy Ceiling and resolves SupplyMultipliers before
sectors finalize their derivatives. Sits between sector demand broadcasting
and derivative calculation in the engine loop.

Phase 2 upgrade: EIA energy baseline calibration (Q77, Q84).
  All energy flows converted to EJ/yr via _EJ_SCALE before ceiling check.
  Supply computed from actual energy sector outputs, not abstract total_output.

Architecture (from Q09, Q52):
  Per RK4 sub-step:
    1. Sectors compute() — write demands to shared_state
    2. CentralRegistrar reads demands, checks 65% Energy Ceiling
    3. If ceiling breached: compute SupplyMultipliers < 1.0
       Allocation based on: (a) Ability to Pay, (b) Security Value
    4. Write SupplyMultipliers back to shared_state
    5. Sectors compute derivatives with multipliers applied

Key design decisions from Q52:
  - NOT equal scaling — Ability to Pay + Security Value determine access
  - Basic survival sectors are NOT universally protected
  - Loop avoidance: State-Gating (every cross-sector loop contains
    Integrator or Delay) + 1/512 dt overshoot tolerance
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyworldx.core.quantities import Quantity


# ── Constants ─────────────────────────────────────────────────────────

_ENERGY_CEILING = 0.65  # 65% of total output dedicated to energy extraction max
_OVERSHOOT_TOLERANCE = 1.0 / 512  # brief ceiling overshoot tolerance (1/512)

# ── EIA Energy Baseline Calibration (Q77, Q84) ───────────────────────
#
# Scale factor: abstract "energy_units" → EJ/yr (exajoules per year)
# At 1900: fossil_output=1e11 + sustainable_output=8e9 + technology_output=5e9
#        = 1.13e11 abstract units ≡ 22 EJ/yr (historical EIA/BP baseline)
# _EJ_SCALE = 22.0 / 1.13e11 ≈ 1.9469e-10
_EJ_SCALE = 1.946903e-10
EJ_SCALE = _EJ_SCALE  # public alias for tests and consumers

# Shared-state keys that contribute to total energy supply
_ENERGY_SUPPLY_KEYS = ("fossil_output", "sustainable_output", "technology_output")


@dataclass
class DemandRecord:
    """A sector's demand for energy or material resources."""

    sector_name: str
    demand: float  # absolute energy demand units
    liquid_funds: float = 0.0  # Ability to Pay
    security_value: float = 0.0  # capital/strategic priority weight


@dataclass
class SupplyResolution:
    """Result of the CentralRegistrar's demand resolution pass."""

    total_demand: float
    total_supply: float
    ceiling_breached: bool
    multipliers: dict[str, float] = field(default_factory=dict)


class CentralRegistrar:
    """Pre-derivative resolution pass enforcing the 65% Energy Ceiling.

    Phase 2: Energy flows calibrated to EJ/yr (Q77, Q84).
    Supply computed from fossil_output + sustainable_output + technology_output.

    Usage:
        registrar = CentralRegistrar(energy_ceiling=0.65)

        # In engine loop:
        resolution = registrar.resolve(shared_state)
        # resolution.multipliers written back to shared_state

    The CentralRegistrar is OPTIONAL — when disabled (default for v1
    backward compatibility), sectors operate without supply constraints.
    """

    def __init__(
        self,
        energy_ceiling: float = _ENERGY_CEILING,
        overshoot_tolerance: float = _OVERSHOOT_TOLERANCE,
        enabled: bool = True,
    ) -> None:
        self.energy_ceiling = energy_ceiling
        self.overshoot_tolerance = overshoot_tolerance
        self.enabled = enabled

    def resolve(self, shared: dict[str, Quantity]) -> SupplyResolution:
        """Read demands from shared state, enforce ceiling, write multipliers.

        Supply is computed from energy sector outputs (EJ/yr):
          fossil_output + sustainable_output + technology_output

        Reads from shared_state:
          - fossil_output, sustainable_output, technology_output (supply)
          - energy_demand_{sector_name}: float — each sector's energy demand
          - liquid_funds_{sector_name}: float — each sector's Ability to Pay
          - security_value_{sector_name}: float — each sector's strategic priority

        Writes to shared_state:
          - supply_multiplier_{sector_name}: float (0.0–1.0)
          - total_energy_supply_ej: float (EJ/yr)
          - total_energy_demand_ej: float (EJ/yr)
        """
        if not self.enabled:
            return SupplyResolution(
                total_demand=0.0,
                total_supply=0.0,
                ceiling_breached=False,
                multipliers={},
            )

        # ── 1. Compute total energy supply from sector outputs ───────
        # Sum energy sector outputs and convert to EJ/yr.
        total_supply_abstract = 0.0
        for supply_key in _ENERGY_SUPPLY_KEYS:
            val = shared.get(supply_key)
            if val is not None:
                total_supply_abstract += max(val.magnitude, 0.0)

        total_supply_ej = total_supply_abstract * _EJ_SCALE
        total_supply = total_supply_ej * self.energy_ceiling

        # Write observability variables
        shared["total_energy_supply_ej"] = Quantity(
            total_supply_ej, "EJ_per_yr"
        )

        # ── 2. Collect demands from shared state ─────────────────────
        demands: list[DemandRecord] = []

        for key, val in shared.items():
            if key.startswith("energy_demand_"):
                sector_name = key.replace("energy_demand_", "")
                lf_key = f"liquid_funds_{sector_name}"
                sv_key = f"security_value_{sector_name}"
                # Convert demand to EJ/yr
                demand_ej = val.magnitude * _EJ_SCALE
                demands.append(DemandRecord(
                    sector_name=sector_name,
                    demand=demand_ej,
                    liquid_funds=shared.get(
                        lf_key, Quantity(1.0, "dimensionless")
                    ).magnitude,
                    security_value=shared.get(
                        sv_key, Quantity(1.0, "dimensionless")
                    ).magnitude,
                ))

        if not demands:
            shared["total_energy_demand_ej"] = Quantity(
                0.0, "EJ_per_yr"
            )
            return SupplyResolution(
                total_demand=0.0,
                total_supply=total_supply,
                ceiling_breached=False,
                multipliers={},
            )

        total_demand = sum(d.demand for d in demands)
        shared["total_energy_demand_ej"] = Quantity(
            total_demand, "EJ_per_yr"
        )

        # Global energy supply factor: ratio of available supply to total demand (capped at 1.0)
        esf = min(total_supply / max(total_demand, 1e-15), 1.0)
        shared["energy_supply_factor"] = Quantity(esf, "dimensionless")

        # ── 3. Check ceiling ───────────────────────────────────────
        ceiling_breached = total_demand > total_supply * (
            1.0 + self.overshoot_tolerance
        )

        if not ceiling_breached:
            # All demands satisfied — multipliers all 1.0
            multipliers = {d.sector_name: 1.0 for d in demands}
            for d in demands:
                shared[f"supply_multiplier_{d.sector_name}"] = Quantity(
                    1.0, "dimensionless"
                )
            return SupplyResolution(
                total_demand=total_demand,
                total_supply=total_supply,
                ceiling_breached=False,
                multipliers=multipliers,
            )

        # ── 4. Allocate based on Ability to Pay + Security Value ─────
        multipliers = self._allocate(demands, total_supply)

        # ── 5. Write multipliers back to shared state ────────────────
        for sector_name, mult in multipliers.items():
            shared[f"supply_multiplier_{sector_name}"] = Quantity(
                mult, "dimensionless"
            )

        return SupplyResolution(
            total_demand=total_demand,
            total_supply=total_supply,
            ceiling_breached=True,
            multipliers=multipliers,
        )

    def _allocate(
        self,
        demands: list[DemandRecord],
        total_supply: float,
    ) -> dict[str, float]:
        """Allocate constrained supply based on Ability to Pay + Security Value.

        NOT equal scaling — sectors with higher Liquid Funds and higher
        Security Value get proportionally larger shares of the supply.

        Combined weight = 0.5 * normalized(liquid_funds) + 0.5 * normalized(security_value)
        Then: allocation_i = weight_i / Σ(weight_j) * total_supply
        Finally: multiplier_i uses super-linear decline (q78 resolution):
          - SM = (allocation/demand)^1.5 for 50%–100% ratio
          - SM = (allocation/demand)^2.0 below 50% (cascading failure)
          - SM = 1.0 at or above 100% ratio
        """
        if not demands:
            return {}

        # Demand-weighted fallback: when ALL sectors have default weights (1.0),
        # no sector has declared Ability to Pay, so allocate proportional to demand.
        # This gives every sector the same multiplier = total_supply / total_demand.
        all_default = all(
            d.liquid_funds == 1.0 and d.security_value == 1.0 for d in demands
        )
        if all_default:
            total_demand = sum(d.demand for d in demands)
            common_ratio = total_supply / max(total_demand, 1e-15)
            multipliers: dict[str, float] = {}
            for d in demands:
                if common_ratio >= 1.0:
                    mult = 1.0
                elif common_ratio < 0.5:
                    mult = max(0.0, common_ratio ** 2.0)
                else:
                    mult = common_ratio ** 1.5
                multipliers[d.sector_name] = mult
            return multipliers

        # Compute combined weights
        total_lf = sum(d.liquid_funds for d in demands)
        total_sv = sum(d.security_value for d in demands)

        weights: dict[str, float] = {}
        for d in demands:
            # Normalize each component (handle zero-sum edge case)
            lf_norm = d.liquid_funds / max(total_lf, 1e-15)
            sv_norm = d.security_value / max(total_sv, 1e-15)
            # Equal weighting of Ability to Pay and Security Value
            weights[d.sector_name] = 0.5 * lf_norm + 0.5 * sv_norm

        total_weight = sum(weights.values())

        multipliers = {}
        for d in demands:
            w = weights[d.sector_name] / max(total_weight, 1e-15)
            allocation = w * total_supply
            # Super-linear decline: SM = (available/required)^1.5 (q78)
            # Below 50% triggers cascading failure warning
            raw_ratio = allocation / max(d.demand, 1e-15)
            if raw_ratio >= 1.0:
                mult = 1.0
            elif raw_ratio < 0.5:
                # Cascading failure: exponential decline below 50%
                mult = max(0.0, raw_ratio ** 2.0)
            else:
                # Super-linear decline between 50% and 100%
                mult = raw_ratio ** 1.5
            multipliers[d.sector_name] = max(mult, 0.0)

        return multipliers
