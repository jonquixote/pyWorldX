"""Built-in scenarios (Section 11.3).

Re-exports from scenario.py for convenience per spec file layout.
"""

from pyworldx.scenarios.scenario import (
    BUILTIN_SCENARIOS,
    agricultural_efficiency_push,
    baseline_world3,
    capital_reallocation_to_maintenance,
    high_resource_discovery,
    pollution_control_push,
    wiliam_high_military_drag,
)

__all__ = [
    "BUILTIN_SCENARIOS",
    "baseline_world3",
    "high_resource_discovery",
    "pollution_control_push",
    "agricultural_efficiency_push",
    "capital_reallocation_to_maintenance",
    "wiliam_high_military_drag",
]
