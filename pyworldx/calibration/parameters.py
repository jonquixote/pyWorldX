"""Parameter registry for calibration (Section 9.2).

Every free parameter entry includes: name, default, bounds, units,
sector owner, rationale, empirical anchor, IDENTIFIABILITY_RISK flag,
and scenario mutability flag.

All defaults calibrated to wrld3-03.mdl (Vensim, September 29 2005).
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

    All defaults from wrld3-03.mdl unless noted as pyWorldX approximation.
    """
    reg = ParameterRegistry()

    # ── Population sector ────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="population.cbr_base",
        default=0.04,
        bounds=(0.02, 0.06),
        units="1/year",
        sector_owner="population",
        rationale="pyWorldX approximation: peak CBR at low IOPC",
    ))
    reg.register(ParameterEntry(
        name="population.cdr_base",
        default=0.028,
        bounds=(0.01, 0.05),
        units="1/year",
        sector_owner="population",
        rationale="pyWorldX approximation: base CDR",
    ))
    reg.register(ParameterEntry(
        name="population.initial_population",
        default=1.65e9,
        bounds=(1.5e9, 1.8e9),
        units="persons",
        sector_owner="population",
        rationale="W3-03 total initial population (sum of 4 cohorts)",
        empirical_anchor="wrld3-03.mdl: P1+P2+P3+P4",
        scenario_mutable=False,
    ))

    # ── Capital sector ───────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="capital.initial_ic",
        default=2.1e11,
        bounds=(1e11, 5e11),
        units="capital_units",
        sector_owner="capital",
        rationale="W3-03 1900 industrial capital",
        empirical_anchor="wrld3-03.mdl",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="capital.icor",
        default=3.0,
        bounds=(1.5, 6.0),
        units="years",
        sector_owner="capital",
        rationale="W3-03 ICOR1 = 3.0",
        empirical_anchor="wrld3-03.mdl",
        identifiability_risk=IdentifiabilityRisk.HIGH,
        id_risk_rationale="Large recalibrations in literature (2.5-5.0)",
    ))
    reg.register(ParameterEntry(
        name="capital.alic",
        default=14.0,
        bounds=(10.0, 20.0),
        units="years",
        sector_owner="capital",
        rationale="W3-03 ALIC1 = 14 years (depreciation = 1/14 per year)",
        empirical_anchor="wrld3-03.mdl",
    ))
    reg.register(ParameterEntry(
        name="capital.alsc",
        default=20.0,
        bounds=(15.0, 30.0),
        units="years",
        sector_owner="capital",
        rationale="W3-03 ALSC1 = 20 years",
        empirical_anchor="wrld3-03.mdl",
    ))

    # ── Agriculture sector ───────────────────────────────────────────
    reg.register(ParameterEntry(
        name="agriculture.initial_al",
        default=9e8,
        bounds=(5e8, 1.5e9),
        units="hectares",
        sector_owner="agriculture",
        rationale="W3-03 1900 arable land",
        empirical_anchor="wrld3-03.mdl",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="agriculture.initial_land_fertility",
        default=600.0,
        bounds=(300.0, 1200.0),
        units="veg_equiv_kg/ha/yr",
        sector_owner="agriculture",
        rationale="W3-03 ILF = 600 (inherent land fertility)",
        empirical_anchor="wrld3-03.mdl",
    ))
    reg.register(ParameterEntry(
        name="agriculture.land_development_rate",
        default=0.005,
        bounds=(0.001, 0.02),
        units="1/year",
        sector_owner="agriculture",
        rationale="Fractional rate of arable land expansion",
    ))
    reg.register(ParameterEntry(
        name="agriculture.sfpc",
        default=230.0,
        bounds=(180.0, 300.0),
        units="veg_equiv_kg/person/yr",
        sector_owner="agriculture",
        rationale="W3-03 SFPC = 230 (subsistence food per capita)",
        empirical_anchor="wrld3-03.mdl",
    ))

    # ── Resources sector ─────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="resources.initial_nr",
        default=1.0e12,
        bounds=(5e11, 2e12),
        units="resource_units",
        sector_owner="resources",
        rationale="W3-03 NRI = 1e12",
        empirical_anchor="wrld3-03.mdl",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="resources.policy_year",
        default=4000.0,
        bounds=(1975.0, 4000.0),
        units="year",
        sector_owner="resources",
        rationale="W3-03 POLICY_YEAR (4000 = base run, inactive)",
        scenario_mutable=True,
    ))

    # ── Pollution sector ─────────────────────────────────────────────
    reg.register(ParameterEntry(
        name="pollution.initial_ppol",
        default=2.5e7,
        bounds=(1e7, 1e8),
        units="pollution_units",
        sector_owner="pollution",
        rationale="W3-03 1900 persistent pollution level",
        empirical_anchor="wrld3-03.mdl",
        scenario_mutable=False,
    ))
    reg.register(ParameterEntry(
        name="pollution.ahl70",
        default=1.5,
        bounds=(0.5, 5.0),
        units="years",
        sector_owner="pollution",
        rationale="W3-03 AHL70 = 1.5 years (absorption half-life in 1970)",
        empirical_anchor="wrld3-03.mdl",
    ))
    reg.register(ParameterEntry(
        name="pollution.pptd",
        default=111.8,
        bounds=(50.0, 200.0),
        units="years",
        sector_owner="pollution",
        rationale="Nebel et al. 2024 recalibration (DOI: 10.1111/jiec.13442); W3-03 original was 20 years",
        empirical_anchor="Nebel et al. 2024 (DOI: 10.1111/jiec.13442); wrld3-03.mdl",
    ))

    return reg
