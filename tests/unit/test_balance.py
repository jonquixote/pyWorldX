"""Tests for conservation balance auditor."""

from __future__ import annotations

from pyworldx.core.balance import BalanceAuditor, BalanceStatus
from pyworldx.core.quantities import DIMENSIONLESS, Quantity
from pyworldx.sectors.base import RunContext


# ── Mock sector for balance testing ──────────────────────────────────────

class ConservedSector:
    """Sector with a declared conservation group."""
    name = "conserved"
    version = "1.0"
    timestep_hint = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"mass": Quantity(100.0, DIMENSIONLESS)}

    def compute(self, t: float, stocks: dict[str, Quantity],
                inputs: dict[str, Quantity], ctx: RunContext) -> dict[str, Quantity]:
        return {"d_mass": Quantity(-2.0, DIMENSIONLESS)}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {"conservation_groups": ["total_mass"]}

    def declares_reads(self) -> list[str]:
        return []

    def declares_writes(self) -> list[str]:
        return ["mass"]


# ── Tests ────────────────────────────────────────────────────────────────

class TestBalanceAuditor:
    def test_pass_on_exact_conservation(self) -> None:
        """Exact match between expected and observed should PASS."""
        auditor = BalanceAuditor()
        result = auditor.audit_step(
            group="mass",
            stock_before=100.0,
            stock_after=98.0,
            expected_net_flow=-2.0,
            t=1.0,
            sector_name="test",
        )
        assert result.status == BalanceStatus.PASS
        assert result.residual == 0.0

    def test_warn_on_small_violation(self) -> None:
        """Small residual should produce WARN."""
        auditor = BalanceAuditor(warn_tol=1e-6, fail_tol=1e-3)
        result = auditor.audit_step(
            group="mass",
            stock_before=100.0,
            stock_after=98.0001,  # off by 1e-4
            expected_net_flow=-2.0,
            t=1.0,
            sector_name="test",
        )
        assert result.status == BalanceStatus.WARN

    def test_fail_on_large_violation(self) -> None:
        """Large residual should produce FAIL."""
        auditor = BalanceAuditor(warn_tol=1e-6, fail_tol=1e-3)
        result = auditor.audit_step(
            group="mass",
            stock_before=100.0,
            stock_after=95.0,  # off by 3.0
            expected_net_flow=-2.0,
            t=1.0,
            sector_name="test",
        )
        assert result.status == BalanceStatus.FAIL

    def test_summary_counts(self) -> None:
        auditor = BalanceAuditor(warn_tol=1e-6, fail_tol=1e-2)
        auditor.audit_step("g", 100, 98, -2.0, 1.0, "s")  # PASS: residual=0
        auditor.audit_step("g", 100, 98.001, -2.0, 2.0, "s")  # WARN: residual=0.001
        auditor.audit_step("g", 100, 95, -2.0, 3.0, "s")  # FAIL: residual=3.0
        summary = auditor.summary()
        assert summary["PASS"] == 1
        assert summary["WARN"] == 1
        assert summary["FAIL"] == 1

    def test_has_failures(self) -> None:
        auditor = BalanceAuditor()
        auditor.audit_step("g", 100, 98, -2.0, 1.0, "s")
        assert not auditor.has_failures()
        auditor.audit_step("g", 100, 50, -2.0, 2.0, "s")
        assert auditor.has_failures()

    def test_to_dict(self) -> None:
        auditor = BalanceAuditor()
        result = auditor.audit_step("mass", 100, 98, -2.0, 1.0, "sector_a")
        d = result.to_dict()
        assert d["group"] == "mass"
        assert d["status"] == "PASS"
        assert d["sector_name"] == "sector_a"

    def test_audit_sectors_integration(self) -> None:
        """audit_sectors should check all declared conservation groups."""
        auditor = BalanceAuditor()
        sector = ConservedSector()

        stocks_before = {"mass": Quantity(100.0, DIMENSIONLESS)}
        stocks_after = {"mass": Quantity(98.0, DIMENSIONLESS)}
        flow_outputs = {
            "conserved": {"d_mass": Quantity(-2.0, DIMENSIONLESS)},
        }

        results = auditor.audit_sectors(
            sectors=[sector],
            stocks_before=stocks_before,
            stocks_after=stocks_after,
            flow_outputs=flow_outputs,
            t=1.0,
            dt=1.0,
        )

        assert len(results) == 1
        assert results[0].status == BalanceStatus.PASS
        assert results[0].group == "total_mass"
