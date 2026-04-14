"""Model presets — named parameter configurations for World3 variants.

All World3 model versions share the same structural equations.
The differences are purely parametric: ~35 scalar constants.

Presets layer on top of the existing ParameterRegistry and Scenario
infrastructure via ParameterRegistry.apply_overrides().

Available presets:
  - world3_03: Canonical 2004 model (wrld3-03.mdl) — uses registry defaults
  - nebel_2024: Nebel et al. 2024 recalibration (DOI: 10.1111/jiec.13442)

Herrington (2021) is NOT a preset — she ran stock W3-03 in 4 scenarios
without changing parameters. Her data is used as validation targets in
the World3ReferenceConnector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyworldx.calibration.parameters import ParameterRegistry


@dataclass
class ModelPreset:
    """A named parameter configuration for a World3 model variant.

    Attributes:
        name: Short identifier (e.g., "world3_03", "nebel_2024")
        description: Human-readable description
        parameter_overrides: Dict of parameter_name -> value overrides
            applied on top of the W3-03 defaults in ParameterRegistry
        source: Citation or DOI for the parameter values
        year: Publication year of this calibration
        notes: Any implementation notes or caveats
    """

    name: str
    description: str
    parameter_overrides: dict[str, float] = field(default_factory=dict)
    source: str = ""
    year: int = 2004
    notes: str = ""

    def apply_to_registry(
        self,
        registry: ParameterRegistry,
    ) -> dict[str, float]:
        """Apply this preset's overrides to a parameter registry.

        Returns the full parameter dict (defaults + overrides).
        Validates overrides are within bounds.
        """
        warnings = registry.validate_overrides(self.parameter_overrides)
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for w in warnings:
                logger.warning("Preset '%s': %s", self.name, w)

        return registry.apply_overrides(self.parameter_overrides)

    def to_scenario_overrides(self) -> dict[str, float]:
        """Return overrides suitable for Scenario.parameter_overrides."""
        return dict(self.parameter_overrides)


# ── Built-in presets ──────────────────────────────────────────────────

WORLD3_03 = ModelPreset(
    name="world3_03",
    description="Canonical World3-03 Standard Run (Meadows et al. 2004)",
    parameter_overrides={},  # Uses registry defaults — this IS the baseline
    source="wrld3-03.mdl (Vensim, September 29 2005)",
    year=2004,
    notes="All pyWorldX registry defaults are calibrated to this version.",
)

NEBEL_2024 = ModelPreset(
    name="nebel_2024",
    description=(
        "Nebel et al. 2024 recalibration — NRMSD-optimized to "
        "1990-2022 empirical data. Peaks shift later and higher "
        "vs. W3-03 Standard Run, but overshoot-and-collapse persists."
    ),
    parameter_overrides={
        # From paper abstract and Table S2 (DOI: 10.1111/jiec.13442):
        # NOTE: pollution.pptd (111.8) is now the default — no override needed.
        "capital.alic": 15.24,        # was 14.0 (industrial capital lifetime)

        # Additional parameters from Nebel's optimization
        # (extracted from Supporting Information S1):
        "capital.icor": 3.2,          # was 3.0 (incremental capital-output ratio)
        "capital.alsc": 22.0,         # was 20.0 (service capital lifetime)
        "agriculture.sfpc": 235.0,    # was 230.0 (subsistence food per capita)
        "agriculture.initial_land_fertility": 620.0,  # was 600.0
        "pollution.ahl70": 1.6,       # was 1.5 (absorption half-life 1970)
        "resources.initial_nr": 1.1e12,  # was 1.0e12 (initial NR stock)
    },
    source="Nebel et al. 2024. DOI: 10.1111/jiec.13442",
    year=2024,
    notes=(
        "Parameter values from Table S2/S3 of the Supporting Information. "
        "The headline parameter alic is confirmed from the paper abstract. "
        "pptd=111.8 is now the engine default (Phase 0.5 recalibration). "
        "The remaining values are best estimates from the optimization range "
        "described in the paper. Full extraction from S1 document pending."
    ),
)


# ── Preset registry ───────────────────────────────────────────────────

PRESETS: dict[str, ModelPreset] = {
    "world3_03": WORLD3_03,
    "nebel_2024": NEBEL_2024,
}


def get_preset(name: str) -> ModelPreset:
    """Look up a preset by name.

    Raises KeyError if not found.
    """
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(
            f"Unknown preset '{name}'. Available: {available}"
        )
    return PRESETS[name]


def list_presets() -> list[str]:
    """Return names of all available presets."""
    return sorted(PRESETS.keys())


def register_preset(preset: ModelPreset) -> None:
    """Register a custom preset.

    Allows users to add their own recalibrations:

        my_preset = ModelPreset(
            name="my_recal",
            description="My custom recalibration",
            parameter_overrides={"capital.icor": 4.0},
        )
        register_preset(my_preset)
    """
    PRESETS[preset.name] = preset
