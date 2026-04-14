# Phase 1 — v2 Core Architecture

**Date:** 2026-04-14  
**Goal:** Build the v2 architecture that qualitatively transforms pyWorldX from a World3 simulator into a biophysically-grounded global systems model  
**Duration:** 6-8 weeks  
**Scope:** 6 tasks — CentralRegistrar, FinanceSector, Energy split, Pollution split, Gini arrays, v2 scenarios  

---

## Rationale

Phase 0 finishes v1. Phase 0.5 fixes v1 correctness gaps. Phase 1 is where the model becomes fundamentally different from World3. Every task is specified by the notebook conversations (Q01–Q10 architecture + Q47–Q57 design guide) and builds on the v1 foundation.

---

## Task 1: CentralRegistrar (Pre-Derivative Resolution Pass)

**Status:** ❌ Not implemented  
**Source:** Notebook Q09, Q52  
**Effort:** 1-2 weeks  
**Blocks:** Task 2 (Energy), Task 4 (Gini), Task 5 (Scenarios), Phase 2 tasks

### What It Is

A new component in the engine core that sits between sector compute and derivative calculation. It enforces the 65% Energy Ceiling and resolves Supply Multipliers before sectors finalize their derivatives.

### Critical Design Fixes (from audit)

**1. Use `shared_state` dict, NOT new `broadcast_demands()` method.** The audit found that adding `broadcast_demands()` to the `BaseSector` Protocol would be a **breaking change** requiring modifications to all 11+ existing sector implementations. The notebooks describe "Demand/Supply Linkage" via interface ports, not a specific method name.

**Correct approach:** Use the existing `RunContext.shared_state` dict for demand broadcasting. Sectors write their demands to `ctx.shared_state` during `compute()`. The CentralRegistrar reads from it, resolves constraints, writes back SupplyMultipliers. No protocol changes needed.

**2. Include "Security Value" allocation.** Q52 explicitly states allocation is based on BOTH "Ability to Pay" (Liquid Funds) AND "Security Value" (capital/energy directed toward nodes with higher Security Value — typically wealthy core or industrial/military capital). The original plan only mentioned Ability to Pay.

**3. Dependency graph with topological sort.** Q52 describes the dependency graph as the specific Python data structure to avoid algebraic loops. The CentralRegistrar should leverage the existing `DependencyGraph` from `pyworldx/core/graph.py` rather than inventing a new mechanism.

### Architecture

```
Per RK4 sub-step:
  1. Sectors compute() — write demands to ctx.shared_state
  2. CentralRegistrar reads demands, checks 65% Energy Ceiling
  3. If ceiling breached: compute SupplyMultipliers < 1.0
     Allocation based on: (a) Ability to Pay (Liquid Funds), (b) Security Value
  4. Write SupplyMultipliers back to ctx.shared_state
  5. Sectors compute derivatives with multipliers applied
  6. RK4 integration proceeds
```

**Key design decisions from Q52:**
- **NOT equal scaling** — "Ability to Pay" (Liquid Funds) AND "Security Value" determine access during scarcity
- Basic survival sectors are NOT universally protected — price spikes starve bottom 90%
- Loop avoidance: Dependency graph (existing `DependencyGraph` class) + State-Gating (every cross-sector loop contains Integrator or Delay) + 1/512 dt overshoot tolerance

### Files Modified/Created

