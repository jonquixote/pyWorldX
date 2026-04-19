# Pre-Flight Remediation Plan
**Branch:** `phase-2-remediation`  
**Date:** 2026-04-18  
**Prerequisite:** Complete all items in this plan before running `EmpiricalCalibrationRunner` or any NRMSD-based calibration.  
**Cross-reference:** `plans/preflight_audit.md`, `plans/Full-System Calibration Plan for pyWorldX (Phase 2 Remediation).md`

---

## Tier 1 — Hard Blockers (Calibration Output is Invalid Without These)

These four issues will produce numerically nonsensical NRMSD scores. Fix in sequence.

---

### T1-1 · Fix Pollution Index Unit Mismatch in `map.py`

**File:** `data_pipeline/map.py`  
**Problem:** `world3_reference_pollution_index` (dimensionless, ~1.0 at 1970) is mapped to the same `CalibrationTarget` entity as `atmospheric.co2` (units: ppm, ~325 at 1970). Dividing a dimensionless index by a ppm value produces a ratio ~0.003 instead of 1.0, corrupting NRMSD for the entire pollution sector.

**Fix:**
- Separate into two distinct entities: `pollution_index_relative` (for the World3 reference trajectory) and `atmospheric_co2_ppm` (for Keeling Curve / GCP data).
- Namespace the World3 reference to `world3.pollution_index` — it must **never** appear in `ENTITY_TO_ENGINE_MAP` as an empirical target.
- Update `ENTITY_TO_ENGINE_MAP` so `pollution_index_relative` maps to the engine's `PPOLX` variable and `atmospheric_co2_ppm` is tagged `unit_mismatch=True` and excluded from the default objective until a ppm→index conversion factor is implemented.
- This is part of the broader World3 reference → real-entity retirement: see calibration plan §0.3 and §0.4.

**Acceptance test:** `assert targets["pollution_index_relative"].values[0] == pytest.approx(1.0, abs=0.05)` (value at `train_start=1970`).

---

### T1-2 · Fix Food Per Capita Unit Collision in `map.py`

**File:** `data_pipeline/map.py`  
**Problem:** `world3_reference_food_per_capita` (kg/person/yr) and `faostat_food_balance_historical`
(kcal/capita/day) are merged under the same pipeline entity `food_per_capita` with no conversion
applied. The two series differ by a factor of ~1,000 at 1970, which blows out the food-sector NRMSD.

**Fix:**
- Namespace `world3_reference_food_per_capita` to `world3.food_per_capita` and exclude from the
  empirical `ENTITY_TO_ENGINE_MAP`.
- Keep FAOSTAT as the sole empirical food entity.
- **Recommended approach — keep as separate entities:** Let `DataBridge._normalize_to_index()`
  handle alignment via index normalization. Both series index to `1.0 ± 0.10` at 1970 without
  requiring any unit conversion. This is preferred because a single kcal/kg scalar is ambiguous
  across crop types (cereal ≈ 1,800 kcal/kg, legumes ≈ 3,400 kcal/kg, etc.).
- If a merged series is required in future, the correct conversion is:
  - 1,800 kcal/kg cereal equivalent → `1 kg/yr = 1800 / 365 = 4.93 kcal/day`
  - Therefore: `1 kcal/day = 1 / 4.93 ≈ 0.203 kg/yr` (not 0.0547 — previous figure was incorrect)
  - Apply as a `ConversionStep` dataclass before merging.
- In the display/reporting layer, convert internal `fpc` (kg/person/yr) to kcal/person/day via
  `kcal/day = kg/yr × (1800 / 365)` ≈ `kg/yr × 4.93`. Ensure threshold queries (e.g., < 2500
  kcal/day) use this converted series.

**Acceptance test:** After normalization, both series index to `1.0 ± 0.10` at 1970.

---

### T1-3 · Fix FAOSTAT World Country Code in `faostat_food_balance_historical` Connector

**File:** `data_pipeline/connectors/faostat_food_balance_historical.py` (or equivalent config)  
**Problem:** Connector passes `world_country_code="WLD"` to the FAOSTAT API. The correct aggregate code for World totals in FAOSTAT is `"5000"`. With `"WLD"`, the filter returns zero rows silently — the entire 1961–2013 FBSH series is missing from the pipeline cache without raising any error.

