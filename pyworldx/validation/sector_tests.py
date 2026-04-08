"""Sector-level validation utilities (Section 13.2).

Each sector must be tested for:
- unit consistency
- sign and monotonicity of key responses
- nonnegative stock guards
- declared algebraic loop convergence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


@dataclass
class SectorTestResult:
    """Result of sector-level validation."""

    sector_name: str
    test_name: str
    passed: bool
    message: str = ""


@dataclass
class SectorValidationReport:
    """Collection of sector validation results."""

    results: list[SectorTestResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def n_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def n_total(self) -> int:
        return len(self.results)

    def failures(self) -> list[SectorTestResult]:
        return [r for r in self.results if not r.passed]


def check_unit_consistency(sector: Any, ctx: RunContext) -> SectorTestResult:
    """Verify that sector outputs have proper units."""
    stocks = sector.init_stocks(ctx)
    inputs: dict[str, Quantity] = {}

    # Provide default inputs for all reads
    for var in sector.declares_reads():
        inputs[var] = Quantity(1.0, "dimensionless")

    try:
        outputs = sector.compute(0.0, stocks, inputs, ctx)
        for name, val in outputs.items():
            if not isinstance(val, Quantity):
                return SectorTestResult(
                    sector_name=sector.name,
                    test_name="unit_consistency",
                    passed=False,
                    message=f"Output '{name}' is not a Quantity: {type(val)}",
                )
        return SectorTestResult(
            sector_name=sector.name,
            test_name="unit_consistency",
            passed=True,
        )
    except Exception as e:
        return SectorTestResult(
            sector_name=sector.name,
            test_name="unit_consistency",
            passed=False,
            message=str(e),
        )


def check_nonnegative_stocks(sector: Any, ctx: RunContext) -> SectorTestResult:
    """Verify that initial stocks are nonnegative."""
    stocks = sector.init_stocks(ctx)
    for name, val in stocks.items():
        if val.magnitude < 0:
            return SectorTestResult(
                sector_name=sector.name,
                test_name="nonneg_stocks",
                passed=False,
                message=f"Stock '{name}' is negative: {val.magnitude}",
            )
    return SectorTestResult(
        sector_name=sector.name,
        test_name="nonneg_stocks",
        passed=True,
    )


def check_metadata_completeness(sector: Any) -> SectorTestResult:
    """Verify required metadata fields are present."""
    required_fields = [
        "validation_status",
        "equation_source",
        "world7_alignment",
        "approximations",
        "free_parameters",
        "conservation_groups",
        "observables",
        "unit_notes",
    ]
    meta = sector.metadata()
    missing = [f for f in required_fields if f not in meta]
    if missing:
        return SectorTestResult(
            sector_name=sector.name,
            test_name="metadata_completeness",
            passed=False,
            message=f"Missing metadata fields: {missing}",
        )
    return SectorTestResult(
        sector_name=sector.name,
        test_name="metadata_completeness",
        passed=True,
    )


def validate_sector(sector: Any, ctx: RunContext | None = None) -> SectorValidationReport:
    """Run all validation checks on a sector."""
    if ctx is None:
        ctx = RunContext()
    report = SectorValidationReport()
    report.results.append(check_unit_consistency(sector, ctx))
    report.results.append(check_nonnegative_stocks(sector, ctx))
    report.results.append(check_metadata_completeness(sector))
    return report