- `pyworldx/core/central_registrar.py` — New: `CentralRegistrar` class
- `pyworldx/core/engine.py` — Integrate CentralRegistrar into run() loop
- `pyworldx/sectors/base.py` — No changes needed (uses existing `shared_state` in RunContext)

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_central_registrar_initialization` | Correct defaults |
| 2 | `test_no_ceiling_breach_pass_through` | SupplyMultipliers=1.0 when demand < 65% |
| 3 | `test_ceiling_breach_reduces_multipliers` | SupplyMultipliers < 1.0 when demand > 65% |
| 4 | `test_market_based_allocation_ability_to_pay` | Higher Liquid Funds gets larger share during scarcity |
| 5 | `test_security_value_allocation` | Higher Security Value gets priority during scarcity |
| 6 | `test_energy_ceiling_65_percent` | Exact threshold at 0.65 |
| 7 | `test_state_gating_prevents_loops` | No algebraic deadlocks with CentralRegistrar |
| 8 | `test_overshoot_stabilizes` | Brief ceiling overshoot stabilizes in next increments |
| 9 | `test_uses_shared_state_not_new_method` | Sectors use ctx.shared_state for demands (no broadcast_demands method) |
| 10 | `test_backward_compatible` | Engine without CentralRegistrar produces identical output |
| 11 | `test_v1_rip_still_passes` | Canonical R-I-P test still passes with CentralRegistrar active but ceiling not breached |

### Acceptance Criteria

- [ ] CentralRegistrar class implements demand broadcast → ceiling check → SupplyMultiplier resolution
- [ ] 65% Energy Ceiling enforced with Ability to Pay + Security Value allocation (NOT equal scaling)
- [ ] Uses existing `RunContext.shared_state` dict (no new BaseSector method)
- [ ] State-Gating ensures no algebraic deadlocks
- [ ] Engine integrates CentralRegistrar as optional hook (default: disabled for backward compatibility)
- [ ] All 11 tests pass
- [ ] All Phase 0 + 0.5 tests still pass

---

## Task 2: FinanceSector (Merged with WILIAM)

**Status:** ❌ Not implemented  
**Source:** Notebook Q05, Q10, Q53  
**Effort:** 2-3 weeks  
**Blocks:** Task 1's "Ability to Pay" allocation, Phase 2 SEIR module

### What It Is

A new sector with 4 ODEs:
1. **Liquid Funds (L):** `dL/dt = IndustrialProfits + LoanTakingRate + MoneyPrinting - Investments - InterestPayments - OperationCosts`
2. **General Debt (D_g):** `dD_g/dt = LoanTakingRate - D_g / 30yr`
3. **Speculative Debt (D_s):** crisis-response borrowing
4. **Pension Debt (D_p):** aging population liabilities

Plus: capital collateralization, 150% Debt-to-GDP ceiling, endogenous market pricing.

### Critical Design Fixes (from audit)

**1. "Governance multiplier" for gradual gating.** Q05 describes the 150% Debt-to-GDP limit as a function: `Loan Availability = f(Deficit) if Debt/GDP < 1.5, else 0`. The plan originally showed a hard cutoff. The governance multiplier provides **gradual gating** — loan availability decreases as the ratio approaches 1.5, not a sudden cliff.

**2. WILIAM military_fraction is computed but NOT subtracted.** Audit found that `pyworldx/sectors/wiliam/economy.py` computes `military = self.military_fraction * output` but does NOT subtract it from `d_wiliam_K`. The military is written as a fraction output but doesn't actually drain capital. The merge must fix this: military spending becomes an OperationCost drain on Liquid Funds.

**3. Three distinct debt pools.** Q05 specifies at least three distinct pools (General, Speculative, Pensions) with the 30-year repayment delay. The plan captures this but should emphasize they're separate ODEs, not a single aggregated debt stock.

### Merge Strategy with WILIAM

WILIAM already has Cobb-Douglas production with military allocation drag. The merge:
- WILIAM's `industrial_output` (Cobb-Douglas) → Revenue (`Q × p`) → Profit (`TV - TC`) → Liquid Funds inflow
- WILIAM's military allocation → becomes one of the OperationCost drains on Liquid Funds (fix the bug where it's not actually subtracted)
- WILIAM's timestep_hint (computed from substep_ratio) → FinanceSector also sub-stepped (needs fine resolution for stiff equations)

**Physical → Financial linkage (from Q53):**
```
Revenue = Q × p (endogenous market price)
Cost = μ×K (capital maintenance) + σ×R (resource extraction) + ω×L (labor)
Profit = Revenue - Cost → dL/dt inflow
```

**Depreciation → Debt linkage (from Q53):**
```
150% ceiling breached → Loan Availability = 0
→ Liquid Funds frozen by legacy interest payments
→ Actual Maintenance < Required → MaintenanceRatio < 1.0
→ φ(MaintenanceRatio) exponential spike → physical depreciation accelerates
```

**Loop avoidance (from Q53):** State-Gating — IC, L, D are all Stocks (Integrators), not auxiliary variables. The levels buffer equations, breaking simultaneous algebraic dependency.

### Files Created/Modified

- `pyworldx/sectors/finance.py` — New: FinanceSector (merged WILIAM + Liquid Funds + Debt pools)
- `pyworldx/sectors/wiliam/` — Merge WILIAM economy into FinanceSector
- `pyworldx/sectors/capital.py` — Connect to FinanceSector (profit → Liquid Funds inflow)
- `pyworldx/core/engine.py` — FinanceSector sub-stepped at finer resolution (q54: 1/512 dt handles stiffness)

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_liquid_funds_ode` | dL/dt computes correctly with all inflows/outflows |
| 2 | `test_debt_pool_ode` | Debt amortization over 30 years |
| 3 | `test_three_distinct_debt_pools` | General, Speculative, Pensions are separate ODEs |
| 4 | `test_150_percent_ceiling_blocks_loans` | Loan Availability = 0 when Debt/GDP ≥ 1.5 |
| 5 | `test_governance_multiplier_gradual_gating` | Loan availability decreases gradually as ratio approaches 1.5 |
| 6 | `test_capital_collateralization` | V_c = Stock × Price for IC, SC, AL |
| 7 | `test_financial_resilience_threshold` | Investment Rate → 0 when ΣV_c < Debt |
| 8 | `test_wiliam_output_to_liquid_funds` | WILIAM Cobb-Douglas → Revenue → Profit → L inflow |
| 9 | `test_military_drains_liquid_funds` | Military spending subtracted from Liquid Funds (fix existing bug) |
| 10 | `test_minsky_moment` | Debt > ΣV_c triggers broad-front collapse |
| 11 | `test_cash_box_no_longer_crashes` | Empty Liquid Funds triggers borrowing, not crash |
| 12 | `test_no_algebraic_loops` | State-Gating prevents zero-delay deadlocks |
| 13 | `test_full_engine_with_finance` | Full World3-03 + Finance runs without crash or NaN |
| 14 | `test_substep_finance` | FinanceSector sub-stepped at correct ratio |
| 15 | `test_interest_drains_liquid_funds` | Interest payments = D × 0.03 reduce L |

