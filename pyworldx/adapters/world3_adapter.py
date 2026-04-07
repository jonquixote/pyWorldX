"""World3-03 to pyWorldX adapter (Section 7.4).

Maps World3 variable names to canonical ontology entities.
Handles the nonrenewable resources time-varying allocator.
"""

from __future__ import annotations

from typing import Any

from pyworldx.adapters.base import VariableMapping


class World3Adapter:
    """Adapter between World3-03 nomenclature and pyWorldX ontology."""

    name: str = "world3_03"
    version: str = "1.0.0"

    NAME_MAP: dict[str, str] = {
        "Population": "population.total",
        "Industrial_Output": "capital.industrial_output",
        "Food_Per_Capita": "food.per_capita",
        "Persistent_Pollution": "pollution.persistent_load",
        "Nonrenewable_Resources": "resources.nonrenewable_stock",
        "Service_Output_Per_Capita": "capital.service_output",
        "Industrial_Capital": "capital.industrial_stock",
        "Service_Capital": "capital.service_stock",
        "Arable_Land": "agriculture.arable_land",
        "Life_Expectancy": "population.life_expectancy",
        "Human_Welfare_Index": "welfare.index",
        "Human_Ecological_Footprint": "welfare.ecological_footprint",
        "Pollution_Index": "pollution.index",
        "Extraction_Rate": "resources.extraction_rate",
        "Birth_Rate": "population.birth_rate",
        "Death_Rate": "population.death_rate",
    }

    UNIT_MAP: dict[str, str] = {
        "persons": "people",
        "dollars": "capital_units",
        "resource_units": "resource_units",
        "pollution_units": "pollution_units",
        "vegetal_equiv_kg": "food_units",
        "hectares": "hectares",
        "years": "years",
        "dimensionless": "dimensionless",
    }

    def translate_name(self, source_name: str) -> str:
        if source_name in self.NAME_MAP:
            return self.NAME_MAP[source_name]
        raise KeyError(f"No mapping for World3 variable: {source_name}")

    def convert_units(
        self, value: float, source_unit: str, target_unit: str
    ) -> float:
        return value  # World3 uses abstract units; identity conversion

    def get_mappings(self) -> list[VariableMapping]:
        mappings: list[VariableMapping] = []
        for source, target in self.NAME_MAP.items():
            if source != "Nonrenewable_Resources":
                mappings.append(
                    VariableMapping(
                        source_var=source,
                        target_vars=[target],
                        weight_fn=lambda state, t: [1.0],
                        equation_source="World3-03 direct mapping",
                        is_static=True,
                    )
                )
        # NR: time-varying allocator (Section 7.4)
        mappings.append(
            VariableMapping(
                source_var="Nonrenewable_Resources",
                target_vars=[
                    "resources.nonrenewable_stock",
                    "resources.extraction_rate",
                ],
                weight_fn=self._nr_weight_fn,
                equation_source="World3-03 stock/flow decomposition",
                notes="Separately represents remaining stock and extraction flow",
            )
        )
        return mappings

    @staticmethod
    def _nr_weight_fn(
        state: dict[str, Any], t: float
    ) -> list[float]:
        nr = state.get("NR", 1.0)
        er = state.get("extraction_rate", 0.0)
        total = abs(nr) + abs(er)
        if total < 1e-15:
            return [1.0, 0.0]
        return [abs(nr) / total, abs(er) / total]

    def validate(self) -> list[str]:
        issues: list[str] = []
        for source, target in self.NAME_MAP.items():
            if target.count(".") != 1:
                issues.append(
                    f"Target '{target}' not in sector.variable format"
                )
        return issues
