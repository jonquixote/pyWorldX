# pyWorldX Foundation Analysis

**Date:** 2026-04-13  
**Scope:** `pyworldx/`, `data_pipeline/`, `pyWorldX_spec_0.2.9.0.md`  
**Purpose:** Comprehensive assessment of implementation status against spec, gap identification, and structural observations.

---

## Architecture Overview

pyWorldX is a modular, unit-safe, auditable forecasting platform for long-horizon global systems modeling, built on World3-03 compatibility with extensibility for biophysical and economic adapters. The spec (v0.2.9.0) is the authoritative implementation target.

### Three-Layer Foundation

| Layer | Role | Status |
|-------|------|--------|
| **Spec** (`pyWorldX_spec_0.2.9.0.md`) | Authoritative, self-contained spec with inline formulas, explicit constants, enum definitions, and reproducible validation bounds | Complete — 1611 lines, 27 changelog items, 20 sections |
| **Engine** (`pyworldx/`) | Core engine, World3-03 sectors, calibration, ensemble, scenarios, observability | ~90 Python files across 13 directories |
| **Data Pipeline** (`data_pipeline/`) | 29 connectors, Parquet stores, transforms, quality validation, export layer | 26 test files, 285+ tests, 4600+ test lines |

---

## Implementation Status Assessment

### ✅ Core Engine — Fully Implemented

| Primitive | Implementation | Spec Section |
|-----------|---------------|--------------|
| **Integration** | RK4 default with NaN/inf guards at k1-k4 stages; Euler for debug; fixed master-clock execution | 6.1 |
| **Multi-rate scheduler** | Fixed integer sub-stepping (Resources at 4:1, WILIAM at 4:1); `resolve_substep_ratio()` with `IncompatibleTimestepError` on non-integer ratios | 5.3, 6.4 |
| **Sub-step integrator policy** | RK4 default enforced; Euler requires explicit opt-in via `preferred_substep_integrator` metadata; warning logged for stiff transitions | 6.1 |
| **Dependency graph** | Topological sort via Kahn's algorithm; DFS cycle detection; sub-stepped sectors ordered first | 6.2 |
| **Algebraic loop resolution** | Fixed-point iteration with damping; convergence diagnostics as `LoopResult`; `UndeclaredAlgebraicLoopError` for unmatched cycles | 6.3 |
| **Balance auditor** | Conservation group enforcement with expected/observed delta comparison; PASS/WARN/FAIL status | 6.5 |
| **Bootstrap** | 4-pass initialization: seed industrial_output guess → compute sub-stepped → resolve loops → compute single-rate → re-compute sub-stepped → final loop resolution | — |
| **Stochastic state** | Named RNG streams, master seed + stream seeds + draws tracking; deterministic reproducibility | 6.6 |
| **Run result** | Structured output with time index, trajectories, observables, trace refs, balance audits, warnings, provenance manifest | 6.7 |

### ✅ World3-03 Sectors — Fully Implemented

| Sector | File | Key Features |
|--------|------|-------------|
| **Population** | `sectors/population.py` | 4-cohort (P1-P4), 15 table functions with exact W3-03 values, DLINF3 as 1st-order smooth approximation (documented) |
| **Capital** | `sectors/capital.py` | Industrial + service capital, Phase D labor/CUF, FIOAA/FIOAS/FIOAC/FIOAI allocation chain, dynamic ISOPC table, `capital_pollution_loop` hint |
| **Agriculture** | `sectors/agriculture.py` | Arable land + land fertility, SMOOTH2 cascade (AI_S1/AI_S2), dynamic IFPC, LYMC 26-point table, LYMAP air pollution effects |
| **Resources** | `sectors/resources.py` | Non-renewable stock, sub-stepped at 4:1 (`timestep_hint=0.25`), FCAOR1/FCAOR2 switching, `nonrenewable_resource_mass` conservation group |
| **Pollution** | `sectors/pollution.py` | Persistent pollution, DELAY3 cascade (PPDL1/2/3), three-stage pipeline, AHLM absorption half-life |
| **Welfare** | `sectors/welfare.py` | Pure auxiliary (no stocks), HWI geometric mean, ecological footprint |

