# Phase 2 — Implementation Plan (Bulletproof)

**Date:** 2026-04-14  
**Goal:** Add 6 biophysical modules to pyWorldX: SEIR, Regional Objects, Climate, Human Capital, Phosphorus, Ecosystem Services  
**Scope:** 6 tasks + cross-module integration + comprehensive testing  
**Duration:** 6-8 weeks  

---

## Pre-Implementation Findings (3-Subagent Investigation)

### Critical Bugs Discovered

| # | Bug | Location | Impact | Fix Required |
|---|-----|----------|--------|-------------|
| 1 | `energy_fossil` reads `NRFR` but resources writes `nr_fraction_remaining` | `energy_fossil.py:91` vs `resources.py:124` | Fossil sector gets 0.0 for NRFR — EROI calculation is wrong | Rename key or add alias |
| 2 | No Phase 1 end-to-end integration test | N/A | FinanceSector + EnergySplit + PollutionSplit + GiniDistribution + CentralRegistrar have never run together in Engine | Must add before Phase 2 |
| 3 | Balance auditor tolerances are absolute (1e-6 warn, 1e-3 fail) | `balance.py:73-74` | May be too tight for large Phase 2 stocks or too loose for small ones | Make configurable per group or relative |
| 4 | No exception handling in main run() loop | `engine.py:149-310` | Any sector compute() error crashes the entire simulation | Consider adding try/except with diagnostic |
| 5 | No shared_state in RunContext after construction | `engine.py:109` | RunContext.shared_state is empty — sectors can't access it via ctx.get_input() | Engine must populate ctx.shared_state = shared |

### Engine Capacity Assessment

| Metric | Finding | Phase 2 Impact |
|--------|---------|---------------|
| Max sectors | No limit (dict-based) | Adding 6 modules is trivial |
| Max state variables | No limit (dict-based) | 20+ new stocks is fine |
| RK4 scaling | O(N) per stage, N = stocks per sector | SEIR with 16 stocks: trivial |
| SEIR at 1/512 dt | Requires substep_ratio=512 | 2048 compute() calls per master step — heavy but feasible |
| Memory footprint | ~63 MB worst case (1/512 dt recording) | Acceptable; recording only at master boundaries |
| Exception handling | None in main loop — crashes on error | Phase 2 sectors must be thoroughly unit-tested before integration |

### Architectural Decisions Needed

| Decision | Options | Recommendation |
|----------|---------|---------------|
| SEIR substep ratio | 16:1, 64:1, 256:1, 512:1 | Start with 64:1 (timestep_hint=0.015625). 512:1 is overkill for disease dynamics with 10+ year timescales |
| Regional trade resolution | New engine phase, or algebraic loop | Use algebraic loop resolution (Phase 2) — trade matrix is a fixed-point problem |
| Human Capital sector | Standalone sector, or extend Population | Standalone sector — has its own ODE, reads/writes different variables |
| Phosphorus sector | Standalone, or extend Agriculture | Standalone — mass-balance stock, energy demands, recycling economics |
| Climate module | Standalone, or extend Pollution GHG | Standalone — needs temperature ODE, aerosol stock, radiative forcing |
| ESP sector | Standalone, or extend Agriculture | Standalone — logistic ODE, AES cost function, TNDS linkage to Finance |

---

## Implementation Order (Dependency Graph)

```
Phase 1 Integration Test (prerequisite) ──────────────────────────┐
                                                                  │
Task A: Fix NRFR naming bug ──────────────────────────────────────┤
                                                                  │
Task 1: Human Capital ────────────────────────────────────────────┤
   (depends on: nothing — reads Service Capita, writes H)        │
                                                                  │
Task 2: Phosphorus ───────────────────────────────────────────────┤
   (depends on: nothing — reads/writes own stocks,              │
    broadcasts energy_demand_phosphorus)                         │
                                                                  │
Task 3: Ecosystem Services ───────────────────────────────────────┤
   (depends on: nothing — reads pollution + land use,            │
    writes ESP, TNDS_AES to FinanceSector)                       │
                                                                  │
Task 4: Climate Module ───────────────────────────────────────────┤
   (depends on: Task 3 (climate affects ESP r(T)))              │
                                                                  │
Task 5: SEIR Module ──────────────────────────────────────────────┤
   (depends on: Task 4 (climate affects disease range),          │
    Task 1 (Human Capital affected by disease mortality))        │
                                                                  │
Task 6: Regional Objects ─────────────────────────────────────────┤
   (depends on: ALL ABOVE — integrates all modules per region)   │
                                                                  │
Task 7: Cross-Module Integration Tests ───────────────────────────┘
   (depends on: ALL ABOVE)
```