**Fix:**
- Change `world_country_code="WLD"` → `world_country_code="5000"` (or `area_code=5000` depending on the API wrapper used).
- Add a post-fetch assertion: `assert len(df) > 0, "FAOSTAT FBSH returned empty — check area_code"`.
- Re-run the connector to regenerate the Parquet cache.

**Acceptance test:** `len(load_parquet("faostat_food_balance_historical")) > 40` (expect ~52 rows for 1961–2013).

---

### T1-4 · Fix `initial_conditions.py` Default Year

**File:** `pyworldx/calibration/initial_conditions.py`  
**Problem:** `target_year` defaults to `1900` rather than `1970`. Any call site that does not explicitly pass `target_year=1970` will initialize World3 stocks from pre-industrial era values. The World3-03 model is not validated before 1900 and the stock trajectories diverge severely before reaching 1970.

**Fix:**
- Change function/class default: `target_year: int = 1970`.
- Grep the entire codebase for `initial_conditions(` without `target_year=` and audit each call site.
- Add a `ValueError` guard: `if target_year < 1900 or target_year > 2100: raise ValueError(...)`.
- Add assertion: `assert target_year <= CrossValidationConfig.train_start` — the simulation
  must start *at or before* the calibration window opens so that a valid state vector exists
  at `train_start`. A `target_year` greater than `train_start` would leave the 1970–`target_year`
  window without simulation data.
- **Replace all literal `1970` integers** in `pyworldx/` and `data_pipeline/` with
  `CrossValidationConfig.train_start` — see T2-5.

**Acceptance test:** `get_initial_conditions()` (no arguments) returns the 1970 stock vector;
`get_initial_conditions(target_year=1900)` still works when explicitly requested.

---

## Tier 2 — Pre-Calibration Data Quality (Fix Before First Optimizer Run)

These issues will not crash calibration, but will silently degrade fit quality or produce misleading NRMSD scores.

---

### T2-1 · Resolve Multi-Source Fan-In Conflicts for SC, IC, AL

**Files:** `data_pipeline/map.py`, `pyworldx/data/bridge.py` (when created)  
**Problem:** `service_capital` (SC), `industrial_capital` (IC), and `arable_land` (AL) each receive data from 2–3 connectors with incompatible units and no arbitration logic. Last-write in Python dict iteration order determines which series is used — non-deterministic across Python versions.

**Fix:**
- Add a `source_priority` list to each multi-source entity in `ENTITY_TO_ENGINE_MAP`:
  ```python
  "service_capital": {
      "engine_var": "SC",
      "sources": ["penn_world_table", "world_bank_capital_stock", "gapminder_gdp_per_capita"],
      "source_priority": ["penn_world_table", "world_bank_capital_stock", "gapminder_gdp_per_capita"],
      "unit": "constant_2017_usd_ppp"
  }
  ```
- Authoritative source assignments (recommended):

  | Stock | Authoritative Source | Unit |
  |---|---|---|
  | SC | PWT `rgdpe` per capita | constant 2017 USD PPP |
  | IC | PWT `rnna` world-summed | constant 2017 USD (deflator step required vs. UNIDO/WB 2015) |
  | AL | FAOSTAT RL `arable_land` | 1000 ha (×1000 to reach ha) |

- In `DataBridge.load_targets()`, implement priority-waterfall: use highest-priority source where non-null, fall back in order.
- Log which source was selected for each entity and year range to the calibration report.

**Acceptance test:** `load_targets()` is deterministic across 100 repeated calls with shuffled source registration order.

---

### T2-2 · Add BP Statistical Review Proved Reserves for NR

**Files:** `data_pipeline/connectors/` (new file), `data_pipeline/map.py`  
**Problem:** There is no continuous observed nonrenewable resource stock series in the pipeline. `usgs_mcs` delivers metadata strings. The `world3_reference_nonrenewable_resources` trajectory is the only current NR input — this is circular calibration. The resource sector is entirely synthetic without a real empirical anchor.