**Documented approximations:**
- DLINF3 delays approximated as 1st-order smooths
- Simplified LFDR chain in agriculture
- No DCPH (development cost per hectare) modeling
- No FALM (fraction of inputs to land maintenance)
- `pollution_efficiency` default seeded as 1.0 in engine bootstrap (workaround, not proper coupling)

### ✅ Extension Sectors — Fully Implemented

| Sector | Description |
|--------|-------------|
| **Adaptive Technology** | Unified technology index (pyWorldX extension), single TECH stock, pressure-driven R&D investment, inert before POLICY_YEAR, `EXPERIMENTAL` status |
| **WILIAM Economy** | Sub-stepped Cobb-Douglas economy, computed `timestep_hint = master_dt / config.substep_ratio`, military allocation drag, `EXPERIMENTAL` status |
| **R-I-P Test World** | Canonical test world from spec Section 17.1, exact parameters, Resource at 4:1, I<->P algebraic loop, analytical sub-case support |

### ✅ Calibration Layer — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **Parameter registry** | 15 parameters across 5 sectors (population: 3, capital: 4, agriculture: 4, resources: 2, pollution: 3) with bounds, rationale, empirical anchors, identifiability risk flags |
| **NRMSD metrics** | `nrmsd_direct` (mean-normalized RMSD), `nrmsd_change_rate` (annual pct change transform), `weighted_nrmsd` — all matching Nebel et al. 2023 formulation |
| **Nebel 2023 bounds** | Hardcoded bounds for 8 variables, total NRMSD ≤ 0.2719 |
| **Cross-validation config** | `CrossValidationConfig` with default (train_end=2010) and `NEBEL_2023_CALIBRATION_CONFIG` (train_end=2020) |
| **Profile likelihood** | Grid-based identifiability screening: "identifiable", "flat_plateau", "threshold_gated" classifications |
| **Morris screening** | Full OAT design with configurable trajectories, levels, seed; mu_star and sigma ranking |
| **Sobol analysis** | Saltelli sampling, Jansen estimator, S1/ST indices with bootstrap CI |
| **4-step pipeline** | Profile pre-screen → Morris → Nelder-Mead optimization → Sobol |
| **Empirical runner** | 3-layer stack: W3-03 reference → DataBridge pipeline → USGS cross-validation |

### ✅ Ensemble Forecasting — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **DistributionType enum** | UNIFORM, NORMAL, LOGNORMAL, TRUNCATED_NORMAL |
| **ParameterDistribution** | dist_type, params, seed_stream, mandatory uncertainty_type |
| **EnsembleSpec** | n_runs, base_scenario, parameter/exogenous/initial_condition perturbations, threshold_queries, seed |
| **run_ensemble()** | Pre-samples perturbations, runs N members, computes percentiles (mean, median, p05, p25, p75, p95, min, max), evaluates threshold queries |
| **Threshold queries** | Three ops: "below", "above", "crosses" (sign change); probability + member_count results |
| **Uncertainty decomposition** | Variance-based decomposition (currently parameter-only; other categories at 0.0) |

### ✅ Scenario Management — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **PolicyShape enum** | STEP, RAMP, PULSE, CUSTOM (callable) |
| **PolicyEvent** | target, shape, t_start, t_end, magnitude, rate, custom_fn, description |
| **Scenario** | name, description, parameter_overrides, exogenous_overrides, policy_events, tags |
| **Built-in scenarios (6)** | baseline_world3, high_resource_discovery, pollution_control_push, agricultural_efficiency_push, capital_reallocation_to_maintenance, wiliam_high_military_drag |
| **Scenario runner** | Serial + parallel (ProcessPoolExecutor), `sector_factory` callback pattern |

