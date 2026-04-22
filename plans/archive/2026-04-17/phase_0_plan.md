# Phase 0 Implementation Plan — Finish v1

**Date:** 2026-04-14  
**Goal:** Close the 0.2.9 release gate checklist. Make the foundation rock-solid before building v2.  
**Duration:** 3 weeks  
**Scope:** 6 tasks, all in existing code. No new sectors. No new architectural patterns.  
**Status:** ✅ **COMPLETE** — All 6 tasks verified. Independent subagent review confirmed all tasks correct.

---

## Current State Assessment (Verified Against Actual Code)

### Test Suite: ✅ 470 passed, 0 failed, 1 skipped

- 470 tests across `tests/unit/`, `tests/integration/`, `tests/canonical/`, `tests/validation/`
- 0 failures (2 parquet-related failures resolved by installing `duckdb`)
- 1 skipped (network test)
- **Coverage note:** CLAUDE.md requires 90%+; must verify after changes

### Type Checking: ⚠️ 12 errors in 2 files

| File | Errors | Nature |
|------|--------|--------|
| `data_pipeline/connectors/usgs.py` | ~9 | `object` has no attribute — needs typed connector |
| `pyworldx/data/bridge.py` | 2 | Array type mismatch (`ExtensionArray | ndarray` vs `ndarray`) |
| `pyproject.toml` | 1 note | Unused override section for `pyworldx.data.transforms.normalization` |

The usgs errors are in data_pipeline (not pyworldx core). The bridge errors are minor type annotation fixes.

### Linting: ✅ All checks passed

`ruff check pyworldx` — clean.

### Canonical R-I-P Test: ⚠️ Passing but self-referential

- All 8 canonical integration tests pass
- **PROBLEM:** `generate_reference.py` generates reference from pyWorldX's own RK4 engine, NOT from PySD. The CSV header says: `# Engine: pyWorldX RK4 (self-consistent reference)`. This verifies pyWorldX matches pyWorldX — not independent verification.
- The spec (Section 17.3) requires PySD==3.14.0 as the independent reference generator.
- **PROBLEM:** No analytical sub-case test exists (spec requires hybrid pass criterion: relative < 1e-4 for t≤100, absolute < 1e-6 for t>100).

### World3-03 Validation: ❌ Never executed

- `validate_against_nebel2023()` exists but has never been run with actual model output.
- `World3ReferenceConnector` provides decadal data (1900-2100 step 10), but NRMSD needs annual data for 1970-2020 window.
- Variable name mismatch: NEBEL_2023_BOUNDS keys (`population`, `pollution`, `nonrenewable_resources`) don't match engine trajectory keys (`POP`, `pollution_index`, `NR`).

### Agriculture Sector: ⚠️ Simplified investment chain

- Computes TAI = IO × FIOAA correctly
- Uses SMOOTH2 cascade (AI_S1, AI_S2) on TAI directly — no FIALD split
- Land development uses heuristic `(PAL - AL) × land_dev_rate × IO_factor` instead of `TAI × FIALD / DCPH`
- Missing: FIALD table, DCPH table, FALM table, CAI state variable, MPLD/MPAI calculations
- FIOAA computed independently in BOTH capital.py and agriculture.py with same table but different inputs (capital uses static SFPC, agriculture uses dynamic IFPC) — can produce divergent values

### Policy Events: ❌ Never applied during simulation

- `Scenario.apply_policies()` works correctly but is never called by Engine.run()
- Only ONE built-in scenario has policy_events (`pollution_control_push`), and its target (`pollution.industrial_pollution_intensity`) does not exist as an engine variable
- The engine's `shared` dict uses flat keys like `"pollution_index"`, not dotted namespace like `"pollution.industrial_pollution_intensity"`

### Exogenous Overrides: ❌ Never injected

- `Scenario.exogenous_overrides` stores dict[str, pd.Series] but zero mechanism to inject during simulation
- Example keys like `"atmospheric.co2"` would need to map to engine keys like `"pollution_index"` via ENTITY_TO_ENGINE_MAP

### Connector Stubs: ❌ 9 dead files

- 9 stub connectors return empty pd.Series with metadata. Only imported by their own test file.
- `data_pipeline/` has 27 working connectors. DataBridge already works through data_pipeline aligned Parquet.

