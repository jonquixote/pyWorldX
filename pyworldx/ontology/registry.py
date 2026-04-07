"""Ontology registry: canonical variable names, units, and sector ownership.

Section 7.2: The registry defines canonical entities, validates no
duplicate writes, and provides lookup/registration for all model variables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class VariableRole(Enum):
    """Role of a variable in the model."""

    STOCK = "stock"
    FLOW = "flow"
    AUXILIARY = "auxiliary"
    PARAMETER = "parameter"


class DuplicateWriteError(Exception):
    """Raised when two sectors declare writes to the same variable."""


class UnknownVariableError(Exception):
    """Raised when looking up a variable not in the registry."""


@dataclass
class VariableEntry:
    """A single canonical variable in the ontology.

    Attributes:
        name: canonical dot-namespaced name (e.g. 'population.total')
        unit_family: unit family string for runtime checking
        role: stock, flow, auxiliary, or parameter
        sector_owner: name of the sector that writes this variable
        description: human-readable description
        world3_name: corresponding World3-03 variable name (if any)
        aggregation: how this variable aggregates (sum, mean, none)
    """

    name: str
    unit_family: str
    role: VariableRole
    sector_owner: str
    description: str = ""
    world3_name: str | None = None
    aggregation: str = "none"


@dataclass
class OntologyRegistry:
    """Central registry for all canonical model variables.

    Validates no duplicate writes at registration time. Provides
    lookup by canonical name, by sector, and by World3 name.
    """

    _entries: dict[str, VariableEntry] = field(default_factory=dict)
    _by_sector: dict[str, list[str]] = field(default_factory=dict)
    _by_world3: dict[str, str] = field(default_factory=dict)
    _mappings: list[dict[str, Any]] = field(default_factory=list)

    def register(self, entry: VariableEntry) -> None:
        """Register a canonical variable.

        Raises DuplicateWriteError if the variable name is already registered
        by a different sector.
        """
        if entry.name in self._entries:
            existing = self._entries[entry.name]
            if existing.sector_owner != entry.sector_owner:
                raise DuplicateWriteError(
                    f"Variable '{entry.name}' already registered by sector "
                    f"'{existing.sector_owner}', cannot register from "
                    f"'{entry.sector_owner}'."
                )
        self._entries[entry.name] = entry

        if entry.sector_owner not in self._by_sector:
            self._by_sector[entry.sector_owner] = []
        if entry.name not in self._by_sector[entry.sector_owner]:
            self._by_sector[entry.sector_owner].append(entry.name)

        if entry.world3_name:
            self._by_world3[entry.world3_name] = entry.name

    def lookup(self, name: str) -> VariableEntry:
        """Look up a variable by canonical name.

        Raises UnknownVariableError if not found.
        """
        if name not in self._entries:
            raise UnknownVariableError(
                f"Variable '{name}' not found in ontology registry. "
                f"Available: {list(self._entries.keys())[:10]}..."
            )
        return self._entries[name]

    def lookup_by_world3(self, world3_name: str) -> VariableEntry | None:
        """Look up by World3-03 variable name. Returns None if not mapped."""
        canon = self._by_world3.get(world3_name)
        if canon is None:
            return None
        return self._entries.get(canon)

    def get_sector_variables(self, sector_name: str) -> list[VariableEntry]:
        """Return all variables owned by a sector."""
        names = self._by_sector.get(sector_name, [])
        return [self._entries[n] for n in names if n in self._entries]

    def validate_sector(self, sector: Any) -> list[str]:
        """Validate a sector's declares_writes against the registry.

        Returns list of warning strings. Empty list means all good.
        """
        warnings: list[str] = []
        for var in sector.declares_writes():
            if var.startswith("d_"):
                continue
            if var not in self._entries:
                warnings.append(
                    f"Sector '{sector.name}' writes '{var}' which is not "
                    f"registered in the ontology."
                )
            else:
                entry = self._entries[var]
                if entry.sector_owner != sector.name:
                    warnings.append(
                        f"Sector '{sector.name}' writes '{var}' but it is "
                        f"owned by '{entry.sector_owner}'."
                    )
        return warnings

    def register_mapping(
        self,
        source_var: str,
        target_vars: list[str],
        weight_fn: Callable[[dict[str, Any], float], list[float]],
        equation_source: str,
        notes: str,
    ) -> None:
        """Register a state-dependent mapping per Section 7.2."""
        self._mappings.append({
            "source": source_var,
            "targets": target_vars,
            "weight_fn": weight_fn,
            "equation_source": equation_source,
            "notes": notes,
        })

    def all_variables(self) -> list[VariableEntry]:
        """Return all registered variables."""
        return list(self._entries.values())

    @property
    def size(self) -> int:
        return len(self._entries)


def build_world3_registry() -> OntologyRegistry:
    """Build the canonical World3-03 ontology registry.

    Registers all standard World3 variables with their canonical names,
    unit families, roles, and World3 name mappings.
    """
    reg = OntologyRegistry()

    # ── Population sector ────────────────────────────────────────────
    for entry in [
        VariableEntry("population.total", "persons", VariableRole.STOCK,
                      "population", "Total world population",
                      world3_name="population"),
        VariableEntry("population.birth_rate", "persons_per_year",
                      VariableRole.FLOW, "population",
                      "Annual births", world3_name="births"),
        VariableEntry("population.death_rate", "persons_per_year",
                      VariableRole.FLOW, "population",
                      "Annual deaths", world3_name="deaths"),
        VariableEntry("population.life_expectancy", "years",
                      VariableRole.AUXILIARY, "population",
                      "Life expectancy at birth",
                      world3_name="life_expectancy"),
    ]:
        reg.register(entry)

    # ── Capital sector ───────────────────────────────────────────────
    for entry in [
        VariableEntry("capital.industrial", "capital_units",
                      VariableRole.STOCK, "capital",
                      "Industrial capital stock",
                      world3_name="industrial_capital"),
        VariableEntry("capital.service", "capital_units",
                      VariableRole.STOCK, "capital",
                      "Service capital stock",
                      world3_name="service_capital"),
        VariableEntry("capital.industrial_output", "industrial_output_units",
                      VariableRole.AUXILIARY, "capital",
                      "Industrial output per year",
                      world3_name="industrial_output"),
        VariableEntry("capital.service_output", "service_output_units",
                      VariableRole.AUXILIARY, "capital",
                      "Service output per year",
                      world3_name="service_output_per_capita"),
    ]:
        reg.register(entry)

    # ── Agriculture sector ───────────────────────────────────────────
    for entry in [
        VariableEntry("agriculture.arable_land", "hectares",
                      VariableRole.STOCK, "agriculture",
                      "Total arable land",
                      world3_name="arable_land"),
        VariableEntry("agriculture.food", "food_units",
                      VariableRole.AUXILIARY, "agriculture",
                      "Total food production",
                      world3_name="food"),
        VariableEntry("agriculture.food_per_capita", "food_units_per_person",
                      VariableRole.AUXILIARY, "agriculture",
                      "Food per capita",
                      world3_name="food_per_capita"),
    ]:
        reg.register(entry)

    # ── Resources sector ─────────────────────────────────────────────
    for entry in [
        VariableEntry("resources.nonrenewable", "resource_units",
                      VariableRole.STOCK, "resources",
                      "Nonrenewable resource stock",
                      world3_name="nonrenewable_resources"),
        VariableEntry("resources.extraction_rate", "resource_units_per_year",
                      VariableRole.FLOW, "resources",
                      "Resource extraction rate",
                      world3_name="nr_extraction_rate"),
        VariableEntry("resources.fraction_remaining", "dimensionless",
                      VariableRole.AUXILIARY, "resources",
                      "Fraction of initial resources remaining",
                      world3_name="nr_fraction_remaining"),
    ]:
        reg.register(entry)

    # ── Pollution sector ─────────────────────────────────────────────
    for entry in [
        VariableEntry("pollution.persistent", "pollution_units",
                      VariableRole.STOCK, "pollution",
                      "Persistent pollution index",
                      world3_name="persistent_pollution"),
        VariableEntry("pollution.index", "dimensionless",
                      VariableRole.AUXILIARY, "pollution",
                      "Pollution index (ratio to 1970 level)",
                      world3_name="pollution_index"),
    ]:
        reg.register(entry)

    return reg
