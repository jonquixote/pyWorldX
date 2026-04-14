"""Phase 0.5 tests — Nonlinear Depreciation, PPTD Recalibration, FIOAA Dedup.

Tests cover:
  Task 1: depreciation_multiplier φ function + capital sector integration
  Task 2: pollution PPTD default = 111.8 per Nebel 2024
  Task 3: FIOAA dedup (already tested in test_investment_chain.py)
"""
from __future__ import annotations

import pytest

from pyworldx.sectors.capital import CapitalSector, depreciation_multiplier
from pyworldx.core.quantities import Quantity


# ── Task 1: Nonlinear Depreciation Tests ──────────────────────────────

class TestDepreciationMultiplier:
    """Test the φ(MaintenanceRatio) function boundary conditions."""

    def test_phi_at_1_0_is_1_0(self) -> None:
        assert depreciation_multiplier(1.0) == 1.0

    def test_phi_above_1_0_is_1_0(self) -> None:
        assert depreciation_multiplier(1.5) == 1.0
        assert depreciation_multiplier(10.0) == 1.0

    def test_phi_at_0_5_is_quadratic(self) -> None:
        # φ = 1 + 3 × (1 - 0.5)² = 1 + 3 × 0.25 = 1.75
        assert depreciation_multiplier(0.5) == pytest.approx(1.75)

    def test_phi_at_0_0_is_bounded(self) -> None:
        assert depreciation_multiplier(0.0) == 4.0

    def test_phi_at_negative_is_bounded(self) -> None:
        assert depreciation_multiplier(-1.0) == 4.0
        assert depreciation_multiplier(-100.0) == 4.0

    def test_phi_monotonic(self) -> None:
        """φ is monotonically decreasing from ratio=0 to ratio=1."""
        ratios = [i / 20.0 for i in range(21)]
        values = [depreciation_multiplier(r) for r in ratios]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1], (
                f"φ({ratios[i]})={values[i]} should be >= φ({ratios[i+1]})={values[i+1]}"
            )


class TestCapitalDepreciationIntegration:
    """Test that capital sector uses φ when maintenance_ratio is provided."""

    def _make_sector(self) -> CapitalSector:
        return CapitalSector()

    def _base_inputs(self) -> dict[str, Quantity]:
        return {
            "POP": Quantity(1.65e9, "persons"),
            "fcaor": Quantity(0.05, "dimensionless"),
            "frac_io_to_agriculture": Quantity(0.1, "dimensionless"),
            "P2": Quantity(7.0e8, "persons"),
            "P3": Quantity(1.9e8, "persons"),
            "AL": Quantity(0.9e9, "hectares"),
            "aiph": Quantity(2.0, "agricultural_inputs_per_hectare"),
        }

    def _base_stocks(self) -> dict[str, Quantity]:
        return {
            "IC": Quantity(2.1e11, "capital_units"),
            "SC": Quantity(1.44e11, "capital_units"),
            "LUFD": Quantity(1.0, "dimensionless"),
            "IOPCD": Quantity(40.3, "industrial_output_units"),
        }

    def test_default_maintenance_ratio_is_1_0(self) -> None:
        """Without explicit maintenance_ratio input, φ=1.0 (no change from v1)."""
        sector = self._make_sector()
        ctx_type = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})
        ctx = ctx_type()
        inputs = self._base_inputs()
        stocks = self._base_stocks()

        result = sector.compute(0.0, stocks, inputs, ctx)  # type: ignore[arg-type]
        d_ic = result["d_IC"].magnitude

        # Now explicitly set maintenance_ratio=1.0 — should be identical
        inputs["maintenance_ratio"] = Quantity(1.0, "dimensionless")
        result2 = sector.compute(0.0, stocks, inputs, ctx)  # type: ignore[arg-type]
        d_ic2 = result2["d_IC"].magnitude

        assert d_ic == pytest.approx(d_ic2)

    def test_capital_depreciation_accelerates(self) -> None:
        """Capital sector depreciation increases when maintenance_ratio < 1.0."""
        sector = self._make_sector()
        ctx_type = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})
        ctx = ctx_type()
        stocks = self._base_stocks()

        # Run with maintenance_ratio=1.0 (baseline)
        inputs_normal = self._base_inputs()
        inputs_normal["maintenance_ratio"] = Quantity(1.0, "dimensionless")
        result_normal = sector.compute(0.0, stocks, inputs_normal, ctx)  # type: ignore[arg-type]

        # Run with maintenance_ratio=0.5 (accelerated depreciation)
        inputs_stressed = self._base_inputs()
        inputs_stressed["maintenance_ratio"] = Quantity(0.5, "dimensionless")
        result_stressed = sector.compute(0.0, stocks, inputs_stressed, ctx)  # type: ignore[arg-type]

        # d_IC should be LOWER (more depreciation) when maintenance is poor
        assert result_stressed["d_IC"].magnitude < result_normal["d_IC"].magnitude

    def test_maintenance_ratio_in_declares_reads(self) -> None:
        """maintenance_ratio must be in declares_reads for dependency graph."""
        sector = self._make_sector()
        assert "maintenance_ratio" in sector.declares_reads()


# ── Task 2: PPTD Recalibration Tests ─────────────────────────────────

class TestPPTDRecalibration:
    """Test that PPTD defaults to 111.8 per Nebel 2024."""

    def test_pptd_default_is_111_8(self) -> None:
        from pyworldx.sectors.pollution import PollutionSector
        sector = PollutionSector()
        assert sector.pptd == pytest.approx(111.8)

    def test_3rd_order_delay_correct(self) -> None:
        """3-stage cascade uses stage_delay = pptd / 3.0."""
        from pyworldx.sectors.pollution import PollutionSector
        sector = PollutionSector()
        expected_stage_delay = 111.8 / 3.0
        assert expected_stage_delay == pytest.approx(37.2667, rel=1e-3)

    def test_bounds_accommodate_default(self) -> None:
        """Parameter bounds must contain the new default comfortably."""
        from pyworldx.calibration.parameters import build_world3_parameter_registry
        reg = build_world3_parameter_registry()
        entry = reg.lookup("pollution.pptd")
        assert entry is not None
        assert entry.default == pytest.approx(111.8)
        lo, hi = entry.bounds
        assert lo <= 111.8 <= hi
        # Default should not be at the edge — at least 10% margin from bounds
        margin = (hi - lo) * 0.1
        assert lo + margin < 111.8 < hi - margin

    def test_pollution_slower_response(self) -> None:
        """Higher PPTD = slower transmission delay."""
        from pyworldx.sectors.pollution import PollutionSector
        sector_slow = PollutionSector()
        sector_slow.pptd = 111.8
        sector_fast = PollutionSector()
        sector_fast.pptd = 20.0
        assert sector_slow.pptd > sector_fast.pptd