---

## Task 1: Wire Policy Events into Engine Execution

**Status:** ❌ Never applied during simulation  
**Priority:** 🔴 HIGH  
**Effort:** 2-3 days

### The Problem

The engine has no policy awareness. The `sector_factory` in `run_scenarios()` receives only `parameter_overrides` — not the full Scenario, not policy_events. Only one built-in scenario (`pollution_control_push`) has policy_events, and its target variable does not exist in the engine.

### Critical Design Fix (from audit)

**The policy hook must go BEFORE sector compute, not after.** If applied after RK4 integration, sectors have already computed with old values and won't see the policy effects until the NEXT timestep. The correct placement is at the **beginning of the master loop, before Phase 1 (sub-stepped sectors)**:

```python
for step_idx in range(steps):
    # NEW: Apply policy events BEFORE any sector compute
    if self._policy_applier is not None:
        shared_floats = {k: v.magnitude for k, v in shared.items()}
        shared_floats = self._policy_applier(shared_floats, t)
        for k, v in shared_floats.items():
            if k in shared:
                shared[k] = Quantity(v, shared[k].unit)

    # Phase 1: Sub-stepped sectors advance (will see policy-modified values)
    for s in self._sub_stepped:
        ...
```

**Variable name fix:** Built-in scenario targets use dotted namespace (`"pollution.industrial_pollution_intensity"`) that doesn't match engine keys. Two options:
- **A)** Fix the scenario targets to use flat engine names
- **B)** Add a name translation layer in `apply_policies()` that maps dotted names to flat names via a registry

**Recommendation: Option A.** The dotted namespace is an ontology convention, not an engine convention. Fix the scenario targets:
```python
# Before (wrong):
target="pollution.industrial_pollution_intensity"
# After (correct):
target="pollution_index"  # or whatever the actual engine variable is
```

### Implementation

**Files modified:**
- `pyworldx/core/engine.py` — Add `policy_applier` parameter; hook at start of master loop
- `pyworldx/scenarios/runner.py` — Create `policy_applier` from Scenario; pass to Engine
- `pyworldx/scenarios/scenario.py` — Fix `pollution_control_push` target to use flat engine variable name

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_policy_applier_none_no_change` | Engine.run() with `policy_applier=None` produces byte-identical output |
| 2 | `test_policy_applier_called_each_timestep` | Called `steps` times (once per master step) |
| 3 | `test_policy_applied_before_sector_compute` | Sectors see policy-modified values in their compute() call |
| 4 | `test_step_policy_modifies_shared` | STEP policy adds magnitude to target after t_start |
| 5 | `test_custom_policy_fn_receives_correct_args` | Custom fn receives (baseline_value, t) |
| 6 | `test_pollution_control_push_scenario` | Fixed target actually reduces pollution trajectory vs baseline |
| 7 | `test_multiple_policies_same_run` | Multiple policy events all take effect |
| 8 | `test_policy_not_applied_to_stocks` | Policies modify auxiliaries, not stock values |
| 9 | `test_policy_with_custom_fn` | CUSTOM shape works end-to-end |

### Acceptance Criteria

- [ ] Policy hook at START of master loop (before any sector compute)
- [ ] `policy_applier=None` produces byte-identical output to current behavior
- [ ] `pollution_control_push` target fixed to flat engine variable name
- [ ] All 9 tests pass
- [ ] Existing 470 tests still pass
- [ ] mypy strict passes
- [ ] ruff check passes

---

## Task 2: Wire Exogenous Overrides into Sector Inputs

**Status:** ❌ Never injected  
**Priority:** 🔴 HIGH  
**Effort:** 2-3 days

### The Problem

`exogenous_overrides` maps ontology names (`"population.total"`) to time-series. The engine's `shared` dict uses engine names (`"POP"`). The injection code must translate between the two.

### Critical Design Fix (from audit)

**Variable name translation:** The injector must use `ENTITY_TO_ENGINE_MAP` to translate ontology names to engine names before checking `shared`:

```python
if self._exogenous_injector is not None:
    overrides = self._exogenous_injector(t)  # returns {ontology_name: value}
    from pyworldx.data.bridge import ENTITY_TO_ENGINE_MAP
    for ontology_name, override_val in overrides.items():
        engine_name = ENTITY_TO_ENGINE_MAP.get(ontology_name, ontology_name)
        if engine_name in shared:
            shared[engine_name] = Quantity(override_val, shared[engine_name].unit)
        elif engine_name in all_stocks:
            all_stocks[engine_name] = Quantity(override_val, all_stocks[engine_name].unit)