**Recommended execution order:**
1. Fix NRFR naming bug (30 minutes)
2. Add Phase 1 end-to-end integration test (1 day)
3. Task 1: Human Capital (2-3 days)
4. Task 2: Phosphorus (3-4 days)
5. Task 3: Ecosystem Services (3-4 days)
6. Task 4: Climate Module (2-3 days)
7. Task 5: SEIR Module (4-5 days)
8. Task 6: Regional Objects (5-7 days)
9. Task 7: Cross-module integration tests (3-4 days)

---

## Task 0: Prerequisites (1-2 days)

### 0a. Fix NRFR Naming Bug

**File:** `pyworldx/sectors/energy_fossil.py`, line 91  
**Current:** `nrfr = inputs.get("NRFR", Quantity(1.0, "dimensionless")).magnitude`  
**Resources writes:** `"nr_fraction_remaining"` (not `"NRFR"`)  
**Fix:** Change to `inputs.get("nr_fraction_remaining", ...)`

### 0b. RunContext.shared_state Population

**File:** `pyworldx/core/engine.py`, line 109  
**Current:** `ctx = RunContext(master_dt=..., t_start=..., t_end=...)` — shared_state empty  
**Fix:** `ctx = RunContext(master_dt=..., t_start=..., t_end=..., shared_state=shared)`  
**Impact:** Sectors can access shared state via `ctx.get_input(name)` if needed

### 0c. Phase 1 End-to-End Integration Test

**New file:** `tests/integration/test_phase1_integration.py`  
**What it tests:** Engine run with ALL Phase 1 sectors together:
- PopulationSector, CapitalSector, AgricultureSector, ResourcesSector, PollutionSector (existing 5)
- FinanceSector
- EnergyFossilSector, EnergySustainableSector, EnergyTechnologySector
- PollutionGHGModule, PollutionToxinModule
- GiniDistributionSector
- CentralRegistrar (enabled)
- WelfareSector

**Assertions:**
- Engine completes 200-year run without crash or NaN
- FinanceSector: L starts positive, debt accumulates
- Energy sectors: fossil_output > 0, EROI declines over time
- Pollution split: ghg_stock rises, toxin stocks rise
- Gini: food_top10 > food_bot90 in scarcity
- CentralRegistrar: supply_multipliers written to shared

### 0d. conftest.py with Shared Fixtures

**New file:** `tests/conftest.py`  
**Fixtures:**
- `fake_ctx()` — returns RunContext with shared_state
- `default_5_sectors()` — returns list of 5 World3 sectors
- `phase1_all_sectors()` — returns list of all Phase 1 sectors
- `run_200yr(sector_list)` — runs engine for 200 years, returns RunResult

---

## Task 1: Human Capital Sector (2-3 days)

### Specification (from q64)

```
Stock: H (human capital index, 0-1 scale, initial = 0.3)
ODE: dH/dt = EducationRate - SkillDegradationRate - MortalityLoss
EducationRate = f(Service_Output_Per_Capita) × LaborForce
SkillDegradationRate = H / skill_half_life (5-10 year half-life)
MortalityLoss = H × DeathRate

Production: Q = A × K^α × R^β × H^(1-α-β)
  where (1-α-β) = 50-60% output elasticity
```

### Implementation

**File:** `pyworldx/sectors/human_capital.py`

**declares_reads():**
```python
["service_output_per_capita", "death_rate", "POP"]
```

**declares_writes():**
```python
["H", "education_rate", "skill_degradation_rate", "human_capital_multiplier"]
```

**init_stocks():**
```python
{"H": Quantity(0.3, "dimensionless")}  # Pre-industrial baseline
```

