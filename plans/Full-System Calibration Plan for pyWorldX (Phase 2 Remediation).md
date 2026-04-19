# Full-System Calibration Plan for pyWorldX (Phase 2 Remediation)

## Overview

This report proposes a concrete, end-to-end calibration strategy for the `phase-2-remediation` branch of pyWorldX, leveraging its existing calibration pipeline, DataBridge, and 37-connector data pipeline. The plan is designed for iterative implementation and focuses on obtaining a physically plausible, empirically anchored global trajectory that remains robust under cross-validation.

Key updates in this revision incorporate findings from the Pre-Flight Data Audit (`preflight_audit.md`) and the DataBridge Integration Review, including hard blockers around unit mismatches, circular calibration risks, multi-source arbitration failures, and `initial_conditions.py` default year errors. **All Tier 1 blockers from the preflight plan must be resolved before Phase 1 begins.**

---

## Current Capabilities and Gaps

The calibration stack is already well-structured:

- A `ParameterRegistry` defines free parameters with defaults, bounds, units, empirical anchors, and identifiability risk flags.
- The `run_calibration_pipeline` function implements a multi-stage workflow: profile likelihood, Morris screening, Bayesian global search (Optuna), Nelder-Mead, and Sobol variance decomposition.
- `EmpiricalCalibrationRunner` ties the DataBridge to the pipeline and supports train/validation NRMSD splits via `CrossValidationConfig`.

Remaining gaps — now explicitly catalogued in the preflight audit — are:

1. **Four hard unit/mapping blockers** in `map.py` and `initial_conditions.py` that will produce numerically nonsensical NRMSD scores.
2. **No continuous observed nonrenewable resource stock series** — the `World3ReferenceConnector` creates a circular calibration loop if used as a primary target.
3. **Multi-source fan-in conflicts** for SC, IC, and AL with no arbitration logic.
4. **Missing transform functions** (`imf_weo_parse`, `nebel_2023_parse`) that will raise `KeyError` at runtime.
5. **CEDS non-CO₂ species** (NOx, BC, OC, CO, NH₃, NMVOC) not collapsed to global rows.

---

## Phase 0: Pre-Calibration Physics and Units Fixes

Before any calibration, the engine must not contain structural imbalances that force parameters to compensate for bugs. **All four Tier 1 blockers from `2026-04-18-preflight-plan.md` must be resolved and committed before proceeding to Phase 1.**

### 0.1 Carbon Cycle Equilibrium Fix

The 5-stock carbon model in `pollution_ghg.py` initializes atmospheric, land, soil, and ocean stocks and defines NPP and respiration fluxes. At present, pre-industrial NPP (60 GtC/yr) exceeds the combined plant respiration and litter flux (39 GtC/yr), causing an unphysical drawdown of atmospheric carbon even in 1900.

**Action:**
- Adjust `_K_RESP_PLANT` and `_K_LITTER` so that at `C_land = 600 GtC`, `NPP0 = 60` equals `(k_resp_plant + k_litter) × 600`.
- A symmetric choice `k_resp_plant = k_litter = 0.05` satisfies this equilibrium while preserving the existing soil respiration structure.

This stops the 1900–1940 atmospheric carbon dip and yields a stable pre-industrial baseline against which anthropogenic emissions act.

### 0.2 Food Per Capita Unit Conversion

The agriculture sector expresses food per capita in World3's canonical `veg_equiv_kg/person/yr`
units. The FAOSTAT pipeline emits `kcal/capita/day`. These two series are merged under the same
entity with no conversion, producing a ~1,000× magnitude mismatch that will corrupt the
agriculture-sector NRMSD.

**Action:**
- **Recommended (short-term):** Keep the two series as separate entities and let
  `DataBridge._normalize_to_index()` handle alignment. Both series index to `1.0 ± 0.10` at 1970.
  This is the safer approach — a single kcal/kg scalar is ambiguous across crop types (cereal
  ≈ 1,800 kcal/kg, legumes ≈ 3,400 kcal/kg), making any merged conversion brittle.
- If a merged series is required in future, the correct conversion factor is:
  `1 kg/yr = 1800 / 365 ≈ 4.93 kcal/day`, so `1 kcal/day ≈ 0.203 kg/yr`.
  Apply as a `ConversionStep` dataclass before merging.
- In the display/reporting layer, convert internal `fpc` (kg/person/yr) to kcal/person/day via
  `kcal/day = kg/yr × (1800 / 365) ≈ kg/yr × 4.93`. Ensure threshold queries use this converted
  series, not the raw kg/person/yr value.

### 0.3 Pollution Index / CO₂ Unit Separation (NEW — Preflight Blocker T1-1)