```

**Sub-stepped sector coverage:** The injection must happen in the Phase 1 loop (sub-stepped sectors) as well as Phase 3 (single-rate sectors). The cleanest approach is to inject once per master step, before Phase 1, since sub-stepped sectors use `frozen_inputs` (last-known master boundary values):

```python
# At start of master loop (same placement as policy_applier):
if self._exogenous_injector is not None:
    overrides = self._exogenous_injector(t)
    for ontology_name, val in overrides.items():
        engine_name = ENTITY_TO_ENGINE_MAP.get(ontology_name, ontology_name)
        if engine_name in shared:
            shared[engine_name] = Quantity(val, shared[engine_name].unit)
```

This way both sub-stepped sectors (which receive `frozen_inputs` derived from `shared`) and single-rate sectors (which read from `shared` directly) see the overrides.

### Implementation

**Files modified:**
- `pyworldx/core/engine.py` — Add `exogenous_injector` parameter; inject at start of master loop
- `pyworldx/scenarios/runner.py` — Create `exogenous_injector` from Scenario; pass to Engine

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_exogenous_injector_none_no_change` | Identical output when None |
| 2 | `test_exogenous_injector_called_each_timestep` | Called once per master step |
| 3 | `test_ontology_name_translated_to_engine_name` | `"population.total"` → `"POP"` via ENTITY_TO_ENGINE_MAP |
| 4 | `test_exogenous_override_replaces_shared_value` | Override replaces corresponding shared variable |
| 5 | `test_exogenous_override_handles_missing_key` | Silently ignored if key not in shared |
| 6 | `test_exogenous_affects_sub_stepped_sectors` | Sub-stepped sectors see overrides via frozen_inputs |
| 7 | `test_exogenous_interpolation_at_non_integer_t` | pd.Series interpolation works at non-integer t |

### Acceptance Criteria

- [ ] Engine accepts optional `exogenous_injector` parameter
- [ ] Ontology names translated to engine names via ENTITY_TO_ENGINE_MAP
- [ ] Injection affects both sub-stepped and single-rate sectors
- [ ] Default behavior (None) is identical to current
- [ ] All 7 tests pass
- [ ] All previous tests still pass
- [ ] mypy strict passes
- [ ] ruff check passes

---

## Task 3: Run Canonical R-I-P Test Against PySD Reference

**Status:** ⚠️ Self-referential, no analytical sub-case test  
**Priority:** 🔴 HIGH  
**Effort:** 2-3 days

### The Problem

`generate_reference.py` generates reference from pyWorldX's own engine, not from PySD. The test verifies pyWorldX matches pyWorldX. The spec requires independent verification against PySD==3.14.0.

### What needs to happen

**Step 3a: Install PySD and generate proper reference**

```bash
pip install PySD==3.14.0
cd tests/canonical
python generate_reference.py  # Should load rip_canonical.xmile via PySD
```

The script must be rewritten to:
1. Read `requirements-canonical.txt` and assert PySD version matches
2. Load `rip_canonical.xmile` via PySD
3. Run simulation with RK4, dt=1.0, t_start=0, t_end=200
4. Write `reference_trajectory.csv` with header: PySD version, xmile sha256, generation timestamp

**Step 3b: Compare pyWorldX against PySD reference**

If max relative error < 1e-4: ✅ engine correctness verified independently.
If mismatch > 1e-4: investigate in order:
1. XMILE parameter encoding (verify all Section 17.1 parameters match)
2. Table interpolation (PySD uses piecewise-linear with clamped extrapolation — same as pyWorldX?)
3. RK4 step size (PySD may use different integrator settings)
4. Actual engine bug

**Step 3c: Add analytical sub-case test**

Spec Section 17.4 requires:
```
Configuration: pollution_inflow=0, P(0)=100, tau_p=20.0, t_end=200
Analytical: P(t) = 100 * exp(-t / tau_p)
Pass: relative error < 1e-4 for t≤100, absolute error < 1e-6 for t>100
```