### ✅ Observability — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **Run manifest** | git commit, pyWorldX version, scenario/ensemble info, parameter values, connector vintages, active sectors/versions, sub-step integrators, wall-clock, hostname, Python version |
| **CausalTraceRef** | Lightweight emission during run (indices/keys only); stores variable, t, raw_value, unit, upstream_keys, state_snapshot_ref, equation_source, sector, loop_resolved |
| **CausalTrace** | Fully materialized via `ref.render(run_result)`; resolves upstream input values |
| **Snapshot ring buffer** | Configurable size (default 2), FIFO eviction, `StaleTraceRefError` on expired access |
| **TraceCollector** | Three levels: OFF, SUMMARY, FULL (emits per-variable per-step refs) |
| **Forecast reports** | JSON-serializable: final values, peaks, percentile bands, threshold results, warnings, balance audits |

### ✅ Data Pipeline — Extensively Implemented

| Layer | Status | Details |
|-------|--------|---------|
| **Connectors** | 29 assessed | 27 functional (API/download), 2 manual helpers, 1 skipped |
| **Raw store** | Functional | One Parquet per source_id, pyarrow engine |
| **Aligned store** | Functional | One Parquet per ontology entity, merge-on-write deduplication |
| **Normalizers** | 26 functions | Wide-to-long melting, column renaming, world aggregate filtering, year normalization |
| **Transforms** | 7 registered + 8 standalone | interpolate_annual, aggregate_world, unit_conversion, filter_rows, derive_per_capita, imf_weo_parse (stub), nebel_2023_parse (stub) |
| **Quality** | Functional | Coverage %, freshness (age), cross-source consistency (GCP↔PRIMAP correlation) |
| **Storage** | Functional | HTTP cache (SHA-256, 7-day TTL), SQLite metadata DB (4 tables), Parquet stores |
| **Export** | Functional | Calibration CSV with provenance headers, JSON manifest, `PipelineConnectorResult` bridge |
| **Ontology map** | 51+ source→entity mappings | Population, emissions, energy, temperature, GDP, food, land use, health, welfare, capital, resources |
| **NRMSD** | Functional | Direct, change-rate, weighted — spec Section 9.1 compliant |
| **Initial conditions** | Functional | 15 entity→sector stock mappings, year-closest extraction, documented defaults |
| **Tests** | 26 files, 285+ passing | Connectors, transforms, normalization, quality, export, NRMSD, ontology, CLI, initial conditions, e2e |

### ✅ Ontology Layer — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **OntologyRegistry** | Prevents duplicate writes, register/lookup by canonical/World3 name, sector queries, validates `declares_writes` |
| **VariableEntry** | Canonical dot-namespaced names, dimension, unit family, stock/flow/auxiliary/parameter role, aggregation semantics |
| **OntologyEntity** | 16 canonical entities (population.total, food.per_capita, capital.industrial_stock, etc.) |
| **Unit families** | 11 families with conversion tables, intra-family `convert_units()` |
| **State-dependent weights** | `register_mapping()` with `weight_fn(state, t)` returning weights summing to 1.0 |

### ✅ Adapter Layer — Fully Implemented

| Adapter | Purpose |
|---------|---------|
| **World3Adapter** | 16 World3 variable names → pyWorldX canonical entities; time-varying weight function for nonrenewable resources |
| **WiliamEconomyAdapter** | 5 WILIAM GDP variables → pyWorldX sectors; `WiliamAdapterConfig` (substep_ratio=4, price base 2015 EUR) |

### ✅ Configuration Layer — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **ModelConfig** | master_dt, t_start, t_end, integrator, tolerances, trace settings |
| **Model presets** | `world3_03` (defaults), `nebel_2024` (8 parameter overrides from Nebel et al. 2024) |

### ✅ Validation Layer — Fully Implemented

| Component | Implementation |
|-----------|---------------|
| **Regression tests** | Reference CSV loading, relative/absolute tolerance comparison, hybrid pass criterion |
| **Sector tests** | Unit consistency, nonnegative stocks, metadata completeness |
| **World3 reference validation** | Nebel 2023 bounds for 8 variables, total NRMSD check, per-variable pass/fail |

---

## Key Gaps & Risks

### Medium Severity