`world3_reference_pollution_index` (dimensionless, ~1.0 at 1970) is currently mapped to the same `CalibrationTarget` entity as `atmospheric.co2` (ppm, ~325 at 1970). This is a category error — dividing a dimensionless index by a ppm value produces a ratio of ~0.003 instead of 1.0.

**Action:**
- Separate into two distinct entities: `pollution_index_relative` (World3 reference, maps to engine `PPOLX`) and `atmospheric_co2_ppm` (NOAA Keeling Curve / GCP).
- Tag `atmospheric_co2_ppm` as `unit_mismatch=True` and exclude from the default objective until a ppm→index conversion factor is implemented.
- `world3_reference_pollution_index` must be namespaced to `world3.pollution_index` and excluded from the empirical `ENTITY_TO_ENGINE_MAP`.

### 0.4 Retire All World3 Reference → Real-Entity Collisions (NEW — Preflight Blocker)

Four `world3_reference_*` mappings in `map.py` collide with real-data entities:

| Colliding Mapping | Correct Action |
|---|---|
| `world3_reference_pollution_index` → `atmospheric.co2` | Retire; see §0.3 |
| `world3_reference_food_per_capita` → `food_per_capita` | Namespace to `world3.food_per_capita` |
| `world3_reference_industrial_output` → `gdp.current_usd` | Namespace to `world3.industrial_output` |
| `world3_reference_nonrenewable_resources` → `NR` target | Namespace to `world3.nr_fraction`; exclude from objective |

All World3 reference trajectories must be namespaced under `world3.*` and treated as **Layer 0 structural references**, never as empirical calibration targets in `ENTITY_TO_ENGINE_MAP`.

---

## Phase 1: Data Pipeline and DataBridge Readiness

Calibration depends on real-world trajectories being available and correctly mapped into engine variables. The following steps must follow completion of all Tier 1 and Tier 2 items in `2026-04-18-preflight-plan.md`.

### 1.1 Ensure Aligned Parquet Store is Populated

**Action:**
- Run the full data pipeline locally:
  - `poetry install --extras pipeline`
  - `poetry run python -m data_pipeline collect`
  - `poetry run python -m data_pipeline run`
- Confirm `data_pipeline/data/aligned/` contains expected per-entity Parquet outputs.
- Run Gate 3 coverage report: `python -m pyworldx.data.bridge --report-coverage --aligned-dir ./output/aligned`
- Any entity with `base_year_nonzero=False` is a blocker — resolve before proceeding.

### 1.2 Fix FAOSTAT World Code (Preflight Blocker T1-3)

Change `world_country_code="WLD"` → `"5000"` in `faostat_food_balance_historical`. Add post-fetch assertion. Re-run the connector to regenerate the Parquet cache. See `2026-04-18-preflight-plan.md` §T1-3 for full specification.

### 1.3 Nominate Single Authoritative Source Per Stock

The preflight audit identifies SC, IC, and AL as having multi-source fan-in with no arbitration. Before any calibration run:

- Add `source_priority` lists to each multi-source entity in `ENTITY_TO_ENGINE_MAP`.
- Implement priority-waterfall in `DataBridge.load_targets()`: use highest-priority source where non-null, fall back in order.
- Log the selected source for each entity and year range to the calibration report.

Authoritative sources (recommended):

| Stock | Authoritative Source | Unit |
|---|---|---|
| SC | Penn World Tables `rgdpe` per capita | constant 2017 USD PPP |
| IC | Penn World Tables `rnna` world-summed | constant 2017 USD |
| AL | FAOSTAT RL `arable_land` | 1000 ha (×1000 to reach ha) |

### 1.4 Harden DataBridge Error Handling