This tests the RK4 integrator in isolation (no algebraic loops, no multi-rate, no cross-sector coupling).

### Acceptance Criteria

- [ ] `generate_reference.py` loads `rip_canonical.xmile` via PySD==3.14.0
- [ ] `reference_trajectory.csv` header contains PySD version, xmile sha256, timestamp
- [ ] pyWorldX passes max relative error < 1e-4 against PySD reference
- [ ] Analytical sub-case test: relative < 1e-4 for t≤100, absolute < 1e-6 for t>100
- [ ] Existing canonical tests still pass

---

## Task 4: Run World3-03 Validation with NEBEL_2023_CALIBRATION_CONFIG

**Status:** ❌ Never executed  
**Priority:** 🔴 HIGH  
**Effort:** 2-3 days

### The Problem

No one has actually run the World3-03 model and compared against historical data. The function exists, the data exists, but they've never been connected.

### Critical Design Fixes (from audit)

**Variable name mapping:** NEBEL_2023_BOUNDS keys don't match engine trajectory keys. Need an explicit mapping layer:

```python
NEBEL_TO_ENGINE = {
    "population": "POP",
    "industrial_output": "industrial_output",  # matches
    "food_per_capita": "food_per_capita",        # matches
    "pollution": "pollution_index",              # engine uses pollution_index
    "nonrenewable_resources": "NR",              # engine uses NR
    "service_per_capita": "service_output_per_capita",  # engine uses service_output_per_capita
    "human_welfare_hdi": "human_welfare_index",  # engine uses human_welfare_index
    "ecological_footprint": "ecological_footprint",  # matches
}
```

**Annual data requirement:** `World3ReferenceConnector` provides decadal data. Use `fetch_interpolated()` method for annual resolution in the 1970-2020 window.

**Time index conversion:** Engine uses offset-from-1900 (0.0 to 123.0). Historical data uses year indices (1970, 1971, ...). Convert via `index = result.time_index + 1900`.

### Acceptance Criteria

- [ ] Variable name mapping implemented (NEBEL → engine names)
- [ ] Annual historical data available for at least 6 of 8 variables
- [ ] `validate_against_nebel2023()` runs with `NEBEL_2023_CALIBRATION_CONFIG`
- [ ] Total NRMSD documented (≤ 0.2719 or failures documented with root cause)
- [ ] Per-variable bounds documented (pass/fail for each of 8 variables)
- [ ] Validation report saved as artifact

---

## Task 5: Resolve Connector Architecture Decision

**Status:** ❌ 9 dead stub files  
**Priority:** 🟡 MEDIUM  
**Effort:** 1 day

### The Decision (Verified)

All 9 stubs return empty pd.Series. Only imported by `test_data_connectors.py`. `data_pipeline/` has 27 working connectors. DataBridge already reads from `data_pipeline/data/aligned/` Parquet.

### The Fix

**Delete 9 files:** `world_bank.py`, `fred.py`, `faostat.py`, `noaa_co2.py`, `our_world_in_data.py`, `un_pop.py`, `undp_hdr.py`, `unido.py`, `footprint_network.py`

**Keep:** `base.py` (DataConnector Protocol), `csv_connector.py` (working utility)

**Update test:** Replace `test_data_connectors.py` with a test that verifies the DataBridge correctly reads from data_pipeline aligned store. Or remove it entirely if the data_pipeline tests cover this.

**Document architecture:** Add docstring to `pyworldx/data/__init__.py`:
```python
"""Data layer for pyWorldX calibration.

This layer provides:
- DataBridge: maps data_pipeline aligned entities to engine variable names
- CalibrationTarget: structured calibration data with NRMSD methods

For raw data ingestion, use data_pipeline/ (27 working connectors, Parquet stores,
quality validation). The DataBridge reads data_pipeline's aligned Parquet output
and converts it to calibration targets.

Do not add new connectors here. Add them to data_pipeline/connectors/.
"""
```

### Acceptance Criteria

- [ ] 9 stub connector files deleted
- [ ] `test_data_connectors.py` updated or removed
- [ ] `__init__.py` clean
- [ ] Architecture documented in `pyworldx/data/__init__.py`
- [ ] Full test suite still passes
- [ ] Decision #1 marked as resolved in `open_decisions.md`