**Fix:**
- Add `BPStatisticalReviewConnector` to fetch proved reserves time-series (oil + gas + coal combined, EJ or Gtoe) from the OWID/BP mirror: `https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/`.
- Map to entity `nonrenewable_resources_proved_reserves` with `unit="EJ"`, tagged `layer=1` (observed proxy).
- Add conversion: `EJ → World3 NR resource units` (calibrate scalar against 1970 World3-03 NR initial value of ~1.0 × 10¹²).
- Keep `world3_reference_nonrenewable_resources` namespaced to `world3.nr_fraction` as `layer=0` (structural reference only) — **never** include it in `ENTITY_TO_ENGINE_MAP`.
- Tag USGS extraction index and depletion ratio as `layer=2` (secondary cross-validation proxy, not primary objective signal).

**Acceptance test:** Series covers at least 1965–2023 with no more than 3 consecutive missing years.

---

### T2-3 · Implement Zero-Guard in `_normalize_to_index()`

**File:** `pyworldx/data/bridge.py` (when created)  
**Problem:** Several USGS and early World Bank series have zero-padded years before 1960. If `X(train_start) = 0`, the normalization `X(t) / X(train_start)` produces `inf` or `NaN`, which propagates silently through the NRMSD calculation.

**Fix:**
```python
def _normalize_to_index(self, series: pd.Series, base_year: int) -> pd.Series:
    base_val = series.loc[base_year]
    if base_val == 0 or pd.isna(base_val):
        # Fall back to first non-zero value within ±5 years of base_year
        window = series.loc[base_year - 5 : base_year + 5]
        nonzero = window[window > 0]
        if nonzero.empty:
            raise DataBridgeError(
                f"Cannot normalize: no non-zero base value near {base_year}"
            )
        base_val = nonzero.iloc[0]
        logger.warning(
            "Zero base value at %d; using %d instead", base_year, nonzero.index[0]
        )
    return series / base_val
```

Note: `base_year` must always be passed as `CrossValidationConfig.train_start`, never as a hardcoded integer.

**Acceptance test:** `_normalize_to_index(pd.Series({1970: 0, 1971: 3.5}), 1970)` raises `DataBridgeError` rather than returning `inf`.

---

### T2-4 · Add Parquet Cache Staleness Check to `DataBridge.load_targets()`

**File:** `pyworldx/data/bridge.py` (when created)  
**Problem:** If a connector's Parquet cache is missing or older than the connector's `cache_ttl`, `DataBridge` currently hits a bare `FileNotFoundError` from pandas with no diagnostic context — making the manual verification step very slow to debug.

**Fix:**
- Before loading each Parquet file, check `Path(parquet_path).exists()`.
- If missing: raise `DataBridgeError(f"Parquet cache missing for '{entity}'. Run: python -m data_pipeline.connectors.{connector_name}")`.
- If present but older than `cache_ttl` days: emit `logger.warning(...)` with the file age and connector refresh command.

**Acceptance test:** Deleting a Parquet file and calling `load_targets()` raises `DataBridgeError` with the connector name in the message.

---

### T2-5 · Confirm `CrossValidationConfig.train_start` Propagates Correctly

**Files:** `pyworldx/calibration/metrics.py`, `pyworldx/calibration/pipeline.py`  
**Problem:** `CrossValidationConfig.train_start = 1970` is defined in `metrics.py` but it is not verified that all downstream consumers (`build_objective()`, `calculate_validation_score()`, `initial_conditions`) actually read from this single source of truth. If any site hardcodes `1970` as a literal int, a future config change will silently break alignment.

**Fix:**
- Grep for literal `1970` across `pyworldx/` and `data_pipeline/`.
- Replace every instance with `CrossValidationConfig.train_start` or a passed `config` reference.
- Add a `__post_init__` assertion to `CrossValidationConfig`: `assert self.train_start < self.train_end < self.validation_end`.
- This includes the `base_year` argument to `_normalize_to_index()` — it must always receive `config.train_start`, never a literal integer.

**Acceptance test:** Changing `CrossValidationConfig.train_start = 1971` in tests causes all window boundaries to shift by one year with no `AssertionError` and no hardcoded 1970 producing misalignment.

---

### T2-6 · Add Scenario Argument to `EmpiricalCalibrationRunner` (NEW)

**File:** `pyworldx/calibration/empirical.py`  
**Problem:** `EmpiricalCalibrationRunner` has no `scenario` argument. Hardcoding `Standard Run` makes it impossible to compare calibration quality against historical policy scenarios (e.g., `Historical Emissions Policy`) without a separate runner subclass.

