"""Regional Trade & Migration sector (Phase 2 Task 6, from q60, q61, q70).

This sector adds inter-regional trade and migration flows to the pyWorldX
model. Rather than wrapping all sectors per region (which would require
major engine restructuring), it operates as a redistribution layer that
modifies sector outputs based on trade and migration matrices.

Trade Matrix (dissipative):
  Export[i→j] = surplus_i * trade_attractiveness_ij
  Import[j] = Σ Export[i→j] * (1 - transport_loss)
  Transport energy = Σ Export[i→j] * energy_per_unit_distance

Migration Flows:
  Migration[i→j] = f(attractiveness_j - attractiveness_i)
  Migration continues during lifeboating (trade severed)
  Destination dilution: immediate reduction in SOPC, IOPC

N regions with:
  - Regional food surpluses/deficits
  - Regional industrial output surpluses/deficits
  - Regional population and attractiveness
  - Trade linkages (can be severed during lifeboating)
"""

from __future__ import annotations

import numpy as np

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Parameters ──────────────────────────────────────────────────────────

_NUM_REGIONS = 3  # Default: Core, Periphery, Emerging
_REGION_NAMES = ["core", "periphery", "emerging"]

# Trade parameters
_TRANSPORT_LOSS = 0.05  # 5% loss during transport (spoilage, friction)
_ENERGY_PER_TRADE_UNIT = 0.01  # Energy units per unit of trade
_TRADE_ATTRACTION_BASE = np.array([
    [1.0, 0.3, 0.6],  # Core trades mostly with Emerging
    [0.3, 1.0, 0.5],  # Periphery trades weakly
    [0.6, 0.5, 1.0],  # Emerging trades with both
])

# Migration parameters
_MIGRATION_SENSITIVITY = 0.1  # Migration rate per unit attractiveness gap
_MIGRATION_THRESHOLD = 0.05   # Minimum attractiveness gap for migration
_MIGRATION_COST = 0.01        # Fixed migration cost (reduces flow)

# Lifeboating threshold
_LIFEBOATING_FPC_THRESHOLD = 150.0  # Food per capita below which region lifeboats

# Energy demand
_TOTAL_AVAILABLE_ENERGY = 600.0  # EJ/year (global baseline)