| Gap | Location | Impact | Root Cause |
|-----|----------|--------|------------|
| **Policy events not integrated into engine** | `scenarios/scenario.py` → `core/engine.py` | Scenarios define `PolicyEvent` records with STEP/RAMP/PULSE/CUSTOM shapes, but engine never invokes `apply()` during simulation loop; policies must be applied manually via `sector_factory` callbacks | Engine execution loop does not call `scenario.apply_policies(values, t)` at each timestep |
| **Exogenous overrides not applied** | `scenarios/scenario.py` → `core/engine.py` | `Scenario.exogenous_overrides` (time-series) stored but never injected into sector inputs during simulation | No mechanism to override sector inputs from scenario time-series during `compute()` |
| **Pyworldx data connectors are stubs** | `pyworldx/data/connectors/` | World Bank, FRED, FAOSTAT, NOAA, UN Population, etc. are metadata-only stubs returning empty series; real implementations exist in `data_pipeline/` but are not wired into pyworldx | Architectural split: `data_pipeline/` is the production data layer; `pyworldx/data/` is a thin interface layer with stubs |
| **Transform registry duplication** | `data_pipeline/transforms/chain.py` vs `data_pipeline/transforms/` standalone modules | `chain.py` has simplified inline versions of `interpolate_annual`, `aggregate_world`, etc.; standalone modules are richer but unwired into the main transform chain | Chain.py uses its own registry; standalone modules are available for direct import but not integrated |
| **`run_transform_pipeline` unused** | `data_pipeline/pipeline.py` | DAG orchestrator with topological sort, dependency validation, and 9-stage pipeline defined but never called; CLI uses `run_all_transforms` from `chain.py` instead | `pipeline.py` exists as a reference implementation; no CLI command invokes it |
| **Agriculture pollution_efficiency coupling** | `core/engine.py` bootstrap | `pollution_efficiency` default seeded as 1.0; not dynamically coupled to Pollution sector output during simulation | Engine bootstrap workaround; proper cross-sector dependency not established |

### Low Severity

| Gap | Location | Impact |
|-----|----------|--------|
| **Uncertainty decomposition simplified** | `forecasting/uncertainty.py` | Only attributes variance to parameter perturbations; scenario, exogenous_input, initial_condition all at 0.0; labeled TODO in code |
| **Trace SUMMARY level is no-op** | `observability/tracing.py` | `emit()` returns immediately without collecting anything; SUMMARY trace level provides no data |
| **SimState unused** | `core/state.py`, `core/engine.py` | Typed `SimState` container exists but engine uses raw dicts for state management |
| **Ontology duality** | `ontology/registry.py` vs `ontology/entities.py` | Two parallel entity systems: `VariableEntry` in registry.py vs `OntologyEntity` in entities.py; not unified |
| **Custom Nelder-Mead** | `calibration/pipeline.py` | Bounded implementation works but is less sophisticated than scipy's optimizer |
| **Sobol CI simplified** | `calibration/sensitivity.py` | Bootstrap confidence intervals use simplified resampling, not full bootstrap |
| **No YAML/JSON config loading** | `config/` | Config is dataclass-only; no unified config serialization/deserialization |

---

## Structural Observations

### Strengths

1. **Spec compliance is high** — Every docstring references corresponding spec sections; enums (`DistributionType`, `PolicyShape`, `EquationSource`, `ValidationStatus`, `WORLD7Alignment`) match spec exactly; no magic strings
2. **Protocol-based contracts** — `BaseSector` uses `@runtime_checkable Protocol` for duck-typed interface enforcement; `BaseAdapter` Protocol with explicit error types
3. **Dataclass immutability** — Frozen dataclasses throughout: `Quantity`, `SimState`, `LoopResult`, `BalanceAuditResult`, `StochasticState`, `PolicyEvent`, `Scenario`, `EnsembleSpec`, `RunManifest`
4. **Re-export modules** — Clean file organization matching spec layout: `sensitivity.py` → `morris.py`/`sobol.py`/`profile_likelihood.py`; `provenance.py`, `trace.py`, `builtin.py` are thin re-exports
5. **Data pipeline is production-ready** — Collect → normalize → align → export flow is functional and tested; 27 working connectors with real API calls and file downloads
6. **Provenance discipline** — HTTP cache with SHA-256 hashing, SQLite metadata DB with 4 tables, connector vintages, transform logs, quality reports
7. **Test coverage** — 285+ tests spanning connectors, transforms, normalization, quality, export, NRMSD, ontology mappings, CLI commands, initial conditions, and e2e integration
8. **Self-contained spec** — Every formula defined inline, every constant explicit, every type an Enum, every validation bound reproducible

