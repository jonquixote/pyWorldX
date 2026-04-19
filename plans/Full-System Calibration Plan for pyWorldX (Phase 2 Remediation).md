# Full-System Calibration Plan for pyWorldX (Phase 2 Remediation)

## Overview

This report proposes a concrete, end-to-end calibration strategy for the `phase-2-remediation` branch of pyWorldX, leveraging its existing calibration pipeline, DataBridge, and 37-connector data pipeline. The plan is designed for iterative implementation and focuses on obtaining a physically plausible, empirically anchored global trajectory that remains robust under cross-validation.

## Current Capabilities and Gaps

The calibration stack is already well-structured:

- A `ParameterRegistry` defines free parameters with defaults, bounds, units, empirical anchors, and identifiability risk flags.
- The `run_calibration_pipeline` function implements a multi-stage workflow: profile likelihood, Morris screening, Bayesian global search (Optuna), Nelder-Mead, and Sobol variance decomposition.
- `EmpiricalCalibrationRunner` ties the DataBridge to the pipeline and supports train/validation NRMSD splits via `CrossValidationConfig`.

Remaining gaps are primarily in: (1) a small number of physics/units inconsistencies, and (2) the absence of a systematic sector-by-sector empirical calibration sequence using real Parquet outputs from the data pipeline.

## Phase 0: Pre-Calibration Physics and Units Fixes

Before any calibration, the engine must not contain structural imbalances that force parameters to compensate for bugs.

### 0.1 Carbon Cycle Equilibrium Fix

The 5-stock carbon model in `pollution_ghg.py` initializes atmospheric, land, soil, and ocean stocks and defines NPP and respiration fluxes. At present, pre-industrial NPP (60 GtC/yr) exceeds the combined plant respiration and litter flux (39 GtC/yr), causing an unphysical drawdown of atmospheric carbon even in 1900.

**Action:**
- Adjust `_K_RESP_PLANT` and `_K_LITTER` so that at `C_land = 600 GtC`, `NPP0 = 60` equals `(k_resp_plant + k_litter) × 600`.
- A symmetric choice `k_resp_plant = k_litter = 0.05` satisfies this equilibrium while preserving the existing soil respiration structure.

This stops the 1900–1940 atmospheric carbon dip and yields a stable pre-industrial baseline against which anthropogenic emissions act.

### 0.2 Food Per Capita Unit Conversion

The agriculture sector expresses food per capita in World3’s canonical `veg_equiv_kg/person/yr` units. Threshold queries and reporting, however, are expressed in kcal/day terms (e.g., “< 2500 kcal by 2050”). Without a conversion layer, users see values around 220–250 and may misinterpret them as kcal/day, suggesting catastrophic starvation.

**Action:**
- Implement a display-layer conversion in the reporting or forecasting layer:
  - Convert internal `fpc` from kg/person/yr to kcal/person/day via a factor 
  \(\text{kcal/day} = \text{kg/yr} × 3500 / 365\) (≈ 9.589).
- Ensure threshold queries comparing against kcal/day values either:
  - Use the converted kcal/day series, or
  - Convert user thresholds down to kg/person/yr using the inverse factor.

This preserves internal W3-compliant units while making all analytics and threshold results physically interpretable.

## Phase 1: Data Pipeline and DataBridge Readiness

Calibration depends on real-world trajectories being available and correctly mapped into engine variables.

### 1.1 Ensure Aligned Parquet Store is Populated

The data pipeline is designed to collect, transform, align, and export NRMSD-ready calibration series from 37 sources. The `EmpiricalCalibrationRunner` expects its `aligned_dir` to be a populated directory containing these aligned Parquet files.

**Action:**
- Run the full data pipeline locally:
  - `poetry install --extras pipeline`
  - `poetry run python -m data_pipeline collect`
  - `poetry run python -m data_pipeline run`
- Confirm that `data_pipeline/data/aligned/` (or configured equivalent) exists and contains the expected per-entity Parquet outputs.

### 1.2 Harden DataBridge Error Handling

`DataBridge` now exposes `load_targets` and related utilities, used by `EmpiricalCalibrationRunner` to construct `CalibrationTarget` objects from the aligned store. Robust calibration requires clear feedback when the aligned store is missing or malformed.

**Action:**
- Ensure `DataBridge.load_targets` raises a dedicated `DataBridgeError` when `aligned_dir` is absent, with a clear message instructing the user to run the pipeline first.
- Confirm that `_clip_targets_to_window` and `build_objective` correctly enforce train-window clipping as configured in `CrossValidationConfig`.