### Acceptance Criteria

- [ ] FinanceSector implements Liquid Funds + 3 distinct Debt Pool ODEs
- [ ] Capital collateralization (V_c = Stock × Price) for IC, SC, AL
- [ ] 150% Debt-to-GDP ceiling with gradual governance multiplier gating
- [ ] WILIAM output correctly monetized and fed into Liquid Funds
- [ ] Military spending actually drains Liquid Funds (fix existing bug)
- [ ] Maintenance Gap links FinanceSector to Capital sector depreciation
- [ ] All 15 tests pass
- [ ] All previous tests still pass
- [ ] mypy strict passes

---

## Task 3: Energy Sector Split (Fossil / Sustainable / Technology)

**Status:** ❌ Not implemented (Resources sector is single aggregated NR stock)  
**Source:** Notebook Q47, Q03, Q08  
**Effort:** 1-2 weeks

### What It Is

Split the single Resources sector into three energy sub-sectors:
1. **Fossil Fuels** — hydrocarbons + conventional nuclear, EROI declines with ore grade
2. **Sustainable/Renewable** — hydropower, biofuels, EROI relatively stable
3. **Technology Energies** — solar PV, wind, geothermal, EROI depends on Technology Metals availability

Each has independent EROI curve. They compete for capital via endogenous profitability (higher profit attracts more Investment from Liquid Funds).

### Critical Design Fixes (from audit)

**1. Specific Technology Metals.** Q47 explicitly names: silver, gallium, indium, rare earths (neodymium). The plan originally mentioned "Ag, In, Nd, etc." — must include gallium.

