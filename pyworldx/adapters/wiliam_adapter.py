"""WILIAM economy adapter (Section 15).

Expresses intent for multi-rate execution via WiliamAdapterConfig.substep_ratio.
At engine init, timestep_hint is a computed property: master_dt / substep_ratio.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyworldx.adapters.base import VariableMapping


@dataclass
class WiliamAdapterConfig:
    """WILIAM adapter configuration (Section 15.1)."""

    substep_ratio: int = 4
    price_base_year: int = 2015
    price_base_currency: str = "EUR"


class WiliamEconomyAdapter:
    """WILIAM-derived economy adapter.

    timestep_hint is a computed property derived from master_dt and substep_ratio.
    resolve_substep_ratio() is still called on this value.
    """

    name: str = "wiliam_economy"
    version: str = "1.1.0"
    _master_dt: float | None = None

    def __init__(self, config: WiliamAdapterConfig | None = None) -> None:
        self.config = config or WiliamAdapterConfig()

    def set_master_dt(self, master_dt: float) -> None:
        """Called by engine at init to set master timestep."""
        self._master_dt = master_dt

    @property
    def timestep_hint(self) -> float | None:
        """Computed: master_dt / substep_ratio (Section 15.1)."""
        if self._master_dt is None:
            return None
        return self._master_dt / self.config.substep_ratio

    NAME_MAP: dict[str, str] = {
        "GDP": "capital.industrial_output",
        "gross_fixed_capital_formation": "capital.industrial_stock",
        "government_consumption": "capital.service_output",
        "military_spending": "capital.military_allocation",
        "household_consumption": "welfare.consumption",
    }

    def translate_name(self, source_name: str) -> str:
        if source_name in self.NAME_MAP:
            return self.NAME_MAP[source_name]
        raise KeyError(f"No mapping for WILIAM variable: {source_name}")

    def convert_units(
        self, value: float, source_unit: str, target_unit: str
    ) -> float:
        return value

    def get_mappings(self) -> list[VariableMapping]:
        mappings: list[VariableMapping] = []
        for source, target in self.NAME_MAP.items():
            mappings.append(
                VariableMapping(
                    source_var=source,
                    target_vars=[target],
                    weight_fn=lambda state, t: [1.0],
                    equation_source="WILIAM economic model",
                    is_static=True,
                )
            )
        return mappings

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.config.substep_ratio < 1:
            issues.append("substep_ratio must be >= 1")
        return issues