This guarantees that calibration runs fail fast and descriptively when empirical data is unavailable.

## Phase 2: Sector-by-Sector Calibration Strategy

A global NRMSD objective over all free parameters is likely to be rugged and poorly conditioned. Instead, a block-decomposed strategy is recommended, where sectors are calibrated sequentially against their primary observables.

### 2.1 Population Sector

**Targets:** Historical world population 1900–2023 (from UN WPP or similar), already ingested via the pipeline into an aligned `population` entity.

**Parameters:**
- `population.cbr_base` (baseline crude birth rate)
- `population.cdr_base` (baseline crude death rate)
- `population.initial_population` (initial stock, likely fixed for calibration)

**Objective:** NRMSD between engine population trajectory and empirical population over a train window (e.g., 1900–2010), with validation on 2010–2023.

**Steps:**
1. Configure `CrossValidationConfig` with train and validation windows appropriate for population (e.g., train_start=1900, train_end=2010, validate_start=2010, validate_end=2023).
2. Restrict the `ParameterRegistry` to population parameters for this stage (either via a separate registry or by marking other sectors as fixed).
3. Use the existing pipeline:
   - Profile likelihood on `population.cbr_base` and `population.cdr_base` to check identifiability.
   - Run Morris screening, then Bayesian + Nelder-Mead over these 2 parameters.
4. Evaluate train vs validation NRMSD and adjust bounds if necessary.

### 2.2 Capital Sector

**Targets:** World industrial output or GDP/Sector index series, e.g., from Maddison Project or World Bank, aligned into the `capital`/`industrial_output` entity.

**Parameters:**
- `capital.initial_ic` (initial industrial capital)
- `capital.icor` (incremental capital-output ratio)
- `capital.alic` and `capital.alsc` (lifetimes of industrial and social capital)

**Objective:** NRMSD between engine industrial output and empirical GDP index, using a similar train/validate split.

**Steps:**
1. Freeze population parameters at their calibrated values from 2.1.
2. Focus calibration on the capital parameters while treating agriculture and resources as fixed at defaults.
3. Use the same pipeline (profile → Morris → Bayesian → Nelder-Mead) on capital-sector parameters.

### 2.3 Agriculture Sector

**Targets:** Food per capita or crop yield per person from FAO or similar, mapped to `agriculture` entities in the aligned store.

**Parameters:**
- `agriculture.initial_al` (initial arable land)
- `agriculture.initial_land_fertility`
- `agriculture.land_development_rate`
- `agriculture.sfpc` (subsistence food per capita)

**Objective:** NRMSD between engine food per capita (converted to kcal/day at the reporting layer) and empirical per-capita food availability.

**Steps:**
1. Use calibrated population and capital parameters; treat energy and resources as defaults.
2. Calibrate agriculture parameters to match the timing and magnitude of the post-1950 Green Revolution.
3. Confirm that the food-per-capita series, once converted, sits in the expected 2500–3200 kcal/day band during the late 20th and early 21st century.

### 2.4 Resources Sector

**Targets:** Fossil extraction and reserve depletion proxies based on USGS data (already used in `EmpiricalCalibrationRunner.load_usgs_targets`).

**Parameters:**
- `resources.initial_nr` (initial nonrenewable resource stock)
- `resources.policy_year` (activation year for resource policy, if still free)

**Objective:** NRMSD between engine resource extraction/output and the USGS-derived extraction index and reserve depletion ratio, using the `nrmsd_method="change_rate"` for trajectories dominated by slopes rather than levels.

**Steps:**
1. With population, capital, and agriculture calibrated, adjust resource parameters to align the timing of peak fossil extraction and depletion with empirical data.
2. Use the Layer 3 USGS cross-validation in `EmpiricalCalibrationRunner` as an explicit calibration step, not just a post-hoc check.

### 2.5 Pollution and Climate Sectors

**Targets:**
- Persistent pollution trajectories (if empirical proxies exist)
- Atmospheric CO₂ concentration and radiative forcing series from NOAA and GCB, aligned via the pipeline.

**Parameters:**
- `pollution.initial_ppol`
- `pollution.ahl70` (absorption half-life in 1970)
- `pollution.pptd` (toxic pollution persistence, already anchored to Nebel 2024)

**Objective:** Jointly minimize NRMSD for CO₂ concentration, radiative forcing, and persistent pollution proxies, ensuring mass conservation (as enforced by the carbon model’s conservation group metadata).