**2. Financial capital trapping mechanism.** Q47 describes the "Resulting Capital Competition" dynamic: "even if the 'Technology Energies' sub-sector has massive financial capital from the Liquid Funds pool, the RK4 Engine mathematically prohibits the instantiation of the requested solar or wind arrays if the physical materials cannot be supplied due to the 65% energy ceiling." The trapped financial capital either remains unspent (lowering the Capital Output Ratio) or is out-competed by lower-complexity energy systems.

### CentralRegistrar interaction

- Technology Energies broadcast material demands for Ag, Ga, In, Nd, etc. via `ctx.shared_state`
- CentralRegistrar aggregates energy demands, checks 65% ceiling
- If ceiling breached: SupplyMultipliers throttle extraction
- "When actual supply < demand, production is reduced"
- Financial capital for Technology Energies is trapped if materials unavailable → lowers COR

### Files Created/Modified

- `pyworldx/sectors/energy_fossil.py` — Fossil fuel extraction with declining EROI
- `pyworldx/sectors/energy_sustainable.py` — Hydropower, biofuels
- `pyworldx/sectors/energy_technology.py` — Solar PV, wind, geothermal with Technology Metals demands
- `pyworldx/sectors/resources.py` — Refactor or deprecate in favor of energy sub-sectors
- `pyworldx/core/central_registrar.py` — Add energy demand aggregation

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_fossil_eroi_declines_with_depletion` | EROI drops as NRFR decreases |
| 2 | `test_sustainable_eroi_stable` | EROI remains stable for renewables |
| 3 | `test_technology_eroi_depends_on_metals` | EROI drops when Technology Metals scarce |
| 4 | `test_endogenous_profitability_allocation` | Higher profit sub-sector attracts more investment |
| 5 | `test_technology_metals_demand_linkage` | Technology Energies broadcast demands for Ag, Ga, In, Nd |
| 6 | `test_central_registrar_throttles_energy` | 65% ceiling reduces extraction via SupplyMultipliers |
| 7 | `test_financial_capital_trapping` | Technology Energies capital trapped when materials unavailable → lowers COR |
| 8 | `test_energy_sector_integration` | All 3 sub-sectors run together without crash |
| 9 | `test_supply_less_than_demand_reduces_production` | Mechanical choke when metals unavailable |

### Acceptance Criteria

- [ ] 3 energy sub-sectors with independent EROI curves
- [ ] Endogenous profitability-based capital allocation
- [ ] Technology Metals Demand Linkages (Ag, Ga, In, Nd) to CentralRegistrar
- [ ] 65% Energy Ceiling throttles extraction
- [ ] Financial capital trapping when materials unavailable
- [ ] All 9 tests pass
- [ ] All previous tests still pass

---

## Task 4: Pollution Split (GHG + Micro-Toxins)

**Status:** ❌ Not implemented (single PPOL stock)  
**Source:** Notebook Q55, Q03, Q12  
**Effort:** 1-2 weeks

### What It Is

Split the single Persistent Pollution stock into two modules:
1. **GHG Module** — 5-stock carbon model, 100+ year delay, drives climate/thermal arrays
2. **Micro-Toxin Module** — endocrine disruptors, POPs, heavy metals, 111.8-year 3rd-order delay, drives health/mortality/fertility

**Dynamic split (not fixed fraction):** Independent sector-specific intensity coefficients per industrial activity. As Green Capital expands: GHG inflow declines (less fossil combustion) BUT Toxin inflow rises (rare earth extraction/processing for solar/wind/EV).

### Critical Design Fixes (from audit)

**1. Specific GHG sources.** Q55 names: calcination, fossil fuel combustion, natural gas leakage. Plan originally only said "fossil combustion."

**2. Specific coefficient examples.** Q55 provides: `ai_co2_intensity_2020` and `ai_ewaste_intensity_2020`. Include these.

### Key insight from Q55

> "Decarbonization (energy efficiency) scales faster than material circularity (bounded by thermodynamics) → material toxicity can ultimately dominate the long-lived pollution stock even as carbon footprint drops."

### Files Created/Modified

- `pyworldx/sectors/pollution_ghg.py` — GHG module with carbon cycle
- `pyworldx/sectors/pollution_toxins.py` — Micro-toxin module with 111.8-yr delay
- `pyworldx/sectors/pollution.py` — Refactor: split into GHG + Toxin modules, or deprecate

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_ghg_long_lived_delay` | GHG stock persists 100+ years |
| 2 | `test_toxin_111.8_year_delay` | 3rd-order cascaded ODE delay at 111.8 years |
| 3 | `test_dynamic_split_with_green_capital` | GHG inflow declines, Toxin inflow rises as green capital expands |
| 4 | `test_intensity_coefficients_per_activity` | Different industrial activities have different GHG/Toxin intensity |
| 5 | `test_ghg_sources_include_calcination` | GHG sources: calcination, fossil combustion, natural gas leakage |
| 6 | `test_toxin_affects_health` | Micro-toxins increase health costs, mortality, reduce fertility |
| 7 | `test_ghg_affects_climate` | GHG stock drives climate/temperature variable |
| 8 | `test_split_integration` | Both modules run together without crash or NaN |