**compute():**
- Read: service_output_per_capita, death_rate, POP
- Compute: education_rate = table_lookup(SOPC, _EDU_RATE_X, _EDU_RATE_Y) × POP
- Compute: skill_degradation = H / _SKILL_HALF_LIFE
- Compute: mortality_loss = H × death_rate
- Compute: dH = education_rate - skill_degradation - mortality_loss
- Return: d_H, education_rate, skill_degradation_rate, human_capital_multiplier

**Integration with Capital Sector:**
- CapitalSector.compute() must read H from shared
- Modify production function: `IO = A × IC^α × (H × LaborForce)^(1-α-β)`
- Add `"H"` to CapitalSector.declares_reads()

**Tests:**
1. `test_init_stocks` — H initialized to 0.3
2. `test_education_rate_increases_with_sopc` — Higher SOPC → higher education_rate
3. `test_skill_degradation` — H decays without education
4. `test_mortality_loss` — Higher death_rate → faster H loss
5. `test_h_bounded_0_to_1` — H stays in [0, 1]
6. `test_analytical_decay` — Isolated H decay matches exponential (hybrid criterion)
7. `test_capital_uses_h` — CapitalSector production increases with H

---

## Task 2: Phosphorus Sector (3-4 days)

### Specification (from q65, q66, q70)

```
Stock: P_soc (soil phosphorus, Mt P, initial from USGS data)
Stock: PRR (phosphorus recycling rate, 0-1, initial = 0.5)

ODE: dP_soc/dt = P_mining + P_recycling - P_loss - P_waste
ODE: dPRR/dt = ProfitabilityFactor × TechnologyFactor - DissipationDelay

P_mining = f(NRFR) × mining_capacity  # declines with depletion
P_recycling = P_waste × PRR
P_loss = P_soc × weathering_rate  # slow, geologic
P_waste = agricultural_demand × waste_fraction

ProfitabilityFactor = energy_cost_mining / energy_cost_recycling
TechnologyFactor = f(cumulative_industrial_output)  # learning curve
DissipationDelay = P_soc × sedimentation_rate  # lost to ocean

Energy demand: energy_demand_phosphorus = P_mining × energy_per_tonne + P_recycling × energy_per_tonne_recycled
```

### Implementation

**File:** `pyworldx/sectors/phosphorus.py`

**declares_reads():**
```python
["industrial_output", "food_per_capita", "nr_fraction_remaining",
 "supply_multiplier_phosphorus"]
```

**declares_writes():**
```python
["P_soc", "PRR", "phosphorus_mining_rate", "phosphorus_recycling_rate",
 "energy_demand_phosphorus", "phosphorus_availability"]
```

**init_stocks():**
```python
{
    "P_soc": Quantity(<from_USGS>, "megatonnes_P"),
    "PRR": Quantity(0.5, "dimensionless"),
}
```

**CentralRegistrar integration:**
- Writes `energy_demand_phosphorus` to shared
- Reads `supply_multiplier_phosphorus` from shared
- Writes `liquid_funds_phosphorus` and `security_value_phosphorus` (defaults = 1.0)

**Integration with Agriculture:**
- AgricultureSector must read `phosphorus_availability` from shared
- Land yield multiplier modified by phosphorus: `LYMC_adjusted = LYMC × f(P_soc)`

**Tests:**
1. `test_init_stocks` — P_soc and PRR initialized
2. `test_mining_declines_with_nrfr` — Mining rate drops as NRFR drops
3. `test_recycling_increases_with_prr` — Higher PRR → more recycling
4. `test_prr_increases_with_profitability` — Cheaper recycling → higher PRR
5. `test_energy_demand_broadcast` — Writes energy_demand_phosphorus to shared
6. `test_supply_multiplier_affects_output` — Reduced supply multiplier → lower mining
7. `test_85_percent_floor_behavior` — Below 85%, gradual yield decline (not instant crash)
8. `test_analytical_weathering` — Isolated P_soc decay matches exponential (hybrid criterion)

---

## Task 3: Ecosystem Services Sector (3-4 days)

### Specification (from q67, q68, q70)

