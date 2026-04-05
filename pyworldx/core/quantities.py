"""Unit-safe Quantity type with runtime dimension checking.

A Quantity carries a floating-point magnitude and a unit family string.
Arithmetic operators enforce dimensional compatibility at runtime.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Union


class UnitMismatchError(Exception):
    """Raised when an operation combines incompatible unit families."""


# ---------------------------------------------------------------------------
# Unit families — simple strings for now.  The interface is what matters;
# the representation can be swapped to a richer system (e.g. pint) later.
# ---------------------------------------------------------------------------

DIMENSIONLESS = "dimensionless"
PEOPLE = "people"
CAPITAL_UNITS = "capital_units"
RESOURCE_UNITS = "resource_units"
POLLUTION_UNITS = "pollution_units"
YEARS = "years"
PER_YEAR = "per_year"
FOOD_UNITS = "food_units"
INDUSTRIAL_OUTPUT_UNITS = "industrial_output_units"


def _result_unit_mul(a: str, b: str) -> str:
    """Derive the unit family of a product.

    Rules (deliberately simple for Sprint 1):
      - dimensionless * X  →  X
      - X * dimensionless  →  X
      - per_year * years   →  dimensionless
      - years * per_year   →  dimensionless
      - Otherwise the product unit is ``f"{a}*{b}"`` — a compound that can
        participate in further arithmetic but will fail additive checks
        against simple families.
    """
    if a == DIMENSIONLESS:
        return b
    if b == DIMENSIONLESS:
        return a
    if (a == PER_YEAR and b == YEARS) or (a == YEARS and b == PER_YEAR):
        return DIMENSIONLESS
    return f"{a}*{b}"


def _result_unit_div(a: str, b: str) -> str:
    """Derive the unit family of a quotient.

    Rules:
      - X / dimensionless  →  X
      - X / X              →  dimensionless
      - years / years      →  dimensionless  (covered above)
      - Otherwise ``f"{a}/{b}"``.
    """
    if b == DIMENSIONLESS:
        return a
    if a == b:
        return DIMENSIONLESS
    return f"{a}/{b}"


@dataclass(frozen=True, slots=True)
class Quantity:
    """A magnitude with an associated unit family.

    Immutable value object.  Two quantities with the same unit family can be
    added and subtracted; any two quantities can be multiplied or divided
    (producing a derived unit family).
    """

    magnitude: float
    unit: str

    # -- additive operations (require same unit family) --------------------

    def __add__(self, other: object) -> Quantity:
        if isinstance(other, Quantity):
            if self.unit != other.unit:
                raise UnitMismatchError(
                    f"Cannot add {self.unit!r} and {other.unit!r}"
                )
            return Quantity(self.magnitude + other.magnitude, self.unit)
        return NotImplemented

    def __sub__(self, other: object) -> Quantity:
        if isinstance(other, Quantity):
            if self.unit != other.unit:
                raise UnitMismatchError(
                    f"Cannot subtract {other.unit!r} from {self.unit!r}"
                )
            return Quantity(self.magnitude - other.magnitude, self.unit)
        return NotImplemented

    def __neg__(self) -> Quantity:
        return Quantity(-self.magnitude, self.unit)

    # -- multiplicative operations -----------------------------------------

    def __mul__(self, other: object) -> Quantity:
        if isinstance(other, Quantity):
            return Quantity(
                self.magnitude * other.magnitude,
                _result_unit_mul(self.unit, self.unit if False else other.unit),
            )
        if isinstance(other, (int, float)):
            return Quantity(self.magnitude * other, self.unit)
        return NotImplemented

    def __rmul__(self, other: object) -> Quantity:
        if isinstance(other, (int, float)):
            return Quantity(other * self.magnitude, self.unit)
        return NotImplemented

    def __truediv__(self, other: object) -> Quantity:
        if isinstance(other, Quantity):
            return Quantity(
                self.magnitude / other.magnitude,
                _result_unit_div(self.unit, other.unit),
            )
        if isinstance(other, (int, float)):
            return Quantity(self.magnitude / other, self.unit)
        return NotImplemented

    def __rtruediv__(self, other: object) -> Quantity:
        if isinstance(other, (int, float)):
            return Quantity(other / self.magnitude, _result_unit_div(DIMENSIONLESS, self.unit))
        return NotImplemented

    def __pow__(self, exponent: Union[int, float]) -> Quantity:
        if isinstance(exponent, (int, float)):
            # Unit of X^n is just a string annotation for now
            if self.unit == DIMENSIONLESS:
                new_unit = DIMENSIONLESS
            else:
                new_unit = f"{self.unit}^{exponent}"
            return Quantity(self.magnitude ** exponent, new_unit)
        return NotImplemented

    # -- comparison (same-unit only) ---------------------------------------

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Quantity):
            if self.unit != other.unit:
                raise UnitMismatchError(
                    f"Cannot compare {self.unit!r} and {other.unit!r}"
                )
            return self.magnitude < other.magnitude
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, Quantity):
            if self.unit != other.unit:
                raise UnitMismatchError(
                    f"Cannot compare {self.unit!r} and {other.unit!r}"
                )
            return self.magnitude <= other.magnitude
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Quantity):
            if self.unit != other.unit:
                raise UnitMismatchError(
                    f"Cannot compare {self.unit!r} and {other.unit!r}"
                )
            return self.magnitude > other.magnitude
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, Quantity):
            if self.unit != other.unit:
                raise UnitMismatchError(
                    f"Cannot compare {self.unit!r} and {other.unit!r}"
                )
            return self.magnitude >= other.magnitude
        return NotImplemented

    # -- utility -----------------------------------------------------------

    def __repr__(self) -> str:
        return f"Quantity({self.magnitude}, {self.unit!r})"

    def __float__(self) -> float:
        return self.magnitude

    def is_finite(self) -> bool:
        """True if magnitude is finite (not NaN, not inf)."""
        return math.isfinite(self.magnitude)

    def assert_unit(self, expected: str) -> Quantity:
        """Return self if unit matches, else raise UnitMismatchError."""
        if self.unit != expected:
            raise UnitMismatchError(
                f"Expected unit {expected!r}, got {self.unit!r}"
            )
        return self
