# Phase 2 — v2.1 Biophysical Realism

**Date:** 2026-04-14  
**Goal:** Add the biophysical feedback loops that determine carrying capacity  
**Duration:** 6-8 weeks  
**Scope:** 6 tasks — SEIR Module, Regional Objects, Climate Module, Human Capital, Phosphorus, Ecosystem Services  

---

## Rationale

Phase 1 builds the v2 core architecture (CentralRegistrar, Finance, Energy split, Pollution split, Gini, v2 scenarios). Phase 2 adds the biophysical detail that makes carrying capacity endogenous rather than assumed. Each task is specified by notebook conversations (Q48–Q49, Q31, Q27, Q24, Q30/Q57) and plugs into the Phase 1 architecture.

---

## Task 1: SEIR Module (Parallel Disease State Matrix)

**Status:** ❌ Not implemented  
**Source:** Notebook Q48, q40  
**Effort:** 1-2 weeks  

### What It Is

Each of the 4 demographic cohorts (0-14, 15-44, 45-64, 65+) is subdivided into S/E/I/R compartments. 4 × 4 = 16 SEIR state variables. Dynamic contact graphs model how cohorts interact (not uniform mixing).

**Key design decisions from Q48:**
- Working-age (20-60) lockdown → removed from workforce → Labor Force Multiplier crashes
- Elderly (60+) isolation → protects them from mortality without penalizing industrial output (they're not in the workforce)
- Each RK4 sub-step: SEIR matrix broadcasts death-rate multiplier to demographic module + tallies healthy non-quarantined 20-60 → broadcasts as actual available labor

### Files Created/Modified

- `pyworldx/sectors/seir_module.py` — New: SEIR with 16 state variables, dynamic contact graphs
- `pyworldx/sectors/population.py` — Extend 4-cohort model with SEIR sub-compartments
- `pyworldx/core/engine.py` — SEIR module broadcasts Labor Force Multiplier to shared state

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_seir_16_state_variables` | 4 cohorts × 4 compartments = 16 states |
| 2 | `test_dynamic_contact_graphs` | Different cohorts have different interaction patterns |
| 3 | `test_working_age_lockdown_crashes_labor` | Working-age isolation reduces Labor Force Multiplier |
| 4 | `test_elderly_isolation_protects_without_economic_penalty` | Elderly isolation doesn't reduce industrial output |
| 5 | `test_death_rate_broadcast` | SEIR broadcasts mortality multiplier to population sector |
| 6 | `test_recovery_delay` | Economic scarring lasts ~3 years post-pandemic |
| 7 | `test_seir_in_engine` | End-to-end: pandemic scenario runs through engine |
| 8 | `test_pandemic_scenario_from_q40` | SEIR + Labor Multiplier + Financial Contagion (from q40) |

### Acceptance Criteria

- [ ] 16 SEIR state variables (4 cohorts × 4 compartments)
- [ ] Dynamic contact graphs (not uniform mixing)
- [ ] Working-age lockdown crashes Labor Force Multiplier
- [ ] Elderly isolation protects without economic penalty
- [ ] All 8 tests pass
- [ ] All previous tests still pass

---

## Task 2: Regional Objects (N-Region Architecture)

**Status:** ❌ Not implemented  
**Source:** Notebook Q49, q41  
**Effort:** 2-3 weeks  

### What It Is

**Hybrid architecture (from Q49):**
- **Layer 1 (OO):** N distinct Regional Objects — each owns its state vectors and local derivative methods
- **Layer 2 (Vectorized):** CentralRegistrar aggregates demands into vectorized arrays; resolves N×N trade matrix [T_i,j] and migration matrix flows simultaneously
- **Layer 3 (Intra-region):** Parallel array logic for Gini stratification within each region

**Global zero-sum mass balance:** sum of regional derivatives = 0 for trade flows.

**Urban-to-rural migration (from q41):**
- Urbanization reversal during decline
- C_scale "lifeboating" severs supply linkages
- Metropolises abandoned when Maintenance Gap hits urban infrastructure

### Files Created/Modified

- `pyworldx/core/regional_object.py` — New: `RegionalObject` class
- `pyworldx/core/central_registrar.py` — Extend: N×N trade/migration matrix resolution
- `pyworldx/sectors/population.py` — Extend: regional population arrays
- `pyworldx/sectors/capital.py` — Extend: regional capital stocks

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_n_regional_objects` | N distinct regions each have own state vectors |
| 2 | `test_trade_matrix_zero_sum` | Σ regional trade derivatives = 0 |
| 3 | `test_migration_flows` | Population flows between regions based on attractiveness |
| 4 | `test_central_registrar_vectorized_resolution` | N×N matrix resolved via NumPy, not loops |
| 5 | `test_urban_to_rural_migration` | Urbanization reverses during decline phase |
| 6 | `test_lifeboating_severs_trade` | C_scale drop → trade linkages cut |
| 7 | `test_contagion_of_collapse` | One region's collapse triggers neighbors' decline |
| 8 | `test_gini_within_regions` | Intra-region Gini stratification works |
| 9 | `test_mass_balance_across_regions` | No creation/destruction of matter across regional boundaries |

### Acceptance Criteria

- [ ] N Regional Objects with independent state vectors
- [ ] N×N trade matrix resolved by CentralRegistrar (zero-sum)
- [ ] Migration flows based on attractiveness differentials
- [ ] Urban-to-rural migration during decline
- [ ] Lifeboating (C_scale drop) severs trade linkages
- [ ] All 9 tests pass
- [ ] All previous tests still pass

---

## Task 3: Climate Module (GHG/Aerosol Bifurcation + Temperature ODE)

**Status:** ❌ Not implemented  
**Source:** Notebook Q31  
**Effort:** 1-2 weeks  

### What It Is

Temperature ODE with termination shock physics:
```
dT_atm/dt = λ × [RF_GHG(G_stock) - RF_Aero(A_flux)] - OceanThermalInertia
```

- GHG decay constant: τ_GHG ~ 100 years
- Aerosol decay constant: τ_Aero → 0 (1st-order SMOOTH with delay_time = 0.05 years ≈ 2 weeks)

**Termination Shock:** industrial crash → aerosol emissions cease → cooling removed while GHG heating remains → abrupt thermal spike → Agriculture Heat Shock Multiplier penalizes surviving food base.

### Files Created/Modified

- `pyworldx/sectors/climate.py` — New: Temperature ODE, GHG/aerosol radiative forcing
- `pyworldx/sectors/pollution_ghg.py` — Connect: GHG stock → radiative forcing
- `pyworldx/sectors/agriculture.py` — Add: Heat Shock Multiplier from temperature

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_ghg_radiative_forcing` | GHG stock → positive radiative forcing |
| 2 | `test_aerosol_radiative_forcing` | Aerosol flux → negative radiative forcing (cooling) |
| 3 | `test_aerosol_fast_decay` | Aerosols decay in ~2 weeks (0.05 year delay) |
| 4 | `test_temperature_ode_responds_to_forcing` | T increases with net positive forcing |
| 5 | `test_termination_shock` | Industrial crash → aerosol vanishes → thermal spike |
| 6 | `test_heat_shock_affects_agriculture` | Temperature spike reduces food yield |
| 7 | `test_climate_module_integration` | Full climate module runs without NaN or crash |

### Acceptance Criteria

- [ ] Temperature ODE with GHG + Aerosol radiative forcing
- [ ] Aerosol decay in ~2 weeks (1st-order SMOOTH, 0.05 year delay)
- [ ] Termination Shock: industrial crash → thermal spike
- [ ] Heat Shock Multiplier affects agriculture
- [ ] All 7 tests pass
- [ ] All previous tests still pass

---

## Task 4: Human Capital Stock

**Status:** ❌ Not implemented  
**Source:** Notebook q27  
**Effort:** 1-2 weeks  

### What It Is

Human Capital (H) as a dynamic stock within working-age cohorts:
```
dH/dt = EducationRate - SkillDegradationRate - MortalityLoss
```

Where:
- EducationRate = f(Education Index) × LaborForce
- SkillDegradationRate = base degradation rate
- MortalityLoss = H × DeathRate

**Cobb-Douglas with H as explicit factor:**
```
Q = A × K^α × R^β × H^(1-α-β)
```
Where (1-α-β) = 50-60% output elasticity — human capital accounts for majority of value.

### Files Created/Modified

- `pyworldx/sectors/human_capital.py` — New: Human Capital stock ODE
- `pyworldx/sectors/population.py` — Connect: Education Index → EducationRate
- `pyworldx/sectors/capital.py` — Extend: Cobb-Douglas with H factor

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_human_capital_ode` | dH/dt = EducationRate - Degradation - MortalityLoss |
| 2 | `test_education_rate_depends_on_services` | EducationRate = f(EI) × LaborForce |
| 3 | `test_cobb_douglas_with_h` | Q = A × K^α × R^β × H^(1-α-β) |
| 4 | `test_h_output_elasticity_50_60_percent` | (1-α-β) = 50-60% |
| 5 | `test_skill_degradation_during_collapse` | H drops when Education services starve |
| 6 | `test_human_capital_integration` | Full engine runs with Human Capital stock |

### Acceptance Criteria

- [ ] Human Capital stock with correct ODE
- [ ] Cobb-Douglas production includes H factor with 50-60% output elasticity
- [ ] Education Rate depends on Service sector output
- [ ] All 6 tests pass
- [ ] All previous tests still pass

---

## Task 5: Phosphorus Mass-Balance

**Status:** ❌ Not implemented  
**Source:** Notebook Q24  
**Effort:** 1-2 weeks  

### What It Is

Phosphorus as explicit mass-balance stock:
```
dP_soc/dt = P_mining + P_rec - P_loss - P_waste
P_rec = P_waste × PRR_t
dPRR/dt = ProfitabilityFactor × TechnologyFactor - DissipationDelay
```

**Key constraints:**
- 85% Stability Floor: "only better than 85% recycling will be able to preserve a high global population"
- Below 85% → biophysical starvation crisis (natural weathering supports only 1.5-2 billion people)
- BeROI Limit: PRR capped when Benefit Return on Investment of recycling falls to zero
- 65% Energy Ceiling caps total energy for resource extraction/processing

### Files Created/Modified

- `pyworldx/sectors/phosphorus.py` — New: Phosphorus sector with mass-balance
- `pyworldx/sectors/agriculture.py` — Connect: P_soc → land yield modifier
- `pyworldx/core/central_registrar.py` — Extend: phosphorus energy demand aggregation

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_phosphorus_mass_balance` | dP_soc/dt = P_mining + P_rec - P_loss - P_waste |
| 2 | `test_prr_ode` | dPRR/dt = ProfitabilityFactor × TechnologyFactor - DissipationDelay |
| 3 | `test_85_percent_stability_floor` | Below 85% → starvation crisis |
| 4 | `test_be_roi_limits_recycling` | PRR capped when recycling energy cost too high |
| 5 | `test_energy_ceiling_caps_phosphorus` | 65% ceiling limits P extraction energy |
| 6 | `test_phosphorus_affects_agriculture` | P_soc directly modifies food production |
| 7 | `test_phosphorus_integration` | Full engine runs with Phosphorus sector |

### Acceptance Criteria

- [ ] Phosphorus stock with correct mass-balance ODE
- [ ] PRR dynamics with 85% stability floor
- [ ] BeROI limits on recycling
- [ ] 65% Energy Ceiling affects phosphorus extraction
- [ ] All 7 tests pass
- [ ] All previous tests still pass

---

## Task 6: Ecosystem Services Proxy (ESP) + Artificial Ecosystem Services (AES)

**Status:** ❌ Not implemented  
**Source:** Notebook Q30, Q57  
**Effort:** 1-2 weeks  

### What It Is

**ESP stock (from Q57):**
```
dESP/dt = r(T) × ESP × (1 - ESP) - DegradationRate
```
- ESP scaled 0→1.0 (1.0 = optimal)
- r(T) = intrinsic growth rate, suppressed by temperature T
- Logistic ODE: tipping point when DegradationRate > temperature-suppressed RegenerationRate

**AES replacement cost (from Q57):**
```
Service Deficit = 1.0 - ESP
TNDS_AES = f(Service Deficit) × c_AES
```
- c_AES rises exponentially
- AES classified as Total Non-Discretionary Spending → subtracted directly from Liquid Funds → drains Industrial Capital

**Feedback loop:** ESP degrades → AES cost rises exponentially → Liquid Funds depleted → Industrial Capital starved → system cannibalizes own industrial base to pay for artificial life support → accelerates peak and collapse.

### Files Created/Modified

- `pyworldx/sectors/ecosystem_services.py` — New: ESP stock + AES cost function
- `pyworldx/sectors/finance.py` — Connect: TNDS_AES drains Liquid Funds
- `pyworldx/sectors/agriculture.py` — Connect: ESP → land yield modifier

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_esp_logistic_regeneration` | RegenerationRate = r(T) × ESP × (1 - ESP) |
| 2 | `test_temperature_suppresses_regeneration` | r(T) decreases as T increases |
| 3 | `test_tipping_point` | DegradationRate > RegenerationRate → permanent collapse |
| 4 | `test_aes_replacement_cost` | TNDS_AES = f(Service Deficit) × c_AES (exponential) |
| 5 | `test_aes_drains_liquid_funds` | TNDS_AES subtracted from Liquid Funds |
| 6 | `test_cannibalization_feedback` | ESP degradation → Industrial Capital starvation |
| 7 | `test_esp_integration` | Full engine runs with ESP + AES |

### Acceptance Criteria

- [ ] ESP stock with logistic ODE (temperature-suppressed regeneration)
- [ ] AES replacement cost as TNDS (exponential in Service Deficit)
- [ ] AES drains Liquid Funds → starves Industrial Capital
- [ ] Tipping point: permanent ecosystem collapse
- [ ] All 7 tests pass
- [ ] All previous tests still pass

---

## Task Dependencies

```
Task 1 (SEIR Module) ────────────────── independent
Task 3 (Climate Module) ─────────────── needs Task 4 (Pollution split from Phase 1)
Task 4 (Human Capital) ──────────────── independent
Task 5 (Phosphorus) ─────────────────── needs Task 3 (Energy split from Phase 1)
Task 6 (ESP/AES) ────────────────────── needs Task 2 (FinanceSector from Phase 1)
Task 2 (Regional Objects) ────────────── needs Task 1 (CentralRegistrar from Phase 1)
                                        needs Task 5 (Gini from Phase 1)

Recommended order:
1. Tasks 1 + 3 + 4 in parallel (SEIR, Climate, Human Capital)
2. Task 6 (ESP/AES) — needs FinanceSector from Phase 1
3. Task 5 (Phosphorus) — needs Energy split from Phase 1
4. Task 2 (Regional Objects) — most complex, do last
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SEIR module too complex for 4-cohort model | Medium | Medium — 16 SEIR state variables (4 cohorts × 4 compartments) adds significant state space | Start with 2 cohorts (working-age + elderly) and expand |
| Regional objects explode computational cost | High | High — N × (all sectors) × 1/512 dt | Start with 2 regions. Profile performance before scaling. |
| Climate module data not available for calibration | Medium | Medium — need historical temperature data | Use NOAA/GISS data from data_pipeline. Mark as provisional. |
| Phosphorus data uncertain | Medium | Low — use USGS phosphate rock data from data_pipeline | Document uncertainty ranges. |
| ESP/AES parameters speculative | High | Low — these are forward-looking mechanisms, not historical calibration | Document parameter ranges as sensitivity analysis inputs. |

---

## Deliberately Deferred Items (Covered by Notebook Corpus, Not Assigned Here)

The following items are covered in the research corpus but are **not assigned to Phase 2 tasks**. They are deferred to Phase 2.1 or v2.2+ to prevent scope creep:

| Item | Source | Rationale for Deferral |
|------|--------|------------------------|
| **Soil Organic Carbon (SOC)** stock + CO₂/CH₄ feedbacks | Q25 | Depends on Climate Module (Phase 2 Task 3). Can be added as a sub-module after climate is proven stable. |
| **Dietary Trophic Multiplier (DTM)** — endogenous diet shift | Q29 | Enhancement to Agriculture sector. Not blocking for v2 architecture validation. |
| **L²[0,T] integral norm + ROC-Value** calibration metrics | Q10 | Calibration methodology, not engine architecture. Can be implemented independently at any time. |
| **Hydrological Sector** — aquifers, desalination, 65% ceiling | Q31, synthesis 04 | HIGH priority but requires Climate Module + CentralRegistrar. Target for Phase 2.2 or v2.2. |
| **Age Dependency Ratio (ADR)** pension drain | Q46, synthesis 05 | Requires FinanceSector (Phase 1 Task 2). Target for Phase 2.1 or separate sub-phase. |

---

## Definition of Done

- [ ] All 6 tasks completed
- [ ] All new tests pass (8 + 9 + 7 + 6 + 7 + 7 = 44 tests)
- [ ] All Phase 0 + 0.5 + 1 tests still pass (576 tests)
- [ ] Total test count: 576 + 44 = 620 tests
- [ ] mypy strict passes on all modified files
- [ ] ruff check passes on all modified files
- [ ] Regional architecture demonstrated with ≥ 2 regions
- [ ] SEIR pandemic scenario runs end-to-end
- [ ] Climate module produces temperature trajectory
- [ ] ESP degradation triggers AES → Industrial Capital starvation feedback
