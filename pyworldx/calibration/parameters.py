"""Parameter registry for calibration (Section 9.2).

Every free parameter entry includes: name, default, bounds, units,
sector owner, rationale, empirical anchor, IDENTIFIABILITY_RISK flag,
and scenario mutability flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IdentifiabilityRisk(Enum):
    """Risk classification for parameter identifiability."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ParameterEntry:
    """A single free parameter in the model.

    Attributes:
        name: canonical parameter name (e.g. "population.cbr_base")
        default: default/literature value
        bounds: (lower, upper) admissible range
        units: physical units
        sector_owner: which sector owns this parameter
        rationale: why this default was chosen
        empirical_anchor: data source for default, if any
        identifiability_risk: structural or empirical risk flag
        id_risk_rationale: reason for risk assignment
        scenario_mutable: whether scenarios may override this parameter
    """

    name: str
    default: float
    bounds: tuple[float, float]
    units: str
    sector_owner: str
    rationale: str = ""
    empirical_anchor: str | None = None
    identifiability_risk: IdentifiabilityRisk = IdentifiabilityRisk.NONE
    id_risk_rationale: str = ""
    scenario_mutable: bool = True

    def __post_init__(self) -> None:
        lo, hi = self.bounds
        if lo > hi:
            raise ValueError(
                f"Parameter '{self.name}': lower bound {lo} > upper bound {hi}"
            )
        if not (lo <= self.default <= hi):
            raise ValueError(
                f"Parameter '{self.name}': default {self.default} "
                f"outside bounds ({lo}, {hi})"
            )


class DuplicateParameterError(Exception):
    """Raised when duplicate parameter name is registered."""


class UnknownParameterError(KeyError):
    """Raised when looking up an unregistered parameter."""


