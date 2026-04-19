# pyWorldX Phase-2 Calibration — Pre-Flight Data Audit

**Branch:** `phase-2-remediation`  
**Audit Date:** 2026-04-18  
**Scope:** Data sufficiency, proxy identification, unit-transform integrity, and readiness blockers before executing the calibration plan.

---

## Executive Summary

The pipeline is well-stocked for population, emissions, and land sectors. However, **four hard blockers** and **six significant risks** must be resolved before the calibration run is trustworthy. The most critical issues are: (1) the nonrenewable-resource sector has no real observed stock data — only engineered proxies — and the `World3ReferenceConnector` currently maps its dimensionless pollution index directly onto `atmospheric.co2` in ppm, which is a category error; (2) three key entities (`SC`, `IC`, `PPOL`) carry multi-source fan-out with incompatible units and no arbitration logic; (3) the `faostat_food_balance_historical` world-code mismatch (`WLD` vs `5000`) will silently produce empty series for the 1961–2013 window; and (4) `initial_conditions.py` defaults `target_year=1900` but the calibration window starts at 1970, meaning the stock initialization path is exercised with the wrong year unless overridden at every call site.

---

## 1. Data Coverage Audit

### 1.1 Sector-by-Sector Observable Coverage

| pyWorldX Sector | Engine Stock | Primary Real-Data Sources | Coverage (years) | Confidence |
|---|---|---|---|---|
| Population | `POP` | UN Population, World Bank SP.POP.TOTL, FAOSTAT OA, Gapminder | 1950–2024 | ✅ High |
| Industrial Capital | `IC` | PWT `rnna` (185 countries), UNIDO MVA, World Bank NV.SRV.TOTL.KD | 1950–2023 | ✅ High |
| Service Capital | `SC` | Gapminder GDP/capita, OWID Maddison, FRED GDPC1, IMF WEO | 1820–2023 | ✅ High |
| Agriculture — Arable Land | `AL` | FAOSTAT RL (full 1961–2023 + land_use subset) | 1961–2023 | ✅ High |
| Agriculture — Food/capita | `food_supply_per_capita` | FAOSTAT FBS + FBSH + OWID daily caloric supply | 1961–2023 | ✅ High |
| Pollution — Atmospheric CO₂ | `PPOL_atmospheric` | NOAA annual (Mauna Loa + global), NASA GISS anomaly | 1958–2024 | ✅ High |
| Pollution — Fossil CO₂ | `PPOL` | GCP, EDGAR, PRIMAP-hist, OWID, CEDS | 1750–2023 | ✅ High |
| Non-Renewable Resources | `NR` | **USGS MCS metadata only; no continuous stock series** | N/A | 🔴 None |
| Persistent Pollution Index | (dimensionless) | **World3 reference only; CEDS SO₂ is a flow, not a stock** | N/A | 🔴 None |
| Service Output / Welfare | `SC` proxy | UNDP HDI, Footprint Network, IHME GBD | 1990–2023 | ⚠️ Partial |

### 1.2 Missing Sources Worth Adding

The following high-value, freely available datasets are not yet connected and would meaningfully improve coverage for underserved sectors:

| Gap | Recommended Source | Why It Matters |
|---|---|---|
| Fossil fuel production by type (oil/gas/coal) | BP Statistical Review / EIA international | Best real-world proxy for NR depletion rate |
| Mineral reserve estimates time-series | USGS Mineral Commodity Summaries (annual tabular, not metadata) | Grounds `NR` stock with published reserve data |
| Global industrial investment (GFCF) | World Bank NE.GDI.FTOT.KD | Better `IC` accumulation signal than MVA alone |
| Persistent organic pollutant proxies | UNEP POPs Global Monitoring Plan reports | Closest observable to World3 `PPOL` |
| Service sector output (non-US) | World Bank NV.SRV.TOTL.KD already mapped — confirm aggregation works globally | Fills SC gap outside OECD/FRED |

---

## 2. Proxy Audit — Where Real Data Exists

### 2.1 Confirmed Proxies Using Real Data (Appropriate)

| Entity | Source | Quality Flag | Assessment |
|---|---|---|---|
| `resources.extraction_index` | USGS derived | `PROXY` | Acceptable — explicitly flagged |
| `resources.depletion_ratio` | USGS derived | `PROXY` | Acceptable — explicitly flagged |
| `capital.industrial_stock` | PWT `rnna` world-summed | `OK` | Sound: capital stock, not a proxy |
| `output.service_per_capita` | WB NV.SRV.TOTL.KD ÷ population | `OK` | Derived but from primary data |

### 2.2 Proxies Where Better Real Data Exists (Action Required)