```
Stock: ESP (ecosystem services proxy, 0-1, initial = 1.0)

ODE: dESP/dt = r(T) × ESP × (1 - ESP) - DegradationRate

r(T) = r0 × f(T)  # temperature-dependent, suppressed by warming
DegradationRate = pollution_degradation + land_use_degradation
  pollution_degradation = pollution_index × pollution_sensitivity
  land_use_degradation = (PAL - AL) / PAL × land_use_sensitivity

Service Deficit = 1.0 - ESP
TNDS_AES = c_AES × (Service Deficit)^exponent  # exponential scaling
  where exponent > 1 (e.g., 2.0 or 3.0)

FinanceSector linkage: TNDS_AES subtracted from dL/dt
```

### Implementation

**File:** `pyworldx/sectors/ecosystem_services.py`

**declares_reads():**
```python
["pollution_index", "AL", "temperature_anomaly"]
```

**declares_writes():**
```python
["ESP", "tns_aes", "service_deficit", "energy_demand_aes",
 "supply_multiplier_aes"]
```

**init_stocks():**
```python
{"ESP": Quantity(1.0, "dimensionless")}
```

**FinanceSector integration:**
- FinanceSector.compute() reads `tns_aes` from inputs
- `tns_aes` subtracted from dL/dt

**CentralRegistrar integration:**
- Writes `energy_demand_aes` to shared
- Reads `supply_multiplier_aes` from shared

**Tests:**
1. `test_init_stocks` — ESP initialized to 1.0
2. `test_degradation_increases_with_pollution` — Higher pollution → faster ESP decline
3. `test_degradation_increases_with_land_use` — Less AL → faster ESP decline
4. `test_regeneration_at_baseline` — At ESP=1.0, r(T)×ESP×(1-ESP) = 0
5. `test_tnds_aes_scales_exponentially` — As ESP→0, TNDS_AES grows super-linearly
6. `test_energy_demand_broadcast` — Writes energy_demand_aes to shared
7. `test_finance_sector_reads_tnds_aes` — FinanceSector subtracts TNDS from dL/dt
8. `test_100_percent_replacement_impossible` — At some point, energy ceiling blocks further AES

---

## Task 4: Climate Module (2-3 days)

### Specification (from q62, q63, q70)

```
Stock: T (temperature anomaly, °C, initial = 0.0)
Stock: A (aerosol concentration, index, initial = 1.0)

ODE: dT/dt = λ × [RF_GHG - RF_Aero] - OceanThermalInertia × T
ODE: dA/dt = k_aero × industrial_output - A / tau_aero

RF_GHG = 5.35 × ln(CO2 / CO2_preindustrial)
RF_Aero = k_aero_rf × A  # linear relationship

tau_aero = 0.05 years (~2 weeks)
lambda = climate_sensitivity (°C per W/m²)
OceanThermalInertia = 1 / ocean_response_time
```

### Implementation

**File:** `pyworldx/sectors/climate.py`

**declares_reads():**
```python
["industrial_output", "pollution_generation"]
```

**declares_writes():**
```python
["T", "A", "temperature_anomaly", "aerosol_index",
 "radiative_forcing_ghg", "radiative_forcing_aero",
 "heat_shock_multiplier", "energy_demand_climate"]
```

**init_stocks():**
```python
{
    "T": Quantity(0.0, "deg_C_anomaly"),
    "A": Quantity(1.0, "dimensionless"),
}
```

**Heat Shock Multiplier to Agriculture:**
- Write `heat_shock_multiplier` to shared
- AgricultureSector reads it and modifies land yield: `LYMC_adjusted = LYMC × heat_shock_multiplier`
- heat_shock_multiplier = 1.0 at T=0, drops non-linearly above threshold (e.g., 2.0°C)

**CentralRegistrar integration:**
- Writes `energy_demand_climate` (heating/cooling demand as function of |T|)

**Tests:**
1. `test_init_stocks` — T=0, A=1.0
2. `test_aerosol_decay` — Without industrial output, A decays with tau=0.05yr
3. `test_aerosol_production` — Industrial output increases A
4. `test_temperature_rises_with_ghg` — Higher pollution → T increases
5. `test_termination_shock` — Industrial crash → A→0 → T spikes
6. `test_heat_shock_affects_agriculture` — High T → heat_shock_multiplier < 1.0
7. `test_analytical_aerosol_decay` — A(t) = A0 × exp(-t/0.05) (hybrid criterion)

---

## Task 5: SEIR Module (4-5 days)