### Architectural Tensions

1. **Two data layers** — `pyworldx/data/connectors/` has stubs while `data_pipeline/` has real implementations. The `DataBridge` and `PipelineConnectorResult` provide a bridge, but the integration is indirect and requires the external `data_pipeline.storage.parquet_store` module
2. **Policy application gap** — Scenarios define interventions but engine doesn't execute them; requires manual `sector_factory` handling that bypasses the typed `PolicyEvent.apply()` contract
3. **Transform chain vs DAG** — The DAG in `pipeline.py` (with topological sort and dependency validation) is never called; the simpler chain in `chain.py` (with inline transforms) is used instead
4. **Calibration engine factory** — `EmpiricalCalibrationRunner` requires caller to provide `engine_factory` callback with trajectory generation logic; not a standalone calibration tool
5. **Custom optimizer** — Bounded Nelder-Mead works but lacks scipy's sophisticated termination criteria, Hessian estimation, and constraint handling

---

## Validation Readiness

The project is **close to spec-complete**. The following items need attention before the 0.2.9 release gate checklist (Section 20.1) is fully satisfied:

### Required Before Release

- [ ] **Policy event integration** — Wire `scenario.apply_policies()` into engine execution loop at each timestep
- [ ] **Exogenous override application** — Inject `exogenous_overrides` time-series into sector inputs during `compute()`
- [ ] **Connector consolidation** — Clarify boundary between `data_pipeline/` (production) and `pyworldx/data/` (interface); either wire real connectors into pyworldx or formalize the stub layer
- [ ] **Historical validation** — Execute World3-03 validation with `NEBEL_2023_CALIBRATION_CONFIG` and verify NRMSD ≤ 0.2719
- [ ] **Canonical test world** — Execute R-I-P model against PySD reference trajectory with `PySD==3.14.0` and verify max relative error < 1e-4
- [ ] **Analytical sub-case** — Verify hybrid pass criterion (relative < 1e-4 for t≤100, absolute < 1e-6 for t>100)
- [ ] **Profile likelihood screen** — Run for all `IDENTIFIABILITY_RISK` parameters and record in provenance
- [ ] **CI validation harness** — Pin regression fixtures, enforce tolerance bounds, prevent silent relaxation

### Already Satisfied

- [x] Core engine with RK4, multi-rate, loop resolution, balance audit
- [x] World3-03 sectors with table functions and documented approximations
- [x] WILIAM adapter with computed `timestep_hint` and `resolve_substep_ratio()` validation
- [x] Calibration metrics with mean-normalized `nrmsd_direct` and annual-pct-change `nrmsd_change_rate`
- [x] `NEBEL_2023_CALIBRATION_CONFIG` exported from calibration config
- [x] `PolicyShape` enum — no raw string literals in `PolicyEvent.shape`
- [x] `DistributionType` enum — no raw string literals in `ParameterDistribution.dist_type`
- [x] `CausalTraceRef`/`CausalTrace` two-type pattern
- [x] Ring buffer contract with `StaleTraceRefError`
- [x] Sub-step integrator defaults to RK4; Euler requires explicit opt-in
- [x] Provenance manifest emitted for every run
- [x] 29 data connectors assessed; 27 functional

---

## Recommendation

The foundations are solid. The spec is self-contained and reproducible. The core engine and sectors are production-quality. The data pipeline is extensive and functional. **The gaps are primarily in integration points** (policy application, exogenous overrides, connector wiring) rather than core logic.

**Priority order for remediation:**

1. **Policy event integration** — Highest impact; scenarios are unusable without it
2. **Exogenous override application** — Required for scenario realism
3. **Connector consolidation** — Clarify or resolve the dual-layer architecture
4. **Historical validation** — Prove NRMSD compliance with Nebel 2023 bounds
5. **Canonical test world** — Verify engine correctness against PySD reference