| Entity | Current Approach | Problem | Better Alternative |
|---|---|---|---|
| `resources.nonrenewable_stock` (`NR`) | `world3_reference_nr_fraction_remaining` (dimensionless, quality=`REFERENCE`) also mapped from `usgs_nonrenewable_proxy` | Circular calibration: fitting engine to its own reference model | BP Statistical Review total proved reserves time-series (oil + gas + coal) normalized to 1970 = 1.0 |
| `atmospheric.co2` (pollution index) | `world3_reference_pollution_index` mapped to `atmospheric.co2` in ppm | **Category error**: dimensionless pollution index ≠ ppm CO₂. DataBridge will produce nonsense NRMSD when it divides a dimensionless index by NOAA ppm | Retire this mapping; use NOAA `noaa_co2_annual` exclusively; keep `world3_reference_pollution_index` as a separate diagnostic entity |
| `gdp.current_usd` (industrial output proxy) | `world3_reference_industrial_output` mapped to `gdp.current_usd` in `industrial_output_units` | Apples-to-oranges: World3 industrial output is not GDP | Map to a dedicated entity `world3.industrial_output`; never merge with real GDP |
| `food.supply.kcal_per_capita` | `world3_reference_food_per_capita` in `veg_equiv_kg/person/yr` alongside FAOSTAT in `kcal/capita/day` | **Unit collision**: different physical quantities merged under same entity | Retire food reference mapping or map to `world3.food_per_capita` |
| Service Capital (`SC`) | `gdp.per_capita`, `gdp.maddison`, `gdp.current_usd` all map to `SC` | Three incompatible units feeding the same stock with no arbitration | Nominate `gapminder_gdp_per_capita` (constant 2015 USD) as authoritative; demote others to cross-validation |

---

## 3. Unit-Transform Integrity

### 3.1 Hard Unit Blockers

| Issue | Location | Severity |
|---|---|---|
| `world3_reference_pollution_index` → `atmospheric.co2` (ppm) | `map.py` lines ~438–445 | 🔴 Blocker — divide-by-zero or nonsense index ratio |
| `world3_reference_food_per_capita` (kg/person/yr) → `food.supply.kcal_per_capita` (kcal/capita/day) | `map.py` lines ~427–434 | 🔴 Blocker — ~1400 kcal/person/day = ~510 kg/person/yr but no conversion factor defined |
| `world3_reference_industrial_output` (`industrial_output_units`) → `gdp.current_usd` | `map.py` lines ~420–426 | 🔴 Blocker — dimensionally undefined merge |
| `faostat_food_balance_historical` uses `world_country_code="WLD"` but FAOSTAT's World code is `5000` | `map.py` lines ~139–167 | 🔴 Blocker — filter will match nothing; 1961–2013 FBSH series will be empty |

### 3.2 Unit Inconsistencies Requiring Arbitration

| Entity | Sources with Conflicting Units | Resolution Needed |
|---|---|---|
| `population.total` | `persons` (WB), `1000_persons` (FAOSTAT OA, FBSH), `persons` (Gapminder, OWID) | Add `scale_factor: 1000` to all `1000_persons` sources or add a `unit_conversion` transform |
| `gdp.current_usd` | `current_USD` (WB), `USD_millions` (OECD SNA), `industrial_output_units` (World3 ref) | Requires explicit scale `×1e6` on OECD; retire World3 mapping |
| `capital.industrial_stock` (`IC`) | `constant_2017_national_prices` (PWT), `constant_2015_USD` (UNIDO MVA, WB) | Base-year mismatch; PWT values need a deflator step to reach 2015 USD |
| `land.arable_hectares` | `1000_ha` (both FAOSTAT RL sources) | Consistent but requires `×1000` scale factor to reach hectares for the engine |
| `emissions.co2_fossil` | `Mt_CO2` (GCP, EDGAR, OWID), `kt_CO2` (PRIMAP-hist before transform) | PRIMAP transform exists (`factor: 0.001`) — verify it is applied before aggregation, not after |

### 3.3 Missing Transform Specifications

| Entity | Issue |
|---|---|
| `usgs_mcs` → `resources.nonrenewable_stock` | `unit="metadata"` with empty transforms list — produces a useless row of metadata strings in the aligned store |
| `imf_weo` → `imf.weo_raw` | `TransformSpec("imf_weo_parse")` — no corresponding transform function located in the codebase; will raise `KeyError` at runtime |
| `nebel_2023_supplement` → `nebel_2023.raw` | `TransformSpec("nebel_2023_parse")` — same risk; parser existence unconfirmed |
| `ceds_nox/bc/oc/co/nh3/nmvoc` | `country_filter=None` but data is multi-country; no `aggregate_world` step | Will pass through all country rows uncollapsed |

---

## 4. Initial Conditions Integrity

### 4.1 Default Year Mismatch

`initial_conditions.py` sets `target_year=1900` as the default. The calibration window starts at 1970. This means:

- Any call site that doesn't explicitly pass `target_year=1970` will silently initialize stocks with 1900-era values.
- The engine will start the simulation at 1900 and spend 70 years in unmeasured territory before the calibration window begins — amplifying any structural error.
- **Fix:** Change the default to `target_year=1970` and add an assertion that `target_year >= CrossValidationConfig.train_start`.

### 4.2 Stock-to-Entity Collisions