### Specification (from q58, q59, q70)

```
Per cohort (0-14, 15-44, 45-64, 65+):
  Stocks: S, E, I, R (susceptible, exposed, infected, recovered)
  Total: 16 state variables

ODEs per cohort:
  dS/dt = -beta × C × S/N - births + deaths_S
  dE/dt = beta × C × S/N - sigma × E - deaths_E
  dI/dt = sigma × E - gamma × I - deaths_I
  dR/dt = gamma × I - deaths_R

beta = transmission rate (age-specific)
C = contact rate from dynamic contact graph
sigma = 1/incubation_period
gamma = 1/recovery_period

Contact Graph (normal):
  C_ij = baseline_contact_rate[i][j]  # 4×4 matrix

Contact Graph (lockdown):
  C_ij = 0 for edges involving working-age cohorts
  C_ij = reduced for elderly isolation

Labor Force Multiplier:
  LFM = (S_working + R_working) / total_working
  where working = cohorts 15-44 and 45-64
```

### Implementation

**File:** `pyworldx/sectors/seir.py`

**Note:** This sector has 16 stocks. It must be sub-stepped for accuracy.  
**substep_ratio:** 64:1 (timestep_hint = 1/64 = 0.015625)

**declares_reads():**
```python
["temperature_anomaly", "POP", "P1", "P2", "P3", "P4"]
```

**declares_writes():**
```python
["S_0_14", "E_0_14", "I_0_14", "R_0_14",
 "S_15_44", "E_15_44", "I_15_44", "R_15_44",
 "S_45_64", "E_45_64", "I_45_64", "R_45_64",
 "S_65_plus", "E_65_plus", "I_65_plus", "R_65_plus",
 "labor_force_multiplier", "infected_count", "reproduction_number"]
```

**init_stocks():**
```python
{
    "S_0_14": Quantity(P1_initial × (1-epsilon), "persons"),
    "E_0_14": Quantity(P1_initial × epsilon, "persons"),
    "I_0_14": Quantity(0, "persons"),
    "R_0_14": Quantity(0, "persons"),
    # ... repeat for each cohort
}
```

**Labor Force Multiplier broadcasting:**
- Writes `labor_force_multiplier` to shared each timestep
- CapitalSector reads it and modifies labor input: `effective_labor = labor_force × LFM`

**Temperature coupling:**
- Reads `temperature_anomaly` from Climate module
- Modifies beta (transmission rate) based on temperature

**Tests:**
1. `test_init_stocks` — All 16 stocks initialized correctly
2. `test_seir_conservation` — S+E+I+R = total population per cohort
3. `test_infection_spreads` — With I>0, S decreases and E increases
4. `test_recovery` — Infected eventually recover (I→0, R→max)
5. `test_lockdown_reduces_transmission` — Contact graph severing reduces spread
6. `test_labor_force_multiplier` — Working-age infection reduces LFM
7. `test_temperature_affects_transmission` — Higher T increases beta
8. `test_analytical_sir` — Simplified SIR (no E compartment) matches known solution (hybrid criterion)
9. `test_substep_ratio` — SEIR runs at 64:1 substep ratio

---

## Task 6: Regional Objects (5-7 days)

### Specification (from q60, q61, q70)

```
N regions, each with its own:
  - Population (4 cohorts)
  - Capital (IC, SC)
  - Agriculture (AL, LFERT)
  - Resources (NR)
  - Pollution (PPOL)
  - Human Capital (H)
  - Phosphorus (P_soc)
  - ESP
  - Climate (T, A)
  - SEIR (16 states)
  - Finance (L, D_g, D_s, D_p)

Trade Matrix (dissipative):
  Export[i→j] = f(surplus_i, deficit_j, transport_cost_ij)
  Import[j] = Σ Export[i→j] × (1 - transport_loss)
  Transport energy = Σ Export[i→j] × energy_per_unit_distance

Migration Flows:
  Migration[i→j] = f(attractiveness_j - attractiveness_i)
  Migration continues during lifeboating (trade severed)
  Destination dilution: immediate reduction in SOPC, IOPC
```

### Implementation

**File:** `pyworldx/sectors/regional.py`