### Acceptance Criteria

- [ ] GHG module with 100+ year delay (calcination, fossil combustion, gas leakage sources)
- [ ] Micro-Toxin module with 111.8-year 3rd-order cascaded ODE delay
- [ ] Dynamic split via intensity coefficients (not fixed fraction)
- [ ] Toxins affect health costs, mortality, fertility
- [ ] GHG drives climate/temperature variable
- [ ] All 8 tests pass
- [ ] All previous tests still pass

---

## Task 5: Gini Distribution Matrix

**Status:** ❌ Not implemented (global averages only)  
**Source:** Notebook Q06, Q50  
**Effort:** 1-2 weeks

### What It Is

Replace global average resource allocation with a Distribution Matrix that allocates food/capital by percentile with Intake Accentuation during scarcity.

**Implementation (from Q50):**
- Pre-computed non-linear lookup tables (TABHL-style) for Gini weight response curves per percentile at varying scarcity levels
- Live vectorized NumPy array sum for normalization denominator
- Scalar-to-array multiplication for final allocation
- **NOT iterative Python loops**

**Bifurcated Collapse (from Q06):**
- Top 10%: "Comprehensive Technology" moderate decline trajectory
- Bottom 90%: "Business as Usual" demographic crash

### Critical Design Fixes (from audit)

**1. Social Suicide Governance Multiplier mechanism.** Q06 describes the specific mechanism: "equal sharing becomes social suicide if the average amount... is not enough to maintain life." The system "ceases to attempt equitable distribution to prevent the 'rich' cohort from falling below subsistence, effectively 'sacrificing' the bottom 90%." The plan must describe the Governance Multiplier that drives this behavior, not just the threshold.

**2. Three distinct mortality multipliers.** Q06 describes `DRFM_p` (death-rate-from-food), `DRHM_p` (health service deprivation), and `DRPM_p` (pollution) — all stratified by percentile. The plan originally only mentioned "Gini-stratified mortality multipliers" generically.

**3. Threshold-gated exponentials for bottom 90% survival.** Q06 describes how survival equations for the bottom 90% change from linear dependencies to threshold-gated exponentials during collapse.

### Files Created/Modified