---

## Task 6: Implement Full TAI > CAI > AI Investment Allocation Chain

**Status:** ❌ FIALD mechanism, CAI, FALM, DCPH all missing  
**Priority:** 🔴 HIGH (must be done before World3-03 validation)  
**Effort:** 2-3 days

### The Problem (Verified Against pyWorld3 Source)

Studied the actual pyWorld3 implementation and compared against pyWorldX.

**What pyWorld3 does (correct World3-03):**

```
IO × FIOAA → TAI
TAI × FIALD(MPLD/MPAI) → Land Development Rate = TAI × FIALD / DCPH
TAI × (1-FIALD) → CAI → SMOOTH(ALAI=2yr) → AI
AI × (1-FALM) / AL → AIPH → LYMC → food
AI × FALM → Land Maintenance
```

**What pyWorldX does (simplified/wrong):**

```
TAI = IO × FIOAA
ag_input = SMOOTH2(TAI, ALAI=2yr)  # No FIALD split
AIPH = ag_input / AL
land_dev = (PAL - AL) × land_dev_rate × IO_factor  # Heuristic, not TAI×FIALD/DCPH
```

**Missing: 3 lookup tables + 1 state variable + marginal productivity equations.**

**FIOAA duplication:** Both capital.py and agriculture.py compute FIOAA independently. Agriculture uses dynamic IFPC, capital uses static SFPC. They can diverge.

### Critical Design Fixes (from audit)

**MLYMC is NOT a lookup table.** In World3-03, MLYMC is the **derivative (slope) of the LYMC curve** with respect to AIPH, not a separate lookup table. The plan must compute it numerically:

```python
# MLYMC = d(LYMC)/d(AIPH) — numerical derivative of LYMC table
delta = 1.0  # small perturbation
lymc_base = table_lookup(aiph, _LYMC_X, _LYMC_Y)
lymc_perturbed = table_lookup(aiph + delta, _LYMC_X, _LYMC_Y)
mlymc = (lymc_perturbed - lymc_base) / delta
```

**CAI replaces SMOOTH2:** The current agriculture.py uses AI_S1 and AI_S2 as a SMOOTH2 cascade on TAI. With the FIALD split, CAI is smoothed directly (SMOOTH = 1st-order delay). This means removing AI_S1/AI_S2 stocks and replacing with a single CAI stock:

```python
d_CAI = (cai - CAI) / ALAI  # SMOOTH as ODE
```

### Implementation

**Step 6a:** Add FIALD, DCPH, FALM lookup tables to agriculture.py

**Step 6b:** Compute MPLD and MPAI (with MLYMC as numerical derivative of LYMC)

**Step 6c:** Compute FIALD = table_lookup(MPLD / max(MPAI, 1e-10))

**Step 6d:** Replace SMOOTH2 (AI_S1/AI_S2) with CAI stock (1st-order delay)

**Step 6e:** Compute FALM and split CAI into productive use vs. land maintenance

**Step 6f:** Fix FIOAA duplication — remove from capital.py, capital reads from agriculture