class RegionalTradeSector:
    """Regional trade and migration flows.

    Reads: food_per_capita, industrial_output, POP, temperature_anomaly,
           trade_linkages (optional binary matrix)
    Writes: regional_food_per_capita, regional_industrial_output,
            migration_flows, trade_flows, energy_demand_regional_trade,
            supply_multiplier_regional_trade, lifeboating_active
    """

    name = "regional_trade"
    version = "1.0.0"
    timestep_hint: float | None = None

    def __init__(
        self,
        num_regions: int = _NUM_REGIONS,
        transport_loss: float = _TRANSPORT_LOSS,
        migration_sensitivity: float = _MIGRATION_SENSITIVITY,
        lifeboating_fpc_threshold: float = _LIFEBOATING_FPC_THRESHOLD,
    ) -> None:
        self.num_regions = num_regions
        self.transport_loss = transport_loss
        self.migration_sensitivity = migration_sensitivity
        self.lifeboating_fpc_threshold = lifeboating_fpc_threshold
        # Generate region names dynamically
        base_names = _REGION_NAMES[:min(num_regions, len(_REGION_NAMES))]
        self.region_names = list(base_names) + [
            f"region_{i}" for i in range(len(base_names), num_regions)
        ]

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        """No stocks — pure redistribution sector."""
        return {}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        # Read global variables
        global_fpc = inputs.get(
            "food_per_capita", Quantity(300.0, "food_units_per_person")
        ).magnitude
        global_io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        global_pop = inputs.get(
            "POP", Quantity(2.1e9, "persons")
        ).magnitude
        temp_anomaly = inputs.get(
            "temperature_anomaly", Quantity(0.0, "deg_C_anomaly")
        ).magnitude

        # Distribute population across regions (simplified distribution)
        # In a full implementation, these would be read from regional sectors
        pop_base = [0.5, 0.2, 0.3]
        pop_distribution = np.array(
            pop_base + [0.0] * max(0, self.num_regions - 3)
        )[:self.num_regions]
        # If more than 3 regions, distribute remaining evenly
        if self.num_regions > 3:
            remaining = 1.0 - pop_distribution[:3].sum()
            pop_distribution[3:] = remaining / (self.num_regions - 3)
        pop_distribution /= pop_distribution.sum()
        regional_pop = global_pop * pop_distribution

        # Distribute food and IO across regions with some inequality
        # Core gets more, periphery gets less
        fpc_base = [1.2, 0.6, 0.9]
        fpc_distribution = np.array(
            fpc_base + [0.9] * max(0, self.num_regions - 3)
        )[:self.num_regions]
        fpc_distribution /= fpc_distribution.sum()  # Normalize to 1.0
        regional_fpc = global_fpc * fpc_distribution * self.num_regions

        io_base = [0.6, 0.1, 0.3]
        io_distribution = np.array(
            io_base + [0.0] * max(0, self.num_regions - 3)
        )[:self.num_regions]
        if self.num_regions > 3:
            remaining = 1.0 - io_distribution[:3].sum()
            io_distribution[3:] = remaining / (self.num_regions - 3)
        io_distribution /= io_distribution.sum()
        regional_io = global_io * io_distribution

        # ── Trade Matrix ───────────────────────────────────────────────
        # Calculate regional surpluses/deficits
        fpc_reference = 250.0  # Reference food per capita for self-sufficiency
        food_surplus = (regional_fpc - fpc_reference) * regional_pop

        # Trade attraction matrix: build dynamically based on num_regions
        trade_attraction = np.ones((self.num_regions, self.num_regions))
        np.fill_diagonal(trade_attraction, 1.0)
        # Core (index 0) trades more broadly; periphery trades locally
        for i in range(self.num_regions):
            for j in range(self.num_regions):
                if i != j:
                    # Closer regions trade more
                    distance = abs(i - j)
                    trade_attraction[i, j] = max(0.1, 1.0 - distance * 0.3)

        # Temperature stress reduces trade attractiveness
        if temp_anomaly > 2.0:
            trade_attraction *= max(1.0 - temp_anomaly * 0.05, 0.1)

        # Compute trade flows
        trade_flows = np.zeros((self.num_regions, self.num_regions))
        for i in range(self.num_regions):
            for j in range(self.num_regions):
                if i == j:
                    continue
                if food_surplus[i] > 0 and food_surplus[j] < 0:
                    # Export from surplus to deficit region
                    export = min(
                        food_surplus[i] * 0.3,  # Export 30% of surplus
                        abs(food_surplus[j]) * trade_attraction[i, j]
                    )
                    trade_flows[i, j] = max(export, 0.0)

        # Apply transport losses (dissipative)
        received_trade = trade_flows * (1.0 - self.transport_loss)

        # Update regional food based on trade
        for j in range(self.num_regions):
            net_import = received_trade[:, j].sum() - trade_flows[j, :].sum()
            regional_fpc[j] += net_import / max(regional_pop[j], 1.0)

        # ── Migration Flows ────────────────────────────────────────────
        # Attractiveness = weighted combination of FPC, IO per capita
        iopc = regional_io / np.maximum(regional_pop, 1.0)
        attractiveness = (
            0.6 * np.clip(regional_fpc / fpc_reference, 0, 2)
            + 0.4 * np.clip(iopc / 400.0, 0, 2)  # Normalize IO per capita
        )

        # Migration: from low to high attractiveness
        migration_flows = np.zeros((self.num_regions, self.num_regions))
        for i in range(self.num_regions):
            for j in range(self.num_regions):
                if i == j:
                    continue
                attractiveness_gap = attractiveness[j] - attractiveness[i]
                if attractiveness_gap > _MIGRATION_THRESHOLD:
                    migration_rate = self.migration_sensitivity * (
                        attractiveness_gap - _MIGRATION_THRESHOLD
                    )
                    migration_flows[i, j] = (
                        regional_pop[i] * migration_rate
                    )

        # Apply migration to population
        for i in range(self.num_regions):
            net_migration = migration_flows[:, i].sum() - migration_flows[i, :].sum()
            regional_pop[i] += net_migration

        # ── Lifeboating Detection ──────────────────────────────────────
        lifeboating_active = np.array([
            regional_fpc[i] < self.lifeboating_fpc_threshold
            for i in range(self.num_regions)
        ])

        # During lifeboating, trade is severed but migration continues
        for i in range(self.num_regions):
            if lifeboating_active[i]:
                trade_flows[i, :] = 0.0
                trade_flows[:, i] = 0.0

        # ── Energy Demand for Trade ────────────────────────────────────
        total_trade_volume = trade_flows.sum()
        energy_demand = total_trade_volume * _ENERGY_PER_TRADE_UNIT

        # ── Supply Multiplier ──────────────────────────────────────────
        # Trade supply multiplier: 1.0 if trade is flowing, 0.0 if lifeboating
        trade_supply_mult = 1.0 if not lifeboating_active.any() else 0.5

        outputs: dict[str, Quantity] = {}

        # Write regional variables
        for i, name in enumerate(self.region_names):
            outputs[f"regional_fpc_{name}"] = Quantity(
                regional_fpc[i], "food_units_per_person"
            )
            outputs[f"regional_io_{name}"] = Quantity(
                regional_io[i], "industrial_output_units"
            )
            outputs[f"regional_pop_{name}"] = Quantity(
                regional_pop[i], "persons"
            )

        # Aggregate scalar migration signal for population sector
        total_migration_flow = float(migration_flows.sum())

        # Food lost to transport spoilage (sent but not received)
        trade_food_loss = float(total_trade_volume * self.transport_loss)

        # Write trade and migration flows
        outputs["total_migration_flow"] = Quantity(
            total_migration_flow, "persons_per_year"
        )
        outputs["trade_food_loss"] = Quantity(
            trade_food_loss, "food_units"
        )
        outputs["energy_demand_regional_trade"] = Quantity(
            energy_demand, "energy_units"
        )
        outputs["supply_multiplier_regional_trade"] = Quantity(
            trade_supply_mult, "dimensionless"
        )
        outputs["lifeboating_active"] = Quantity(
            float(lifeboating_active.any()), "dimensionless"
        )
        outputs["total_trade_volume"] = Quantity(
            total_trade_volume, "food_units"
        )

        return outputs

    def declares_reads(self) -> list[str]:
        return [
            "food_per_capita",
            "industrial_output",
            "POP",
            "temperature_anomaly",
        ]

    def declares_writes(self) -> list[str]:
        writes = []
        for name in self.region_names:
            writes.extend([
                f"regional_fpc_{name}",
                f"regional_io_{name}",
                f"regional_pop_{name}",
            ])
        writes.extend([
            "energy_demand_regional_trade",
            "supply_multiplier_regional_trade",
            "lifeboating_active",
            "total_trade_volume",
            "total_migration_flow",
            "trade_food_loss",
        ])
        return writes

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.DESIGN_CHOICE,
            "world7_alignment": WORLD7Alignment.NONE,
            "approximations": [
                "Population distribution fixed (not endogenous)",
                "Trade matrix is static (not dynamically computed)",
                "Migration uses simple attractiveness gap model",
                "Lifeboating severs trade but not migration",
                "Transport losses are fixed fraction (not distance-based)",
            ],
            "free_parameters": [
                "num_regions",
                "transport_loss",
                "migration_sensitivity",
                "lifeboating_fpc_threshold",
            ],
            "conservation_groups": [],
            "observables": [
                "energy_demand_regional_trade",
                "supply_multiplier_regional_trade",
                "lifeboating_active",
                "total_trade_volume",
            ],
            "unit_notes": (
                "Regional FPC in food_units_per_person, "
                "regional IO in industrial_output_units, "
                "energy_demand in energy_units"
            ),
        }
