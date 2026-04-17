"""Phase 1 tests — v2 Core Architecture.

Tests cover all 6 Phase 1 tasks:
  Task 1: CentralRegistrar (11 tests)
  Task 2: FinanceSector (15 tests)
  Task 3: Energy Split (9 tests)
  Task 4: Pollution Split (8 tests)
  Task 5: Gini Distribution (9 tests)
  Task 6: v2 Scenarios (8 tests)
"""

from __future__ import annotations


import pytest

from pyworldx.core.quantities import Quantity


# ═══════════════════════════════════════════════════════════════════════
# Task 1: CentralRegistrar
# ═══════════════════════════════════════════════════════════════════════


class TestCentralRegistrar:
    """Test the pre-derivative resolution pass."""

    def test_import(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar()
        assert cr.energy_ceiling == 0.65

    def test_disabled_returns_empty(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(enabled=False)
        shared: dict[str, Quantity] = {}
        result = cr.resolve(shared)
        assert not result.ceiling_breached
        assert result.multipliers == {}

    def test_no_demands_no_breach(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar()
        shared = {"fossil_output": Quantity(1000.0, "energy_units")}
        result = cr.resolve(shared)
        assert not result.ceiling_breached

    def test_under_ceiling_all_multipliers_1(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(energy_ceiling=0.65)
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_fossil": Quantity(100.0, "energy_units"),
            "energy_demand_sustainable": Quantity(100.0, "energy_units"),
        }
        result = cr.resolve(shared)
        assert not result.ceiling_breached
        assert result.multipliers["fossil"] == 1.0
        assert result.multipliers["sustainable"] == 1.0

    def test_over_ceiling_scales_down(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(energy_ceiling=0.65)
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_fossil": Quantity(500.0, "energy_units"),
            "energy_demand_sustainable": Quantity(500.0, "energy_units"),
            "liquid_funds_fossil": Quantity(100.0, "dimensionless"),
            "liquid_funds_sustainable": Quantity(100.0, "dimensionless"),
            "security_value_fossil": Quantity(1.0, "dimensionless"),
            "security_value_sustainable": Quantity(1.0, "dimensionless"),
        }
        result = cr.resolve(shared)
        assert result.ceiling_breached
        for m in result.multipliers.values():
            assert 0.0 <= m <= 1.0

    def test_high_ability_to_pay_gets_more(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(energy_ceiling=0.65)
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_rich": Quantity(500.0, "energy_units"),
            "energy_demand_poor": Quantity(500.0, "energy_units"),
            "liquid_funds_rich": Quantity(1000.0, "dimensionless"),
            "liquid_funds_poor": Quantity(10.0, "dimensionless"),
            "security_value_rich": Quantity(1.0, "dimensionless"),
            "security_value_poor": Quantity(1.0, "dimensionless"),
        }
        result = cr.resolve(shared)
        assert result.ceiling_breached
        assert result.multipliers["rich"] > result.multipliers["poor"]

    def test_supply_multipliers_written_to_shared(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(energy_ceiling=0.65)
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_test": Quantity(100.0, "energy_units"),
        }
        cr.resolve(shared)
        assert "supply_multiplier_test" in shared

    def test_total_demand_tracked(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar, _EJ_SCALE

        cr = CentralRegistrar()
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_a": Quantity(100.0, "energy_units"),
            "energy_demand_b": Quantity(200.0, "energy_units"),
        }
        result = cr.resolve(shared)
        # Demands are converted to EJ/yr by the registrar
        assert result.total_demand == pytest.approx(300.0 * _EJ_SCALE)

    def test_overshoot_tolerance(self) -> None:
        """Slight overshoot within 1/512 tolerance should NOT trigger scaling."""
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(energy_ceiling=0.65, overshoot_tolerance=1.0 / 512)
        supply = 1000.0 * 0.65  # 650
        # Demand just slightly over ceiling but within tolerance
        demand = supply * (1.0 + 0.5 / 512)
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_test": Quantity(demand, "energy_units"),
        }
        result = cr.resolve(shared)
        assert not result.ceiling_breached

    def test_engine_accepts_central_registrar(self) -> None:
        """Engine constructor should accept central_registrar parameter."""
        from pyworldx.core.central_registrar import CentralRegistrar
        from pyworldx.core.engine import Engine
        from pyworldx.sectors.rip_sectors import ResourceSector

        cr = CentralRegistrar(enabled=False)
        e = Engine(
            sectors=[ResourceSector()],
            central_registrar=cr,
            t_end=2.0,
        )
        assert e._central_registrar is cr

    def test_allocation_sums_to_supply(self) -> None:
        from pyworldx.core.central_registrar import CentralRegistrar

        cr = CentralRegistrar(energy_ceiling=0.5)
        shared = {
            "fossil_output": Quantity(1000.0, "energy_units"),
            "energy_demand_a": Quantity(400.0, "energy_units"),
            "energy_demand_b": Quantity(400.0, "energy_units"),
            "liquid_funds_a": Quantity(50.0, "dimensionless"),
            "liquid_funds_b": Quantity(50.0, "dimensionless"),
            "security_value_a": Quantity(1.0, "dimensionless"),
            "security_value_b": Quantity(1.0, "dimensionless"),
        }
        result = cr.resolve(shared)
        # Allocated supply ≤ total supply
        total_allocated = sum(result.multipliers[s] * d for s, d in [("a", 400.0), ("b", 400.0)])
        assert total_allocated <= 1000.0 * 0.5 + 1.0


# ═══════════════════════════════════════════════════════════════════════
# Task 2: FinanceSector
# ═══════════════════════════════════════════════════════════════════════


class TestGovernanceMultiplier:
    def test_zero_ratio_full_availability(self) -> None:
        from pyworldx.sectors.finance import governance_multiplier

        assert governance_multiplier(0.0) == 1.0

    def test_at_ceiling_zero_availability(self) -> None:
        from pyworldx.sectors.finance import governance_multiplier

        assert governance_multiplier(1.5) == 0.0

    def test_above_ceiling_zero_availability(self) -> None:
        from pyworldx.sectors.finance import governance_multiplier

        assert governance_multiplier(3.0) == 0.0

    def test_gradual_decline(self) -> None:
        from pyworldx.sectors.finance import governance_multiplier

        g_low = governance_multiplier(0.3)
        g_mid = governance_multiplier(0.75)
        g_high = governance_multiplier(1.2)
        assert g_low > g_mid > g_high > 0.0

    def test_negative_ratio(self) -> None:
        from pyworldx.sectors.finance import governance_multiplier

        assert governance_multiplier(-1.0) == 1.0


class TestFinanceSector:
    def _make_sector(self):
        from pyworldx.sectors.finance import FinanceSector

        return FinanceSector()

    def _base_stocks(self):
        return {
            "L": Quantity(1.0e11, "capital_units"),
            "D_g": Quantity(0.0, "capital_units"),
            "D_s": Quantity(0.0, "capital_units"),
            "D_p": Quantity(0.0, "capital_units"),
        }

    def _base_inputs(self):
        return {
            "industrial_output": Quantity(7.9e11, "industrial_output_units"),
            "IC": Quantity(2.1e11, "capital_units"),
            "SC": Quantity(1.44e11, "capital_units"),
            "AL": Quantity(0.9e9, "hectares"),
            "POP": Quantity(1.65e9, "persons"),
        }

    def test_init_stocks_has_4_pools(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)
        assert "L" in stocks
        assert "D_g" in stocks
        assert "D_s" in stocks
        assert "D_p" in stocks

    def test_compute_returns_derivatives(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, self._base_stocks(), self._base_inputs(), ctx)
        assert "d_L" in result
        assert "d_D_g" in result
        assert "d_D_s" in result
        assert "d_D_p" in result

    def test_maintenance_ratio_output(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, self._base_stocks(), self._base_inputs(), ctx)
        mr = result["maintenance_ratio"].magnitude
        assert 0.0 <= mr <= 2.0

    def test_military_spending_deducted(self) -> None:
        """Military drain must be deducted from Liquid Funds (WILIAM bug fix)."""
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, self._base_stocks(), self._base_inputs(), ctx)
        mil = result["military_spending"].magnitude
        assert mil > 0

    def test_debt_to_gdp_computed(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = self._base_stocks()
        stocks["D_g"] = Quantity(5.0e11, "capital_units")
        result = s.compute(0.0, stocks, self._base_inputs(), ctx)
        dtg = result["debt_to_gdp"].magnitude
        assert dtg > 0

    def test_collateral_value_positive(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, self._base_stocks(), self._base_inputs(), ctx)
        cv = result["collateral_value"].magnitude
        assert cv > 0

    def test_financial_resilience_high_when_no_debt(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, self._base_stocks(), self._base_inputs(), ctx)
        fr = result["financial_resilience"].magnitude
        # With zero debt, resilience should be very high
        assert fr > 1.0

    def test_declares_reads_includes_ic_sc_al(self) -> None:
        s = self._make_sector()
        reads = s.declares_reads()
        assert "industrial_output" in reads
        assert "IC" in reads
        assert "SC" in reads
        assert "AL" in reads

    def test_profit_positive_with_baseline(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, self._base_stocks(), self._base_inputs(), ctx)
        profit = result["profit"].magnitude
        assert profit > 0

    def test_loan_availability_drops_with_debt(self) -> None:
        s = self._make_sector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        # heavy debt scenario
        stocks_debt = self._base_stocks()
        stocks_debt["D_g"] = Quantity(1.5e12, "capital_units")
        result = s.compute(0.0, stocks_debt, self._base_inputs(), ctx)
        la = result["loan_availability"].magnitude
        assert la < 1.0


# ═══════════════════════════════════════════════════════════════════════
# Task 3: Energy Split
# ═══════════════════════════════════════════════════════════════════════


class TestEnergyFossil:
    def test_eroi_declines_with_depletion(self) -> None:
        from pyworldx.sectors.energy_fossil import EnergyFossilSector

        s = EnergyFossilSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        inputs_full = {"nr_fraction_remaining": Quantity(1.0, "dimensionless")}
        inputs_dep = {"nr_fraction_remaining": Quantity(0.1, "dimensionless")}

        r_full = s.compute(0.0, stocks, inputs_full, ctx)
        r_dep = s.compute(0.0, stocks, inputs_dep, ctx)

        assert r_full["fossil_eroi"].magnitude > r_dep["fossil_eroi"].magnitude

    def test_output_constrained_by_supply_mult(self) -> None:
        from pyworldx.sectors.energy_fossil import EnergyFossilSector

        s = EnergyFossilSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        r_full = s.compute(
            0.0, stocks, {"supply_multiplier_fossil": Quantity(1.0, "dimensionless")}, ctx
        )
        r_half = s.compute(
            0.0, stocks, {"supply_multiplier_fossil": Quantity(0.5, "dimensionless")}, ctx
        )

        assert r_full["fossil_output"].magnitude > r_half["fossil_output"].magnitude

    def test_broadcasts_energy_demand(self) -> None:
        from pyworldx.sectors.energy_fossil import EnergyFossilSector

        s = EnergyFossilSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, s.init_stocks(ctx), {}, ctx)
        assert "energy_demand_fossil" in result


class TestEnergySustainable:
    def test_stable_eroi(self) -> None:
        from pyworldx.sectors.energy_sustainable import EnergySustainableSector

        s = EnergySustainableSector()
        assert s.eroi == 12.0

    def test_output_positive(self) -> None:
        from pyworldx.sectors.energy_sustainable import EnergySustainableSector

        s = EnergySustainableSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        result = s.compute(0.0, s.init_stocks(ctx), {}, ctx)
        assert result["sustainable_output"].magnitude > 0


class TestEnergyTechnology:
    def test_metals_dependency(self) -> None:
        from pyworldx.sectors.energy_technology import EnergyTechnologySector

        s = EnergyTechnologySector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        r_avail = s.compute(
            0.0, stocks, {"tech_metals_availability": Quantity(1.0, "dimensionless")}, ctx
        )
        r_scarce = s.compute(
            0.0, stocks, {"tech_metals_availability": Quantity(0.1, "dimensionless")}, ctx
        )

        assert r_avail["technology_output"].magnitude > r_scarce["technology_output"].magnitude

    def test_trapped_capital_rises_with_scarcity(self) -> None:
        from pyworldx.sectors.energy_technology import EnergyTechnologySector

        s = EnergyTechnologySector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        r_avail = s.compute(
            0.0, stocks, {"tech_metals_availability": Quantity(1.0, "dimensionless")}, ctx
        )
        r_scarce = s.compute(
            0.0, stocks, {"tech_metals_availability": Quantity(0.2, "dimensionless")}, ctx
        )

        assert r_scarce["trapped_capital"].magnitude > r_avail["trapped_capital"].magnitude

    def test_eroi_depends_on_metals(self) -> None:
        from pyworldx.sectors.energy_technology import EnergyTechnologySector

        s = EnergyTechnologySector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        r_full = s.compute(
            0.0, stocks, {"tech_metals_availability": Quantity(1.0, "dimensionless")}, ctx
        )
        r_half = s.compute(
            0.0, stocks, {"tech_metals_availability": Quantity(0.5, "dimensionless")}, ctx
        )

        assert r_full["technology_eroi"].magnitude > r_half["technology_eroi"].magnitude

    def test_declares_tech_metals_demand(self) -> None:
        from pyworldx.sectors.energy_technology import EnergyTechnologySector

        s = EnergyTechnologySector()
        assert "tech_metals_demand" in s.declares_writes()


# ═══════════════════════════════════════════════════════════════════════
# Task 4: Pollution Split (GHG + Toxins)
# ═══════════════════════════════════════════════════════════════════════


class TestPollutionGHG:
    def test_init_ghg_stock(self) -> None:
        from pyworldx.sectors.pollution_ghg import PollutionGHGModule

        s = PollutionGHGModule()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)
        assert "ghg_stock" in stocks

    def test_emissions_increase_with_io(self) -> None:
        from pyworldx.sectors.pollution_ghg import PollutionGHGModule

        s = PollutionGHGModule()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        r_low = s.compute(
            0.0, stocks, {"industrial_output": Quantity(1e11, "industrial_output_units")}, ctx
        )
        r_high = s.compute(
            0.0, stocks, {"industrial_output": Quantity(1e12, "industrial_output_units")}, ctx
        )

        assert r_high["ghg_emission_rate"].magnitude > r_low["ghg_emission_rate"].magnitude

    def test_100yr_decay(self) -> None:
        from pyworldx.sectors.pollution_ghg import PollutionGHGModule

        s = PollutionGHGModule()
        assert s.tau_ghg == 100.0

    def test_radiative_forcing_zero_at_baseline(self) -> None:
        from pyworldx.sectors.pollution_ghg import PollutionGHGModule

        s = PollutionGHGModule(initial_ghg=1.0)
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)
        r = s.compute(0.0, stocks, {}, ctx)
        assert r["ghg_radiative_forcing"].magnitude == pytest.approx(0.0, abs=1e-10)