Critical: Capital sector must add `frac_io_to_agriculture` to `declares_reads()` and remove it from `declares_writes()`. Without the `declares_reads()` update, the dependency graph will NOT order agriculture before capital.

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_fiald_table_values` | Matches pyWorld3 canonical values |
| 2 | `test_dcp_table_values` | Matches canonical values |
| 3 | `test_falm_table_values` | Matches canonical values |
| 4 | `test_fiald_split_high_mpld` | When MPLD >> MPAI, most TAI goes to land development |
| 5 | `test_fiald_split_high_mpai` | When MPAI >> MPLD, most TAI goes to agricultural inputs |
| 6 | `test_cai_smoothed_vs_tai` | CAI is smoothed version of TAI × (1-FIALD) |
| 7 | `test_falm_splits_ai` | FALM splits AI into productive use vs. land maintenance |
| 8 | `test_fioaa_from_agriculture_not_capital` | Capital reads FIOAA from shared state |
| 9 | `test_mlymc_numerical_derivative` | MLYMC computed as numerical derivative of LYMC |
| 10 | `test_full_chain_in_engine` | IO → FIOAA → TAI → FIALD → CAI → AI → FALM → AIPH → LYMC → food |
| 11 | `test_food_trajectory_changes` | Different (more accurate) food_per_capita trajectory vs. simplified version |

### Acceptance Criteria

- [ ] FIALD, DCPH, FALM lookup tables with correct canonical values
- [ ] MPLD and MPAI computed (MLYMC as numerical derivative of LYMC)
- [ ] CAI implemented as 1st-order delay stock (replaces SMOOTH2 on TAI)
- [ ] LDR driven by TAI × FIALD / DCPH (not heuristic)
- [ ] FALM splits AI into productive use and land maintenance
- [ ] FIOAA computed only in agriculture, read by capital (declares_reads updated)
- [ ] All 11 tests pass
- [ ] Existing tests still pass
- [ ] Agriculture metadata updated (remove FALM approximation note)

---

## Task Dependencies and Ordering

```
Week 1:
  ├── Task 5 (Connector cleanup) ── 1 day ── independent
  │
  ├── Task 1 (Policy wiring) ── 2-3 days
  │    └─ Modifies Engine.__init__ and Engine.run()
  │
  └── Task 2 (Exogenous wiring) ── 2-3 days
       └─ Modifies Engine.__init__ and Engine.run()
          Best done right after Task 1 (same files)

Week 2:
  ├── Task 6 (TAI > CAI > AI chain) ── 2-3 days
  │    └─ MUST be done before Task 4 (changes food trajectory)
  │
  ├── Task 3 (Canonical R-I-P vs PySD) ── 2-3 days
  │    └─ Depends on Tasks 1+2 (engine modified)
  │
  └── Task 4 (World3-03 validation) ── 2-3 days
       └─ Depends on Task 6 (food trajectory changes)

Week 3 (buffer):
  └── Address any failures from Tasks 3-4
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Task 1: Policy targets don't match engine variables** | Certain | Medium — `pollution.industrial_pollution_intensity` doesn't exist | Fix scenario targets to use flat engine names (Option A) |
| **Task 1: Hook placement wrong** | Medium (caught by audit) | High — policies would have no effect if placed after sector compute | Place hook BEFORE Phase 1 (sub-stepped sectors) |
| **Task 2: Exogenous keys use ontology names, not engine names** | Certain (caught by audit) | Medium — overrides silently ignored | Use ENTITY_TO_ENGINE_MAP for translation |
| **Task 3: PySD reference doesn't match pyWorldX** | Medium | High — could indicate engine bug | Investigate: XMILE encoding → table interpolation → RK4 → engine bug |
| **Task 4: NRMSD exceeds 0.2719** | Medium | High — but may be data/proxy mismatch | Document per-variable failures; determine root cause |
| **Task 6: MLYMC not a lookup table** | Certain (caught by audit) | Medium — plan had wrong formula | Compute MLYMC as numerical derivative of LYMC curve |
| **Task 6: Capital declares_reads not updated** | Medium (caught by audit) | High — topological sort won't order correctly | Must add `frac_io_to_agriculture` to capital's declares_reads() |

---

## Definition of Done

### Code Quality
- [ ] All 6 tasks completed
- [ ] `pytest tests/ -v` passes with 0 failures (currently 470 passing)
- [ ] `mypy pyworldx --exclude data_pipeline` passes with 0 errors (fix 2 bridge.py errors)
- [ ] `ruff check pyworldx` passes (currently clean)
- [ ] Coverage ≥ 90% for all modified modules

### Validation
- [ ] Canonical R-I-P test passes against PySD reference (max rel error < 1e-4)
- [ ] Analytical sub-case passes (hybrid criterion met)
- [ ] World3-03 validation run with NEBEL_2023_CALIBRATION_CONFIG — results documented
- [ ] 9 new policy tests pass
- [ ] 7 new exogenous tests pass
- [ ] 11 new agriculture investment chain tests pass

### Housekeeping
- [ ] 9 stub connector files deleted
- [ ] `open_decisions.md` updated: Decision #1 and #2 marked as resolved
- [ ] `pyworldx/data/__init__.py` documents architecture
- [ ] No new TODO comments introduced without being tracked