**This is the most complex task.** It requires:
1. A `RegionalObject` class that contains all sectors for one region
2. A `RegionalEngine` wrapper that manages inter-region flows
3. Trade matrix computation (algebraic fixed-point)
4. Migration flow computation
5. Energy demand aggregation across regions

**Approach:** Rather than creating a new sector, create a `RegionalWrapper` that:
- Takes existing sector instances and wraps them per region
- Computes trade/migration flows between regions
- Broadcasts energy demands to CentralRegistrar
- Receives supply multipliers and distributes to regional sectors

**declares_reads()** (for the wrapper):
```python
["trade_attractiveness", "migration_attractiveness"]
```

**declares_writes()**:
```python
["energy_demand_regional_trade", "supply_multiplier_regional_trade"]
```

**Tests:**
1. `test_two_region_trade` — Region A exports to B, B imports from A
2. `test_trade_dissipative` — Export > Import due to transport loss
3. `test_migration_flows` — Population moves from low to high attractiveness
4. `test_migration_continues_during_lifeboating` — Trade severed but migration continues
5. `test_destination_dilution` — Incoming migrants reduce SOPC/IOPC
6. `test_energy_demand_aggregation` — Trade energy demand written to shared
7. `test_lifeboating_severs_trade` — C_scale drop → trade → 0

---

## Task 7: Cross-Module Integration Tests (3-4 days)

### Critical Cross-Couplings to Test (from q69)

| Coupling | Test | Expected Behavior |
|----------|------|-------------------|
| Climate → SEIR | Temperature increases → disease transmission increases | Higher T → higher beta → faster infection spread |
| Migration → Human Capital | Migration to region → Service Capita dilution → Education Rate drops → H collapse | Influx → SOPC↓ → education_rate↓ → H↓ |
| Phosphorus → ESP | P-dependent agriculture pollutes → ESP degrades → AES required | Mining↑ → pollution↑ → ESP↓ → TNDS_AES↑ |
| Aerosol Termination Shock | Industrial crash → aerosol→0 → T spike → agriculture destroyed | IO crash → A→0 in 2 weeks → T↑ → heat_shock→0 → food↓ |
| TNDS Cannibalization Loop | AES drains Liquid Funds → maintenance starves → capital depreciates | ESP↓ → TNDS_AES↑ → L↓ → maintenance_ratio↓ → IC depreciation↑ |

### Test File

**New file:** `tests/integration/test_phase2_cross_coupling.py`

Each test runs a minimal engine with the relevant sectors and verifies the coupling behavior.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SEIR at 64:1 substep ratio too slow | Medium | Medium — 2048 compute() calls per master step | Profile first; reduce to 16:1 if needed |
| Regional Objects too complex for single task | High | High — could block all downstream work | Split into 6a (single region) + 6b (multi-region trade) + 6c (migration) |
| Cross-module coupling errors produce wrong dynamics | High | High — fundamental model behavior wrong | Write analytical tests for each coupling before integration |
| Balance auditor tolerances too tight/loose | Medium | Low — false warnings or missed violations | Make tolerances configurable per conservation group |
| FinanceSector + TNDS_AES feedback loop unstable | Medium | Medium — L oscillates or diverges | Test with extreme ESP degradation scenarios |
| Climate module aerosol decay at 0.05yr causes stiffness | Low | Medium — RK4 may need smaller dt for aerosol | Aerosol is single-stock with simple ODE — RK4 handles it fine at master dt |

---

## Definition of Done

- [ ] All 6 Phase 2 modules implemented with correct declares_reads/writes
- [ ] All new sectors have individual unit tests (analytical sub-case tests where applicable)
- [ ] Phase 1 end-to-end integration test passes
- [ ] All 5 critical cross-couplings tested and verified
- [ ] Energy ceiling integration: P, AES, Trade, Climate broadcast energy demands
- [ ] CentralRegistrar handles new energy demand keys correctly
- [ ] NRFR naming bug fixed
- [ ] RunContext.shared_state populated
- [ ] conftest.py with shared fixtures created
- [ ] Full test suite (535 + new tests) passes with 0 failures
- [ ] mypy strict passes on all new files
- [ ] ruff check passes on all new files
- [ ] No new sectors have naming collisions with existing variables
- [ ] All new sectors have metadata with correct validation_status, equation_source, approximations
