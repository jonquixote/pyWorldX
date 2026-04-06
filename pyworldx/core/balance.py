"""Conservation balance auditor (Section 6.5).

Checks mass/energy conservation groups at master-step boundaries.
Sectors declare which conservation_groups they participate in via
their metadata().  The auditor compares expected vs observed stock
deltas and emits BalanceAuditResult with PASS/WARN/FAIL status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyworldx.core.quantities import Quantity


class BalanceStatus(Enum):
    """Status of a balance audit check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class BalanceAuditResult:
    """Result of a conservation balance check at a master-step boundary.

    Attributes:
        group: name of the conservation group (e.g. "nonrenewable_resource_mass")
        expected_delta: expected net change from declared flows
        observed_delta: actual change in stock (stock_t1 - stock_t0)
        residual: observed_delta - expected_delta
        status: PASS/WARN/FAIL based on tolerances
        t: time at which the audit was performed
        sector_name: sector owning the checked stock
    """

    group: str
    expected_delta: float
    observed_delta: float
    residual: float
    status: BalanceStatus
    t: float
    sector_name: str

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization."""
        return {
            "group": self.group,
            "expected_delta": self.expected_delta,
            "observed_delta": self.observed_delta,
            "residual": self.residual,
            "status": self.status.value,
            "t": self.t,
            "sector_name": self.sector_name,
        }


@dataclass
class BalanceAuditor:
    """Audits conservation balance across master-step boundaries.

    Configured with per-group tolerances.  At each master step, call
    audit() with before/after stock values and declared flow totals.

    Attributes:
        warn_tol: absolute residual above which status is WARN (default 1e-6)
        fail_tol: absolute residual above which status is FAIL (default 1e-3)
        results: accumulated audit results across the run
    """

    warn_tol: float = 1e-6
    fail_tol: float = 1e-3
    results: list[BalanceAuditResult] = field(default_factory=list)

    def audit_step(
        self,
        group: str,
        stock_before: float,
        stock_after: float,
        expected_net_flow: float,
        t: float,
        sector_name: str,
    ) -> BalanceAuditResult:
        """Audit one conservation group at one master-step boundary.

        Args:
            group: conservation group name
            stock_before: stock value at start of step
            stock_after: stock value at end of step
            expected_net_flow: expected net change (sum of flows * dt)
            t: current time
            sector_name: sector owning this stock

        Returns:
            BalanceAuditResult
        """
        observed_delta = stock_after - stock_before
        expected_delta = expected_net_flow
        residual = observed_delta - expected_delta

        abs_residual = abs(residual)
        if abs_residual > self.fail_tol:
            status = BalanceStatus.FAIL
        elif abs_residual > self.warn_tol:
            status = BalanceStatus.WARN
        else:
            status = BalanceStatus.PASS

        result = BalanceAuditResult(
            group=group,
            expected_delta=expected_delta,
            observed_delta=observed_delta,
            residual=residual,
            status=status,
            t=t,
            sector_name=sector_name,
        )
        self.results.append(result)
        return result

    def audit_sectors(
        self,
        sectors: list[Any],
        stocks_before: dict[str, Quantity],
        stocks_after: dict[str, Quantity],
        flow_outputs: dict[str, dict[str, Quantity]],
        t: float,
        dt: float,
    ) -> list[BalanceAuditResult]:
        """Audit all conservation groups declared by sectors.

        Args:
            sectors: list of sector objects
            stocks_before: all stock values before the step
            stocks_after: all stock values after the step
            flow_outputs: dict mapping sector.name -> compute() output
            t: time after the step
            dt: master timestep

        Returns:
            List of BalanceAuditResults for this step
        """
        step_results: list[BalanceAuditResult] = []

        for s in sectors:
            meta = s.metadata()
            groups = meta.get("conservation_groups", [])
            if not isinstance(groups, list):
                continue

            for group in groups:
                # Find stocks owned by this sector
                for stock_name in s.declares_writes():
                    if stock_name.startswith("d_"):
                        continue
                    if stock_name not in stocks_before:
                        continue
                    if stock_name not in stocks_after:
                        continue

                    before_val = stocks_before[stock_name].magnitude
                    after_val = stocks_after[stock_name].magnitude

                    # Find the derivative for this stock
                    deriv_key = f"d_{stock_name}"
                    sector_flows = flow_outputs.get(s.name, {})
                    if deriv_key in sector_flows:
                        expected_net = sector_flows[deriv_key].magnitude * dt
                    else:
                        expected_net = 0.0

                    result = self.audit_step(
                        group=str(group),
                        stock_before=before_val,
                        stock_after=after_val,
                        expected_net_flow=expected_net,
                        t=t,
                        sector_name=s.name,
                    )
                    step_results.append(result)

        return step_results

    def summary(self) -> dict[str, int]:
        """Return count of PASS/WARN/FAIL across all audits."""
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for r in self.results:
            counts[r.status.value] += 1
        return counts

    def has_failures(self) -> bool:
        """True if any audit resulted in FAIL."""
        return any(r.status == BalanceStatus.FAIL for r in self.results)