- `pyworldx/sectors/gini_distribution.py` — New: Gini matrix with lookup tables + NumPy vectorized operations
- `pyworldx/sectors/population.py` — Extend 4-cohort model with Gini-stratified mortality multipliers (DRFM_p, DRHM_p, DRPM_p)
- `pyworldx/core/engine.py` — Integrate Gini distribution into master loop

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_gini_lookup_tables` | Pre-computed tables have correct shape |
| 2 | `test_intake_accentuation` | Bottom share drops more than proportionally during scarcity |
| 3 | `test_vectorized_summation` | NumPy array sum for normalization (no Python loops) |
| 4 | `test_social_suicide_governance_multiplier` | Equal sharing abandoned when average below subsistence via Governance Multiplier |
| 5 | `test_bifurcated_collapse` | Top 10% plateaus, bottom 90% crashes |
| 6 | `test_three_stratified_mortality_multipliers` | DRFM_p, DRHM_p, DRPM_p all stratified by percentile |
| 7 | `test_threshold_gated_exponentials` | Bottom 90% survival equations switch to exponentials during collapse |
| 8 | `test_gini_in_engine` | End-to-end: Gini distribution affects mortality trajectories |
| 9 | `test_performance` | Gini computation completes in < 1ms per timestep (vectorized) |

### Acceptance Criteria

- [ ] Gini Distribution Matrix with pre-computed lookup tables
- [ ] Vectorized NumPy operations (no Python loops)
- [ ] Intake Accentuation during scarcity
- [ ] Social Suicide Governance Multiplier mechanism implemented
- [ ] Three stratified mortality multipliers (DRFM_p, DRHM_p, DRPM_p)
- [ ] Threshold-gated exponentials for bottom 90% during collapse
- [ ] All 9 tests pass
- [ ] All previous tests still pass
- [ ] Performance: < 1ms per timestep

---

## Task 6: v2 Scenario Suite

**Status:** ❌ Not implemented (current scenarios test World3-03, not v2)  
**Source:** Notebook Q51  
**Effort:** 1 week

### 6 Scenarios

| # | Scenario | Trigger | Tests |
|---|----------|---------|-------|
| 1 | **Carrington Event** | 50% instantaneous IC destruction | Financial liquidity trap, re-industrialization prohibited |
| 2 | **Minsky Moment** | Total Debt > ΣV_c | Investment Rate → 0, broad-front collapse |
| 2b | **Minsky Moment (Nature variant)** | ESP → 0, AES drains IC | BeROI negative → industrial starvation |
| 3 | **Absolute Decoupling** (null hypothesis) | 5 thermodynamic overrides | Proves decoupling requires violating physics |
| 4 | **AI Growth vs. Stagnation** | frac_io_ai_2050=6%, ai_CO2_intensity=0.15, ai_ewaste=3.5e-4 | AI as entropy trap |
| 5 | **Giant Leap / Energiewende** | 90% fossil phase-out 2020-2060 | Implementation Delay + Material Drag, Non-Discretionary Investment 24%→36% |
| 6 | **Contagious Disintegration** (Lifeboating) | FPC < 230 or Debt/GDP > 150% → C_scale 1.0→0.0 | Contagion of Collapse across regional network |

### Critical Design Fixes (from audit)

**1. Decoupling scenario has 5 overrides (per Q22).** Q51's abbreviated list shows 4, but Q22 (the definitive source for the decoupling experiment) explicitly specifies 5: (1) β=0 in Cobb-Douglas, (2) FCAOR clamped to 0.05, (3) 65% Energy Ceiling disabled, (4) TNDS for R&D set to 0, (5) 100% Phosphorus Recycling Rate at zero energy cost (bypassing the 85% biophysical stability floor). The 5th override tests the thermodynamic impossibility of perfect circularity.

**2. Minsky Moment has a "Nature variant".** Q51 describes a secondary Minsky Moment triggered when Ecosystem Services Proxy (ESP) drops near zero, forcing Industrial Capital to fund Artificial Ecosystem Services (AES), driving BeROI negative and starving the industrial sector. The plan originally only captured the primary financial variant.

### Files Created/Modified

- `pyworldx/scenarios/v2_scenarios.py` — New: 6 v2 scenario factories (+ 1 Nature variant)
- `pyworldx/scenarios/scenario.py` — Add v2 scenarios to BUILTIN_SCENARIOS

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_carrington_triggers_liquidity_trap` | 50% IC destruction → Debt/GDP > 150% → Investment → 0 |
| 2 | `test_minsky_moment_scenario` | Debt > ΣV_c → Investment Rate → 0 |
| 3 | `test_minsky_nature_variant` | ESP → 0 → AES drains IC → BeROI negative |
| 4 | `test_decoupling_null_hypothesis` | 5 overrides produce infinite GDP growth (proves decoupling violates physics) |
| 5 | `test_ai_growth_acts_as_entropy_trap` | AI scaling increases pollution peak by 4% |
| 6 | `test_energiewende_material_drag` | Fossil phase-out elevates Non-Discretionary Investment to 36% |
| 7 | `test_lifeboating_contagion` | C_scale drop cascades across network |
| 8 | `test_all_v2_scenarios_run_without_crash` | All 6+1 scenarios complete without NaN or exception |