class TestPollutionToxins:
    def test_3_stage_cascade(self) -> None:
        from pyworldx.sectors.pollution_toxins import PollutionToxinModule

        s = PollutionToxinModule()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)
        assert "toxin_s1" in stocks
        assert "toxin_s2" in stocks
        assert "toxin_s3" in stocks

    def test_toxin_rises_with_tech_output(self) -> None:
        """Dynamic split: tech output produces MORE toxins (rare earth)."""
        from pyworldx.sectors.pollution_toxins import PollutionToxinModule

        s = PollutionToxinModule()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)

        r_no = s.compute(0.0, stocks, {"technology_output": Quantity(0.0, "energy_units")}, ctx)
        r_hi = s.compute(0.0, stocks, {"technology_output": Quantity(1e12, "energy_units")}, ctx)

        assert r_hi["d_toxin_s1"].magnitude > r_no["d_toxin_s1"].magnitude

    def test_health_multiplier_increases(self) -> None:
        from pyworldx.sectors.pollution_toxins import PollutionToxinModule

        s = PollutionToxinModule()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        # High toxin level
        stocks = {
            "toxin_s1": Quantity(5.0, "pollution_units"),
            "toxin_s2": Quantity(5.0, "pollution_units"),
            "toxin_s3": Quantity(5.0, "pollution_units"),
        }
        r = s.compute(0.0, stocks, {}, ctx)
        assert r["toxin_health_multiplier"].magnitude > 1.0

    def test_fertility_multiplier_decreases(self) -> None:
        from pyworldx.sectors.pollution_toxins import PollutionToxinModule

        s = PollutionToxinModule()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = {
            "toxin_s1": Quantity(5.0, "pollution_units"),
            "toxin_s2": Quantity(5.0, "pollution_units"),
            "toxin_s3": Quantity(5.0, "pollution_units"),
        }
        r = s.compute(0.0, stocks, {}, ctx)
        assert r["toxin_fertility_multiplier"].magnitude < 1.0