**Fix:**
- Add `scenario: str = "standard_run"` to `EmpiricalCalibrationRunner.__init__`.
- Validate `scenario` against the engine's registered scenario list at initialization; raise `ValueError` with available options if unknown.
- Pass `scenario` through to the engine run call in `build_objective()`.

**Acceptance test:** Instantiating `EmpiricalCalibrationRunner(scenario="historical_emissions_policy")` runs without error. Instantiating with an unregistered scenario raises `ValueError` listing valid options.

---

## Tier 3 — Verification Gates (Run After All Tier 1 + Tier 2 Items Are Complete)

Execute these in order. Do not proceed to calibration until all gates pass.

### Gate 1 — Unit Audit
```bash
python -m pyworldx.data.bridge --audit-units
```
Expected: zero `UNIT_MISMATCH` entries in output. Any remaining mismatches must be resolved or explicitly tagged `excluded_from_objective=True` with a documented reason.

### Gate 2 — Initial Conditions Smoke Test
```bash
python -c "
from pyworldx.calibration.initial_conditions import get_initial_conditions
ic = get_initial_conditions()
assert ic['year'] == 1970
print('IC year:', ic['year'])
print('POP:', ic['POP'])   # expect ~3.5e9
print('NR:', ic['NR'])     # expect ~1.0e12
print('PPOLX:', ic['PPOLX'])  # expect ~1.0
"
```

### Gate 3 — Pipeline Data Coverage Report
```bash
python -m pyworldx.data.bridge --report-coverage --aligned-dir ./output/aligned
```
Expected output columns: `entity | source | years_covered | gap_count | base_year_value | base_year_nonzero`. Any entity with `base_year_nonzero=False` is a T1/T2 blocker that must be resolved before calibration.

### Gate 4 — Full Test Suite
```bash
pytest tests/ -x -q --tb=short
```
Expected: all tests pass. Zero `XFAIL` items that were passing before. Pay particular attention to `test_databridge.py` and `test_empirical_calibration.py`.

**Note on `test_empirical_calibration.py`:** Assert that `overfit_flagged` triggers only when `validation_nrmsd - train_nrmsd > CrossValidationConfig.overfit_threshold` — **not** as a hard failure for any `validation_nrmsd > train_nrmsd`. Mild degradation from train to validation window is expected and healthy. Mock data that accidentally produces `validation_nrmsd < train_nrmsd` should not fail the test.

### Gate 5 — End-to-End Dry Run
```bash
python -m pyworldx.calibration.empirical --dry-run --train-window 1970-2010 --holdout-window 2010-2023
```
Expected: run completes without `UnitMismatchError`, `DataBridgeError`, or `NaN` in reported NRMSD. The `--dry-run` flag skips the Nelder-Mead optimizer and reports data coverage only.

---

## Open Decision Log

| # | Decision | Options | Status |
|---|---|---|---|
| 1 | Scenario for empirical calibration | `Standard Run` only vs. accept `scenario` arg | **Resolved: accept `scenario` arg, default `"standard_run"`** — enables comparison against `Historical Emissions Policy` without a separate runner subclass. See T2-6. |
| 2 | NR proxy layer weighting | BP reserves as sole Layer 1 vs. blend with WEO data | Unresolved — defer to post-preflight. BP reserves is required minimum; WEO blend is optional enhancement. |
| 3 | World3ReferenceConnector scope | Layer 0 (structural only, excluded from objective) vs. Layer 1 (included with low weight) | **Resolved: Layer 0 only** — including World3 reference trajectories as calibration targets is circular. All `world3_reference_*` mappings must be namespaced and excluded from `ENTITY_TO_ENGINE_MAP`. See calibration plan §0.4 and preflight audit §2.2. |

---

## Completion Criteria

This preflight plan is complete when:
- [ ] All 4 Tier 1 blockers resolved and committed
- [ ] All 6 Tier 2 issues resolved and committed (including new T2-6)
- [ ] All 5 Gates pass in a clean `pytest` + dry-run run
- [ ] `plans/implementation_audit_report.md` updated with resolved status for each finding
- [ ] PR description references this file: `plans/2026-04-18-preflight-plan.md`
- [ ] No literal `1970` integers remain in `pyworldx/` or `data_pipeline/` (all replaced with `CrossValidationConfig.train_start`)
- [ ] All `world3_reference_*` mappings namespaced to `world3.*` and excluded from `ENTITY_TO_ENGINE_MAP`