### Acceptance Criteria

- [ ] All 6 v2 scenarios implemented as Scenario factories (+ 1 Nature variant)
- [ ] Decoupling scenario uses exactly 5 overrides (per Q22: β=0, FCAOR clamped, no ceiling, TNDS=0, 100% PRR at zero cost)
- [ ] Each scenario exercises its specific feedback loop
- [ ] All 8 tests pass
- [ ] All previous tests still pass

---

## Task Dependencies

```
Task 1 (CentralRegistrar) ──────────────────────────────────┐
    │                                                        │
    ├── Task 2 (FinanceSector) ──────────────────────────────┤
    │    │                                                    │
    │    ├── Task 3 (Energy split) ───────────────────────────┤
    │    │    │                                                │
    │    │    ├── Task 4 (Pollution split) ────────────────────┤
    │    │    │    │                                            │
    │    │    │    ├── Task 5 (Gini) ───────────────────────────┤
    │    │    │    │    │                                        │
    │    │    │    │    └── Task 6 (v2 Scenarios) ───────────────┘
    │    │    │    │
    │    │    │    └─ Needs: Task 2 (FinanceSector) for Liquid Funds
    │    │    │
    │    │    └─ Needs: Task 2 (FinanceSector) for profitability
    │    │
    │    └─ Needs: Task 1 (CentralRegistrar) for 65% ceiling
    │
    └─ Blocks: Tasks 2-5 all depend on CentralRegistrar

Recommended order:
1. Task 1 (CentralRegistrar) — foundational
2. Task 2 (FinanceSector) — needs CentralRegistrar
3. Tasks 3 + 4 in parallel (Energy split + Pollution split) — both need FinanceSector
4. Task 5 (Gini) — needs FinanceSector for "Ability to Pay"
5. Task 6 (v2 Scenarios) — needs all of the above
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CentralRegistrar changes existing sector behavior | Medium | High — all downstream tasks depend on it | Keep it optional (default: disabled). Add comprehensive backward compatibility tests. |
| FinanceSector introduces algebraic loops | Medium | Medium — State-Gating should prevent them, but verify | Extensive loop detection tests. If loops appear, increase substep resolution. |
| Energy split requires data not in data_pipeline | Low | Medium — need EROI curves for each energy type | Use literature values from WORLD6/7. Mark as provisional until empirical calibration. |
| Pollution split changes NRMSD scores | Certain (by design) | Medium — re-run validation to document new scores | Document old vs. new NRMSD. The split should improve pollution NRMSD. |
| Gini matrix performance too slow | Low | Medium — vectorized NumPy should be fast | Benchmark. If > 1ms per timestep, optimize or reduce percentile resolution. |
| v2 scenarios produce unrealistic dynamics | Medium | Low — scenarios are stress tests, not predictions | Document expected dynamics. If unrealistic, investigate but don't block. |

---

## Definition of Done

- [ ] All 6 tasks completed
- [ ] All new tests pass (11 + 15 + 9 + 8 + 9 + 8 = 60 tests)
- [ ] All Phase 0 + 0.5 tests still pass (499 + 17 = 516 tests)
- [ ] Total test count: 516 + 60 = 576 tests
- [ ] mypy strict passes on all modified files
- [ ] ruff check passes on all modified files
- [ ] World3-03 validation re-run with v2 architecture — NRMSD documented
- [ ] All 6+1 v2 scenarios produce documented, expected dynamics
