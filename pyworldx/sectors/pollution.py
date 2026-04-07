"""World3-03 Persistent Pollution sector.

  dPPOL/dt = pollution_generation - pollution_absorption
  pollution_generation = f(industrial_output, agricultural_inputs)
  pollution_absorption = PPOL / absorption_time
  pollution_index = PPOL / PPOL_1970
  pollution_efficiency = f(pollution_index)
"""

from __future__ import annotations

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup

# Pollution generation from industrial output (table PPGIO)
_PPGIO_X = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
_PPGIO_Y = (0.0, 0.1, 0.3, 0.5, 0.7, 0.8)

# Pollution absorption time multiplier (table AHLM)
_AHLM_X = (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
_AHLM_Y = (1.0, 1.2, 1.5, 2.0, 3.0, 5.0, 8.0)

# Pollution efficiency impact on production (table)
_PE_X = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
_PE_Y = (1.0, 0.99, 0.97, 0.95, 0.90, 0.85, 0.75, 0.65, 0.55, 0.40, 0.20)


class PollutionSector:
    """World3-03 Persistent Pollution sector.

    Stocks: PPOL (persistent pollution)
    Reads: industrial_output, food (agricultural IO proxy)
    Writes: PPOL, pollution_index, pollution_efficiency, pollution_generation
    """

    name = "pollution"
    version = "3.03"
    timestep_hint: float | None = None

    # Parameters
    initial_ppol: float = 2.5e7  # 1900 pollution level
    ppol_1970: float = 1.36e8  # reference pollution level (1970)
    base_absorption_time: float = 20.0  # years
    industrial_pollution_intensity: float = 0.01  # fraction of IO
    agricultural_pollution_intensity: float = 1e-4  # fraction of food

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"PPOL": Quantity(self.initial_ppol, "pollution_units")}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        ppol = stocks["PPOL"].magnitude

        io = inputs.get(
            "industrial_output", Quantity(0.0, "industrial_output_units")
        ).magnitude
        food = inputs.get(
            "food", Quantity(0.0, "food_units")
        ).magnitude

        # Pollution generation
        io_rel = io / 1e9  # normalize to billions
        ppgio = table_lookup(io_rel, _PPGIO_X, _PPGIO_Y)
        gen_industrial = io * self.industrial_pollution_intensity * ppgio
        gen_agricultural = food * self.agricultural_pollution_intensity
        pollution_generation = gen_industrial + gen_agricultural

        # Pollution index
        pollution_index = ppol / self.ppol_1970

        # Absorption time (increases with pollution level)
        ahlm = table_lookup(pollution_index, _AHLM_X, _AHLM_Y)
        absorption_time = self.base_absorption_time * ahlm
        pollution_absorption = ppol / max(absorption_time, 0.1)

        # Pollution efficiency (feedback to capital)
        pe = table_lookup(pollution_index * 10.0, _PE_X, _PE_Y)

        return {
            "d_PPOL": Quantity(
                pollution_generation - pollution_absorption, "pollution_units"
            ),
            "pollution_index": Quantity(pollution_index, "dimensionless"),
            "pollution_efficiency": Quantity(pe, "dimensionless"),
            "pollution_generation": Quantity(
                pollution_generation, "pollution_units"
            ),
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "food"]

    def declares_writes(self) -> list[str]:
        return [
            "PPOL",
            "pollution_index",
            "pollution_efficiency",
            "pollution_generation",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        """Pollution<->Capital loop via pollution_efficiency and industrial_output."""
        return [
            {
                "name": "capital_pollution_loop",
                "variables": [
                    "industrial_output",
                    "pollution_index",
                    "pollution_efficiency",
                ],
                "scope": "cross_sector",
                "solver": "fixed_point",
                "tol": 1e-10,
                "max_iter": 100,
            }
        ]

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": "REFERENCE_MATCHED",
            "equation_source": "MEADOWS_SPEC",
            "world7_alignment": "NONE",
            "approximations": ["simplified absorption table"],
            "free_parameters": [
                "initial_ppol",
                "ppol_1970",
                "base_absorption_time",
            ],
            "conservation_groups": [],
            "observables": [
                "PPOL",
                "pollution_index",
                "pollution_efficiency",
            ],
            "unit_notes": "pollution_units, dimensionless",
        }
