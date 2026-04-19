# Phase 2 Remediation Tasks

- `[/]` **Phase A: Engine Core & Orchestration**
  - `[ ]` **Fix #12 (Scenario Layer Illusion):** Wire `Scenario.apply_policies()` and exogenous overrides into the main RK4 execution loop in `engine.py` so that scenarios actually run.
  - `[ ]` **Fix #2 (Equal Allocation Bug):** Update `central_registrar.py` to calculate "Ability to Pay" by reading true economic size variables instead of defaulting to 1.0.
  - `[ ]` **Fix #8 (Broken Energy Ceiling - Part 1):** Ensure `energy_supply_factor` is broadcast globally from the CentralRegistrar to all sectors.

- `[ ]` **Phase B: Economic & Financial Linkage**
  - `[ ]` **Fix #10 (Military Investment Bug):** Fix the copy-paste error in `finance.py` by replacing `military_fraction` with `reinvestment_fraction`.
  - `[ ]` **Fix #11 (Education Free Lunch):** Calculate the cost of education (`education_tnds`) in `human_capital.py` and declare it as a write.
  - `[ ]` **Fix #9 (Capital Stealing):** Forward economic damages calculated in `welfare.py` as `damages_tnds` to the Finance sector, so they drain real capital.
  - `[ ]` **Fix #15 (SEIR Labor Bypass):** Update `capital.py` to read and multiply Phase D labor output by the `labor_force_multiplier` from SEIR.
  - `[ ]` **Fix #8 (Broken Energy Ceiling - Part 2):** Update `capital.py` and `agriculture.py` to read and apply the `energy_supply_factor` from the Registrar.
  - `[ ]` Ensure `finance.py` aggregates all Total Non-Discretionary Spending (TNDS) from other sectors.

- `[ ]` **Phase C: Biophysical Unification**
  - `[ ]` **Fix #7 (Tech Metals Illusion):** Add a calculation for `tech_metals_availability` (in `resources.py` or internally) that drops as cumulative extraction rises, and wire it into `energy_technology.py`.
  - `[ ]` **Fix #6 (Phantom Climate Physics):** Wire `temperature_anomaly` into `agriculture.py` so that heat shocks reduce crop yields.
  - `[ ]` **Fix #4 (Twin SOC Paradox):** Move `C_soc` entirely into `agriculture.py` (Option 1). Have `pollution_ghg.py` and `phosphorus.py` read the unified stock instead of tracking their own.

- `[ ]` **Phase D: Demographics & Regionality**
  - `[ ]` **Fix #5 (Missing Mortality Link):** Update `population.py` to read `pandemic_mortality` from SEIR and dynamically subtract it from the P1-P4 demographic stocks.
  - `[ ]` **Fix #3 (Gini Matrix Mirage):** Update `population.py` and `capital.py` to consume the Gini arrays from `gini_distribution.py` to calculate starvation and inequality.
  - `[ ]` **Fix #14 (Migrations into Void):** Update `regional_trade.py` to output `migration_flows` and `regional_pop` so that `population.py` can absorb them.

- `[ ]` **Phase E: Data & Validation**
  - `[ ]` **Fix #1 (Ghost Sectors):** Add the 9 missing Phase 2 sectors (`finance.py`, `gini_distribution.py`, `seir.py`, etc.) to the `test_all_phase2_sectors_run_together()` integration test.
  - `[ ]` **Fix #13 (DataBridge Omission):** Update `ENTITY_TO_ENGINE_MAP` in `bridge.py` to include new Phase 2 variables (`C_soc`, `financial_resilience`, etc.).
  - `[ ]` **Fix #12 (Scenario Layer - Part 2):** Populate `v2_scenarios.py` with actual engine hooks now that the engine supports them.