# ═══════════════════════════════════════════════════════════════════════
# Task 5: Gini Distribution Matrix
# ═══════════════════════════════════════════════════════════════════════


class TestGiniDistribution:
    def test_no_stocks(self) -> None:
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        stocks = s.init_stocks(ctx)
        assert stocks == {}

    def test_unequal_allocation_in_scarcity(self) -> None:
        """When food is scarce, top 10% gets disproportionately more."""
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        inputs = {"food_per_capita": Quantity(100.0, "food_units")}
        r = s.compute(0.0, {}, inputs, ctx)
        assert r["gini_food_top10"].magnitude > r["gini_food_bot90"].magnitude

    def test_equal_allocation_in_abundance(self) -> None:
        """When food is abundant, allocation approaches equality."""
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        inputs = {"food_per_capita": Quantity(500.0, "food_units")}
        r = s.compute(0.0, {}, inputs, ctx)
        # In abundance, top10 and bot90 per-capita should be closer
        ratio = r["gini_food_top10"].magnitude / max(r["gini_food_bot90"].magnitude, 1e-15)
        assert ratio < 3.0  # less extreme than scarcity

    def test_social_suicide_activated(self) -> None:
        """Social suicide triggers when bottom 90% FPC < 0.5 × subsistence."""
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        # Very low food → bottom 90% below subsistence
        inputs = {"food_per_capita": Quantity(30.0, "food_units")}
        r = s.compute(0.0, {}, inputs, ctx)
        assert r["social_suicide_active"].magnitude == 1.0

    def test_social_suicide_not_active_normally(self) -> None:
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        inputs = {"food_per_capita": Quantity(400.0, "food_units")}
        r = s.compute(0.0, {}, inputs, ctx)
        assert r["social_suicide_active"].magnitude == 0.0

    def test_drfm_top10_lower_than_bot90(self) -> None:
        """Top 10% has lower food mortality than bottom 90% in scarcity."""
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        inputs = {"food_per_capita": Quantity(100.0, "food_units")}
        r = s.compute(0.0, {}, inputs, ctx)
        assert r["DRFM_top10"].magnitude <= r["DRFM_bot90"].magnitude

    def test_drpm_bot90_higher_pollution_exposure(self) -> None:
        """Bottom 90% has higher pollution exposure (environmental injustice)."""
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        inputs = {"pollution_index": Quantity(5.0, "dimensionless")}
        r = s.compute(0.0, {}, inputs, ctx)
        assert r["DRPM_bot90"].magnitude > r["DRPM_top10"].magnitude

    def test_output_contains_11_variables(self) -> None:
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        assert len(s.declares_writes()) == 11

    def test_conservation_of_food(self) -> None:
        """Total food = top10*0.1 + bot90*0.9 ≈ original FPC."""
        from pyworldx.sectors.gini_distribution import GiniDistributionSector

        s = GiniDistributionSector()
        ctx = type("FakeCtx", (), {"shared_state": {}, "dt": 1.0})()
        fpc = 300.0
        inputs = {"food_per_capita": Quantity(fpc, "food_units")}
        r = s.compute(0.0, {}, inputs, ctx)
        total = r["gini_food_top10"].magnitude * 0.1 + r["gini_food_bot90"].magnitude * 0.9
        assert total == pytest.approx(fpc, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════
# Task 6: v2 Scenario Suite
# ═══════════════════════════════════════════════════════════════════════


class TestV2Scenarios:
    def test_list_scenarios(self) -> None:
        from pyworldx.scenarios.v2_scenarios import list_v2_scenarios

        names = list_v2_scenarios()
        assert len(names) == 7
        assert "carrington_event" in names
        assert "minsky_moment" in names
        assert "absolute_decoupling" in names

    def test_build_carrington(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        s = build_v2_scenario("carrington_event")
        assert s.name == "carrington_event"
        assert "v2" in s.tags
        assert "carrington" in s.tags

    def test_build_minsky_moment(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        s = build_v2_scenario("minsky_moment")
        assert "finance.interest_rate" in s.parameter_overrides

    def test_build_absolute_decoupling_overrides(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        s = build_v2_scenario("absolute_decoupling")
        # 2 parameter overrides: resource_elasticity=0, fcaor_min/max=0.05
        assert len(s.parameter_overrides) >= 2
        assert "capital.resource_elasticity" in s.parameter_overrides
        assert "resources.fcaor_min" in s.parameter_overrides
        assert "resources.fcaor_max" in s.parameter_overrides
        assert "v2" in s.tags
        assert "decoupling" in s.tags

    def test_build_ai_entropy_trap(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        s = build_v2_scenario("ai_entropy_trap")
        assert "ai" in s.tags

    def test_build_energiewende(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        s = build_v2_scenario("energiewende")
        assert "v2" in s.tags
        assert "transition" in s.tags

    def test_build_lifeboating(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        s = build_v2_scenario("lifeboating")
        assert "contagion" in s.tags

    def test_unknown_scenario_raises(self) -> None:
        from pyworldx.scenarios.v2_scenarios import build_v2_scenario

        with pytest.raises(KeyError, match="Unknown v2 scenario"):
            build_v2_scenario("nonexistent")