- `DataBridge.load_targets()` must raise `DataBridgeError` when `aligned_dir` is absent, with a message instructing the user to run the pipeline.
- Add Parquet cache staleness check: if cache is missing or older than `cache_ttl`, emit `logger.warning` with the connector refresh command.
- Add zero-guard to `_normalize_to_index()` per preflight §T2-3 specification.
- `EmpiricalCalibrationRunner` must accept a `scenario: str = "standard_run"` argument and validate it against registered scenarios (see Open Decision #1).

### 1.5 Verify Transform Functions Exist

- Grep for `imf_weo_parse` and `nebel_2023_parse` in the transform registry.
- If absent, add stubs raising `NotImplementedError` with clear messages.
- Add `aggregate_world` step to all CEDS non-CO₂ species connectors (NOx, BC, OC, CO, NH₃, NMVOC).

### 1.6 Add BP Statistical Review Connector for NR

The only real-world anchor for the resource sector. See preflight §T2-2:

- Add `BPStatisticalReviewConnector` fetching proved reserves time-series (oil + gas + coal, EJ) from the OWID/BP mirror.
- Map to `nonrenewable_resources_proved_reserves` with `unit="EJ"`, tagged `layer=1`.
- Add conversion to World3 NR resource units calibrated against the 1970 World3-03 NR initial value (~1.0 × 10¹²).
- Acceptance: series covers at least 1965–2023 with no more than 3 consecutive missing years.

---

## Phase 2: Sector-by-Sector Calibration Strategy

A global NRMSD objective over all free parameters is likely to be rugged and poorly conditioned. A block-decomposed strategy is recommended, calibrating sectors sequentially against their primary observables.

**Baseline normalization:** All series are normalized to `X(t) / X(train_start)` where `train_start = CrossValidationConfig.train_start` (1970). All indices equal 1.0 at the start of the calibration window. `initial_conditions.py` default is `target_year=1970` (fixed per preflight T1-4). Do **not** hardcode `1970` as a literal integer anywhere — always reference `CrossValidationConfig.train_start`.

### 2.1 Population Sector

**Targets:** UN WPP world population 1950–2023 (`population.total`, unit: persons — apply `×1000` scale to FAOSTAT 1000_persons sources).

**Parameters:** `population.cbr_base`, `population.cdr_base`, `population.initial_population` (fixed).

**Objective:** NRMSD on train window 1970–2010; validate 2010–2023.

**Steps:**
1. Configure `CrossValidationConfig(train_start=1970, train_end=2010, validation_end=2023)`.
2. Restrict `ParameterRegistry` to population parameters for this stage.
3. Profile likelihood → Morris screening → Optuna (50 trials) → Nelder-Mead.
4. Evaluate train vs. validation NRMSD; adjust bounds if `overfit_flagged=True`.

### 2.2 Capital Sector

**Targets:** PWT `rnna` world-summed for IC; PWT `rgdpe` per capita for SC. Both in constant 2017 USD (deflator step required to reconcile PWT 2017 with UNIDO/WB 2015 base — see preflight §3.2).

**Parameters:** `capital.initial_ic`, `capital.icor`, `capital.alic`, `capital.alsc`.

**Steps:**
1. Freeze population parameters at calibrated values from §2.1.
2. Nominate PWT as authoritative per §1.3 priority table; demote World Bank NV.SRV to cross-validation.
3. Profile → Morris → Optuna → Nelder-Mead on capital parameters.

### 2.3 Agriculture Sector

**Targets:** FAOSTAT FBS `food_supply_kcal_per_capita` (1961–2023); FAOSTAT RL `arable_land` (1961–2023, ×1000 to hectares). FBSH world code must be `5000` (preflight T1-3).

**Parameters:** `agriculture.initial_al`, `agriculture.initial_land_fertility`, `agriculture.land_development_rate`, `agriculture.sfpc`.

**Steps:**
1. Use calibrated population and capital; treat resources as defaults.
2. Calibrate to match timing and magnitude of post-1950 Green Revolution.
3. Verify converted `fpc` series sits in 2500–3200 kcal/day band during 1980–2020.

### 2.4 Resources Sector

**Targets:** BP Statistical Review proved reserves index (Layer 1, new connector §1.6); USGS extraction index and depletion ratio (Layer 2, existing proxy).

**Parameters:** `resources.initial_nr`, `resources.policy_year`.

**Objective:** `nrmsd_method="change_rate"` for trajectories dominated by slopes rather than levels. Do **not** use `world3_reference_nonrenewable_resources` as a calibration target (circular — see §0.4).

**Steps:**
1. With population, capital, and agriculture calibrated, align the timing of peak fossil extraction with BP reserve data.
2. Use USGS depletion ratio as a secondary cross-validation check, not as a primary objective signal.

### 2.5 Pollution and Climate Sectors

**Targets:** NOAA annual CO₂ (`atmospheric_co2_ppm`, 1958–2024); GCP fossil CO₂ emissions (`emissions.co2_fossil`, Mt CO₂); CEDS SO₂ as a flow-rate proxy for persistent pollution (explicitly **not** a stock proxy — see preflight §1.1).

**Parameters:** `pollution.initial_ppol`, `pollution.ahl70`, `pollution.pptd` (anchored to Nebel 2024).

**Key constraint:** `atmospheric_co2_ppm` is an empirical entity in ppm — it must **not** be merged with `world3.pollution_index` (dimensionless). The engine's `PPOLX` variable maps only to `pollution_index_relative`. CO₂ calibration operates as an independent check on the carbon cycle, not a direct PPOLX target.

**Steps:**
1. With energy usage and industrial output calibrated, adjust pollution parameters so the engine's CO₂ trajectory matches NOAA data from 1958 onward.
2. Verify radiative forcing from engine atmospheric carbon matches external forcing series.
3. Confirm CEDS non-CO₂ species are collapsed to global rows before ingestion (preflight §1.5).

---

## Phase 3: Joint Multi-Sector Fine Tuning

After sector-level calibration, a controlled joint optimization refines the most influential cross-sector parameters.

### 3.1 Identify Influential Parameters

- From each sector's Sobol output, extract top 1–2 parameters per observable.
- Build a reduced joint parameter set of 5–6 parameters that consistently rank high across sectors.

### 3.2 Define Composite NRMSD Objective

Using `DataBridge`, construct a composite objective combining normalized NRMSD across all key observables:

- Train window: 1970–2010 for all series (use `CrossValidationConfig.train_start`, not literal `1970`).
- Standardized weights so each observable contributes comparably.
- Recommended initial weights: population ×1.5, CO₂ ×1.5, food per capita ×1.0, IC ×1.0, resources ×0.75 (lower confidence due to proxy quality).

### 3.3 Run Joint Optuna + Nelder-Mead

- Limit `parameter_names` to the joint influential set (5–6 parameters).
- `bayesian_n_trials=50–100`.
- Assert `validation_nrmsd` is computed **independently** from `train_nrmsd` (separate DataBridge call, holdout window 2010–2023).
- Assert `overfit_flagged` triggers only when gap exceeds `CrossValidationConfig.overfit_threshold`, not as a hard failure for any `validation_nrmsd > train_nrmsd` (mild degradation is expected and healthy).

---

## Phase 4: Robustness, Ensembles, and Scenario Testing

### 4.1 Monte Carlo Ensemble with Saltelli Sampling

- Run ensemble using calibrated parameter set as mean; uncertainty bounds from `ParameterEntry.bounds`.
- Threshold queries (e.g., food per capita < 2500 kcal/day by 2050) must use the converted kcal/day series.
- Sobol decomposition must attribute variance correctly to parameter vs. exogenous vs. initial conditions classes.

### 4.2 Scenario Stress Tests

- `EmpiricalCalibrationRunner` accepts `scenario` argument (default `"standard_run"`); validate against engine's registered scenario list.
- For scenarios such as `Historical Emissions Policy`, run a limited ensemble and confirm calibrated parameters produce qualitatively plausible deviations from the baseline.
- Calibration must not bake in policy assumptions — `Standard Run` is the primary calibration target; policy scenarios are validation-only.

---

## Phase 5: Documentation and Regression Protection

### 5.1 Calibration Snapshots and NRMSD Baselines

- After each major phase, record calibrated parameter set and NRMSD scores (train + validation) in a machine-readable manifest.
- Add regression tests: run `EmpiricalCalibrationRunner.quick_evaluate` with the baseline parameter set; assert composite NRMSD remains below threshold or within tolerance band.

### 5.2 Narrative Documentation

Extend `docs/calibration.md` to describe:
- Block-decomposition strategy and sector sequencing rationale.
- Key data sources, their pipeline connectors, and entity-to-engine mappings.
- Source priority table for multi-source entities.
- Known limitations: NR sector relies on proved reserves proxy (not physical stock); `PPOLX` has no direct empirical observable; pre-1961 agriculture data uses Gapminder estimates.
- The `World3ReferenceConnector` scope: Layer 0 structural reference only, never an empirical calibration target.

### 5.3 plans/implementation_audit_report.md Update

After all Tier 1 + Tier 2 items are resolved, update `plans/implementation_audit_report.md` with resolved status for each preflight finding. PR description must reference `plans/2026-04-18-preflight-plan.md`.

---

## Implementation Ordering Summary

| Step | Action | Prerequisite |
|---|---|---|
| 0 | Fix carbon equilibrium, fpc unit collision, retire World3→real collisions, fix FAOSTAT world code, fix `initial_conditions.py` default year | None |
| 1 | Populate aligned Parquet store; add BP reserves connector; harden DataBridge; verify transforms; nominate authoritative sources | All Tier 1 + Tier 2 preflight items resolved |
| 2 | Calibrate sectors sequentially: population → capital → agriculture → resources → pollution | Phase 1 complete; all 5 preflight Gates pass |
| 3 | Identify influential parameters; run joint Optuna + Nelder-Mead with composite NRMSD | Phase 2 complete |
| 4 | Run ensembles and scenario tests | Phase 3 complete |
| 5 | Capture NRMSD baselines; add regression tests; write `docs/calibration.md`; update audit report | Phase 4 complete |

Following this plan will move pyWorldX from a structurally sophisticated but under-calibrated system to a fully empirical, cross-validated global model that is robust under uncertainty and explicit about its assumptions.