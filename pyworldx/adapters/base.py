"""Base adapter protocol (Section 7.3).

Adapters are responsible for: name translation, unit conversion,
stock/flow interpretation, temporal alignment, proxy declaration,
provenance annotation, and state-dependent disaggregation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable


class AdapterError(Exception):
    """Base error for adapter failures."""


class MissingOntologyEntityError(AdapterError):
    """Required ontology entity is absent."""


class IncompatibleUnitsError(AdapterError):
    """Units are incompatible between source and target."""


class UndocumentedStaticCoefficientError(AdapterError):
    """A mapping requiring weight_fn uses undocumented static coefficients."""


class TemporalFrequencyMismatchError(AdapterError):
    """Temporal frequency mismatch exceeds tolerance."""


@dataclass(frozen=True)
class VariableMapping:
    """Maps a source variable to one or more ontology targets (Section 7.2)."""

    source_var: str
    target_vars: list[str]
    weight_fn: Callable[[dict[str, Any], float], list[float]]
    equation_source: str
    notes: str = ""
    is_static: bool = False

    def get_weights(
        self, state: dict[str, Any], t: float
    ) -> list[float]:
        """Compute mapping weights. Must sum to 1.0."""
        weights = self.weight_fn(state, t)
        total = sum(weights)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Weights for {self.source_var} sum to {total}, not 1.0"
            )
        return weights


@runtime_checkable
class BaseAdapter(Protocol):
    """Protocol for all adapters."""

    name: str
    version: str

    def translate_name(self, source_name: str) -> str: ...
    def convert_units(
        self, value: float, source_unit: str, target_unit: str
    ) -> float: ...
    def get_mappings(self) -> list[VariableMapping]: ...
    def validate(self) -> list[str]: ...