@dataclass
class ParameterRegistry:
    """Central registry of all free model parameters.

    Structured so Bayesian calibration can reuse it without redesign
    (Section 9.7).
    """

    _entries: dict[str, ParameterEntry] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self._entries)

    def register(self, entry: ParameterEntry) -> None:
        """Register a parameter. Raises on duplicate name."""
        if entry.name in self._entries:
            raise DuplicateParameterError(
                f"Parameter '{entry.name}' already registered"
            )
        self._entries[entry.name] = entry

    def lookup(self, name: str) -> ParameterEntry:
        """Look up a parameter by name."""
        if name not in self._entries:
            raise UnknownParameterError(f"Unknown parameter: {name}")
        return self._entries[name]

    def get_defaults(self) -> dict[str, float]:
        """Return all parameters at their default values."""
        return {name: e.default for name, e in self._entries.items()}

    def get_bounds(self) -> dict[str, tuple[float, float]]:
        """Return all parameter bounds."""
        return {name: e.bounds for name, e in self._entries.items()}

    def get_sector_parameters(self, sector: str) -> list[ParameterEntry]:
        """Return all parameters owned by a sector."""
        return [e for e in self._entries.values() if e.sector_owner == sector]

    def get_risky_parameters(self) -> list[ParameterEntry]:
        """Return parameters flagged with identifiability risk."""
        return [
            e
            for e in self._entries.values()
            if e.identifiability_risk != IdentifiabilityRisk.NONE
        ]

    def get_scenario_mutable(self) -> list[ParameterEntry]:
        """Return parameters that scenarios may override."""
        return [e for e in self._entries.values() if e.scenario_mutable]

    def validate_overrides(
        self, overrides: dict[str, float]
    ) -> list[str]:
        """Validate parameter overrides against bounds. Returns warnings."""
        warnings: list[str] = []
        for name, value in overrides.items():
            if name not in self._entries:
                warnings.append(f"Unknown parameter: {name}")
                continue
            entry = self._entries[name]
            lo, hi = entry.bounds
            if not (lo <= value <= hi):
                warnings.append(
                    f"Parameter '{name}' value {value} outside bounds ({lo}, {hi})"
                )
        return warnings

    def apply_overrides(
        self, overrides: dict[str, float]
    ) -> dict[str, float]:
        """Return defaults with overrides applied (validated)."""
        params = self.get_defaults()
        for name, value in overrides.items():
            if name in self._entries:
                params[name] = value
        return params

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialize for provenance/manifest."""
        return {
            name: {
                "default": e.default,
                "bounds": list(e.bounds),
                "units": e.units,
                "sector_owner": e.sector_owner,
                "identifiability_risk": e.identifiability_risk.value,
                "scenario_mutable": e.scenario_mutable,
            }
            for name, e in self._entries.items()
        }

    def all_entries(self) -> list[ParameterEntry]:
        """Return all entries."""
        return list(self._entries.values())


def build_world3_parameter_registry() -> ParameterRegistry:
    """Build the canonical World3-03 parameter registry.

    Every free parameter from the 5 sectors is registered with bounds,
    units, rationale, and identifiability risk flags.
    """
    reg = ParameterRegistry()

    # ── Population sector ────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="population.cbr_base",
        default=0.04,
        bounds=(0.02, 0.06),
        units="1/year",
        sector_owner="population",
        rationale="World3-03 default crude birth rate",
        empirical_anchor="Meadows et al. 1972",
    ))
    reg.register(ParameterEntry(
        name="population.cdr_base",
        default=0.028,
        bounds=(0.01, 0.05),
        units="1/year",
        sector_owner="population",
        rationale="World3-03 default crude death rate",
        empirical_anchor="Meadows et al. 1972",
    ))
    reg.register(ParameterEntry(
        name="population.base_life_expectancy",
        default=32.0,
        bounds=(25.0, 45.0),
        units="years",
        sector_owner="population",
        rationale="1900 baseline life expectancy",
        empirical_anchor="Historical data",
    ))
    reg.register(ParameterEntry(
        name="population.food_le_multiplier",
        default=10.0,
        bounds=(5.0, 20.0),
        units="years",
        sector_owner="population",
        rationale="Life expectancy gain from adequate nutrition",
        identifiability_risk=IdentifiabilityRisk.MEDIUM,
        id_risk_rationale="Sensitive to food_per_capita normalization",
    ))

    # ── Capital sector ───────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="capital.initial_ic",
        default=2.1e11,
        bounds=(1e11, 5e11),
        units="capital_units",
        sector_owner="capital",
        rationale="World3-03 1900 industrial capital",
        empirical_anchor="Meadows et al. 1972",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="capital.icor",
        default=3.0,
        bounds=(1.5, 6.0),
        units="years",
        sector_owner="capital",
        rationale="Industrial capital-output ratio",
        identifiability_risk=IdentifiabilityRisk.HIGH,
        id_risk_rationale="Large recalibrations in literature (2.5-5.0)",
    ))
    reg.register(ParameterEntry(
        name="capital.ic_depreciation_rate",
        default=0.05,
        bounds=(0.02, 0.10),
        units="1/year",
        sector_owner="capital",
        rationale="1/average lifetime (20 years default)",
    ))

    # ── Agriculture sector ───────────────────────────────────────────
    reg.register(ParameterEntry(
        name="agriculture.initial_al",
        default=9e8,
        bounds=(5e8, 1.5e9),
        units="hectares",
        sector_owner="agriculture",
        rationale="World3-03 1900 arable land",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="agriculture.land_yield_base",
        default=600.0,
        bounds=(300.0, 1200.0),
        units="food_units/hectare",
        sector_owner="agriculture",
        rationale="Base yield per hectare without inputs",
        identifiability_risk=IdentifiabilityRisk.MEDIUM,
        id_risk_rationale="Covaries with io_to_agriculture_fraction",
    ))
    reg.register(ParameterEntry(
        name="agriculture.land_development_rate",
        default=0.005,
        bounds=(0.001, 0.02),
        units="1/year",
        sector_owner="agriculture",
        rationale="Fractional rate of arable land expansion",
    ))

    # ── Resources sector ─────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="resources.initial_nr",
        default=1.0e12,
        bounds=(5e11, 2e12),
        units="resource_units",
        sector_owner="resources",
        rationale="World3-03 initial NR stock",
        empirical_anchor="Meadows et al. 1972",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="resources.pcnr_use_base",
        default=1.0,
        bounds=(0.1, 10.0),
        units="resource_units/person",
        sector_owner="resources",
        rationale="Per-capita resource usage base multiplier",
        identifiability_risk=IdentifiabilityRisk.HIGH,
        id_risk_rationale="Flat-plateau in profile likelihood; "
        "covaries with PCRUM table shape",
    ))

    # ── Pollution sector ─────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="pollution.initial_ppol",
        default=2.5e7,
        bounds=(1e7, 1e8),
        units="pollution_units",
        sector_owner="pollution",
        rationale="1900 persistent pollution level",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="pollution.base_absorption_time",
        default=20.0,
        bounds=(5.0, 50.0),
        units="years",
        sector_owner="pollution",
        rationale="Base pollution absorption time constant",
        identifiability_risk=IdentifiabilityRisk.MEDIUM,
        id_risk_rationale="Slow-state parameter with weak obs leverage",
    ))
    reg.register(ParameterEntry(
        name="pollution.industrial_pollution_intensity",
        default=0.01,
        bounds=(0.001, 0.05),
        units="dimensionless",
        sector_owner="pollution",
        rationale="Fraction of IO generating persistent pollution",
    ))

    return reg