**Steps:**
1. With energy usage and industrial output calibrated, adjust pollution parameters so that the engine’s CO₂ trajectory matches observed data from 1958 onward.
2. Confirm that radiative forcing calculated from the engine’s atmospheric carbon matches external radiative forcing series.

## Phase 3: Joint Multi-Sector Fine Tuning

After sector-level calibration, the system is close to plausible but may still have cross-sector mismatches. A controlled joint optimization then refines a subset of the most influential parameters.

### 3.1 Identify Influential Parameters Across Sectors

The Sobol analysis in `run_calibration_pipeline` computes first-order and total-order sensitivity indices for the screened parameter set.

**Action:**
- For each sector’s calibrated run, capture the Sobol results and identify the top 1–2 parameters per observable (population, GDP, food per capita, CO₂, etc.).
- Build a reduced joint parameter set of 5–6 parameters that consistently appear as high-influence.

### 3.2 Define Composite NRMSD Objective

Using the DataBridge, construct a composite objective that combines normalized NRMSD across all key observables, with explicit weights reflecting model priorities (e.g., higher weight on population and CO₂, moderate on pollution proxies).

**Action:**
- Implement a composite objective that:
  - Uses train window 1970–2010 for all series when computing NRMSD.
  - Uses standardized weights so that each observable contributes comparably.

### 3.3 Run Joint Optuna + Nelder-Mead

With the reduced parameter set and composite objective:

- Run `run_calibration_pipeline` with:
  - `parameter_names` limited to the joint influential set.
  - A moderate `bayesian_n_trials` (e.g., 50–100) to avoid excessive compute.
- Inspect train vs validation NRMSD and ensure `overfit_flagged` remains false.

## Phase 4: Robustness, Ensembles, and Scenario Testing

Calibration is not complete until robustness under uncertainty and scenario perturbations is understood.

### 4.1 Monte Carlo Ensemble with Saltelli Sampling

The forecasting layer already supports Saltelli sampling and Sobol decomposition over parameter, exogenous, and initial condition uncertainties.

**Action:**
- Run ensemble simulations using the calibrated parameter set as the mean and uncertainty bounds derived from the `ParameterEntry.bounds` fields.
- Confirm that:
  - Threshold queries (e.g., probability of food per capita dropping below 2500 kcal/day by 2050) use the converted kcal/day series.
  - Sobol decomposition of ensemble output attributes variance correctly to parameter vs exogenous vs initial conditions classes.

### 4.2 Scenario Stress Tests

Using the scenario system, define policy scenarios (e.g., emission reductions, resource policy year shifts) and test the calibrated model under each scenario.

**Action:**
- For each scenario:
  - Run a limited ensemble.
  - Track deviations from the baseline in key indicators.
- Ensure that scenario effects are qualitatively plausible and that the calibration does not “bake in” particular policy assumptions.

## Phase 5: Documentation and Regression Protection

A calibrated system is only as robust as the tests that guard it.

### 5.1 Calibration Snapshots and NRMSD Baselines

**Action:**
- After each major phase (sector-level and joint calibration), record the calibrated parameter set and corresponding NRMSD scores (train and validation) in a machine-readable manifest.
- Add regression tests that:
  - Run `EmpiricalCalibrationRunner.quick_evaluate` with the baseline parameter set.
  - Assert that composite NRMSD remains below a threshold or within a narrow tolerance band.

### 5.2 Narrative Documentation

**Action:**
- Extend the calibration section of the README or a dedicated `docs/calibration.md` to describe:
  - The block-decomposition strategy.
  - Key data sources and their mapping into `CalibrationTarget` variables.
  - Known limitations and assumptions (e.g., reliance on W3-03 defaults where empirical anchors are weak).

This ensures future contributors understand both the calibration workflow and its rationale.

## Implementation Ordering Summary

1. Fix pre-calibration physics and units (carbon equilibrium, fpc conversion).
2. Populate aligned Parquet store; harden DataBridge error handling.
3. Calibrate sectors sequentially: population → capital → agriculture → resources → pollution.
4. Identify influential parameters and run joint multi-sector refinement.
5. Run ensembles and scenario tests to assess robustness.
6. Capture calibrated parameter sets and NRMSD baselines; add regression tests and documentation.

Following this plan will move pyWorldX from a structurally sophisticated but under-calibrated system to a fully empirical, cross-validated global model that is robust under uncertainty and explicit about its assumptions.