Three entities in `SECTOR_STOCK_MAP` resolve to the same `stock_name`:

| Stock | Competing Entities | Risk |
|---|---|---|
| `IC` | `industry.manufacturing_value_added`, `industry.value_added`, `capital.industrial_stock` | Last-write wins; extraction order is dict iteration order (non-deterministic in edge cases) |
| `SC` | `gdp.per_capita`, `gdp.maddison`, `gdp.current_usd` | Same last-write issue; units are completely different |
| `AL` | `land.arable_hectares`, `land.cropland_hectares` | Cropland ⊂ Arable — conflating them overstates the stock |

### 4.3 Default Values Not Cross-Checked

The `default_value` entries (used when aligned data is absent) are hardcoded 1900 estimates with no documented source:
- `NR default = 1.0e12` — unit `resource_units` is undefined; no normalization to engine's expected initial condition
- `IC default = 2.0e11` — in 2015 USD; plausible but uncited
- `SC default = 500.0` — GDP per capita in 1900; plausible but in different units than what the engine expects

---

## 5. DataBridge Readiness

Before `DataBridge._normalize_to_index()` can run cleanly, the following must be true:

| Precondition | Status |
|---|---|
| All entities feeding the objective function share a single unit per entity | ❌ Not yet — multi-source fan-in unresolved |
| `X(train_start)` ≠ 0 for all calibration targets | ❌ Unknown — no zero-guard exists in current code |
| `world3_reference_*` entries are cleanly separated from empirical targets | ❌ Four World3 reference mappings collide with real-data entities |
| All `filter_rows` transforms match actual column values in source data | ⚠️ FBSH world code mismatch confirmed; others untested |
| `imf_weo_parse` and `nebel_2023_parse` transform functions exist | ⚠️ Not verified in pipeline transform registry |

---

## 6. Recommended Pre-Flight Checklist

### Must Fix Before Any Calibration Run (Blockers)

1. **Retire all four `world3_reference_*` → real-entity collision mappings.** Map World3 reference trajectories to namespaced entities (`world3.population`, `world3.industrial_output`, etc.) and exclude them from the `ENTITY_TO_ENGINE_MAP` used by DataBridge.
2. **Fix FBSH world code:** Change `world_country_code="WLD"` to `"5000"` in `faostat_food_balance_historical` mapping.
3. **Add `scale_factor: 1000` transforms** to all `1000_persons` population sources and all `1000_ha` land sources.
4. **Change `initial_conditions.py` default** from `target_year=1900` to `target_year=1970`.
5. **Add zero-guard to `_normalize_to_index()`:** `denominator = max(X[train_start], epsilon)` where `epsilon = 1e-9`.

### Fix Before Full Multi-Sector Calibration

6. **Nominate single authoritative source per stock** — document the source priority table and enforce it in `DataBridge.load_targets()`.
7. **Verify `imf_weo_parse` and `nebel_2023_parse` exist** in the transform registry; add stubs that raise `NotImplementedError` with clear messages if not.
8. **Add `aggregate_world` to CEDS non-CO₂ species** (NOx, BC, OC, CO, NH₃, NMVOC) so they collapse to a single global row.
9. **Replace `usgs_mcs` metadata mapping** with a proper tabular connector reading USGS MCS annual tables (or explicitly mark it as `NOT_CALIBRATION_TARGET`).
10. **Add BP Statistical Review connector** for total proved fossil fuel reserves (oil + gas + coal) as the primary empirical anchor for `NR`.

### Validate Before Execution

11. **Run `report_initial_conditions(aligned_dir, target_year=1970)`** and inspect output — confirm every critical stock shows `source: aligned`, not `source: default`.
12. **Spot-check aligned Parquet files** for population (`population_total.parquet`) and food (`food_supply_kcal_per_capita.parquet`) — verify units are uniform before the 1970 normalization step.
13. **Assert temporal coverage:** every calibration target must have ≥ 1 non-null value in both the train window (1970–2010) and the holdout window (2010–2023).

---

## 7. Data Sources Not Yet in the Pipeline (Priority Additions)

| Source | Entity | Access | Priority |
|---|---|---|---|
| BP Statistical Review of World Energy (via OWID mirror) | `resources.fossil_fuel_reserves` | Free CSV | 🔴 High — only real NR anchor |
| World Bank NE.GDI.FTOT.KD (Gross Fixed Capital Formation) | `capital.gfcf` | Free API (WB connector exists) | 🟡 Medium |
| IEA World Energy Balances (open subset) | `energy.consumption_by_fuel` | Free tier | 🟡 Medium |
| UNEP Global Chemicals Outlook (POPs data) | `pollution.persistent_organic` | PDF/CSV | 🟠 Low (manual extraction) |

---

*Report generated from direct inspection of `data_pipeline/connectors/` (37 files), `data_pipeline/alignment/map.py` (ONTOLOGY_MAP, ~750 lines), and `data_pipeline/alignment/initial_conditions.py` on branch `phase-2-remediation`.*
