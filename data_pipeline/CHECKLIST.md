# pyWorldX Real Data — Master Checklist

Generated from `real_data_pyWorldX.md` + `real_data_pyWorldX_plan.md`.
Updated: April 7, 2026.

---

## API Keys & Accounts

| Source | Auth Type | URL | Status | Notes |
|---|---|---|---|---|
| FRED | API key | https://fred.stlouisfed.org/docs/api/api_key.html | ✅ Got it | `95f42f...` in `.env` |
| EIA | API key | https://www.eia.gov/opendata/register.php | ❌ Pending | Register now — takes 30 seconds |
| Footprint Network | Registration | https://footprint.info.yorku.ca/data/ | ❌ Pending | Free signup, instant |
| IHME GBD | Registration | https://healthdata.org/research-analysis/gbd | ❌ Pending | Free signup, instant |
| HMD | Registration | https://www.mortality.org | ❌ Pending | Free signup, 1-2 day approval |

---

## Phase 1: Spec-Critical Quick Wins (No Auth)

| # | Source | Connector | Status | Notes |
|---|---|---|---|---|
| 1 | Nebel 2023 supplement | `nebel_2023.py` | ❌ Not built | PLOS ONE supplement — verify file names |
| 2 | GCP Fossil CO₂ | `gcp.py` | ✅ Working | Zenodo GCB 2024 v18 — 23,863 records fetched |
| 3 | NOAA CO₂ | `noaa.py` | ✅ Working | Mauna Loa annual — 67 records fetched |
| 4 | World Bank | `world_bank.py` | ✅ Working | 4 indicators — 34,036 records total |
| 5 | OWID | `owid.py` | ❌ Not built | `owid-catalog` library or direct CSV |
| 6 | USGS | `usgs.py` | ❌ Not built | Mineral Commodity Summaries |
| 7 | PRIMAP-hist | `primap.py` | ❌ Not built | Zenodo record 10705513 |
| 8 | CEDS | `ceds.py` | ❌ Not built | Zenodo — 7 pollutants |

**Pipeline skeleton:** `config.py`, `schema.py`, `storage/`, `cli.py` ✅

---

## Phase 2: Portal Downloads

| # | Source | Connector | Status | Notes |
|---|---|---|---|---|
| 9 | UN Population WPP 2024 | `un_population.py` | ❌ Not built | Direct CSV, 5-year periods |
| 10 | UNIDO INDSTAT 4 | `unido.py` | ❌ Not built | Manual download helper |
| 11 | UNDP HDR | `undp.py` | ❌ Not built | Manual download helper |
| 12 | FAOSTAT + FBS Bulk | `faostat.py` | ❌ Not built | SDMX API + bulk CSV |
| 13 | Footprint Network NFA 2025 | `footprint_network.py` | ❌ Not built | Requires registration |
| 14 | Energy Inst. Statistical Review | `ei_review.py` | ❌ Not built | Single Excel workbook |
| 15 | Penn World Table 11.0 | `pwt.py` | ❌ Not built | Excel + capital detail file |

---

## Phase 3: Registration Required

| # | Source | Connector | Status | Notes |
|---|---|---|---|---|
| 16 | EIA | `eia.py` | ❌ Not built | Needs API key |
| 17 | FRED | `fred.py` | ❌ Not built | Has API key ✅ |
| 18 | IHME GBD | `ihme_gbd.py` | ❌ Not built | Needs registration |
| 19 | HMD | `hmd.py` | ❌ Not built | Needs registration (1-2 day approval) |

---

## Phase 4: SDMX + Complex APIs

| # | Source | Connector | Status | Notes |
|---|---|---|---|---|
| 20 | OECD | `oecd.py` | ❌ Not built | SDMX via `sdmx1` library |
| 21 | IMF WEO | `imf_weo.py` | ❌ Not built | SDMX or `weo` package |
| 22 | UN Comtrade | `un_comtrade.py` | ❌ Not built | Commodity API v2 |
| 23 | HYDE | `hyde.py` | ❌ Not built | NetCDF or CSV from Kaggle |

---

## Phase 5: Validation Anchors (Optional)

| # | Source | Connector | Status | Notes |
|---|---|---|---|---|
| 24 | NASA GISS | `nasa_giss.py` | ❌ Not built | Text file parsing |
| 25 | Berkeley Earth | `berkeley_earth.py` | ❌ Not built | Text file parsing |
| 26 | Gapminder | `gapminder.py` | ❌ Not built | CSV per indicator |
| 27 | NASA Earthdata | `nasa_earthdata.py` | ❌ Not built | Login required, NetCDF |
| 28 | Climate TRACE | `climate_trace.py` | ❌ Not built | GeoJSON/CSV download |
| 29 | Climate Watch / WRI | `climate_watch.py` | ❌ Not built | CSV download |
| 30 | Global Carbon Atlas | `carbon_atlas.py` | ❌ Not built | NetCDF/GeoTIFF |
| 31 | Maddison (direct) | `maddison.py` | ❌ Not built | Excel download (alt to OWID) |

---

## Spec Calibration Targets → Data Sources

| Spec § | Calibration Variable | NRMSD Bound | Required Source | Status |
|---|---|---|---|---|
| §13.1 | Industrial output (GDP-deflated) | ≤ 0.321 direct | Nebel 2023 + World Bank deflator | ⚠️ Partial (WB deflator ✅, Nebel ❌) |
| §13.1 | Food production | ≤ 0.292 change-rate | Nebel 2023 + FAO FBS | ❌ Not built |
| §13.1 | Service output | ≤ 0.354 direct | Nebel 2023 supplement | ❌ Not built |
| §13.1 | Pollution index | ≤ 0.337 change-rate | Nebel 2023 + GCP + CEDS | ⚠️ Partial (GCP ✅, CEDS ❌) |
| §13.1 | Ecological footprint | ≤ 0.343 direct | NFA 2025 (Footprint Network) | ❌ Needs registration |
| §13.1 | Human welfare (HDI) | ≤ 0.178 direct | IHME GBD + HMD | ❌ Needs registration |
| §8.3 | Nonrenewable stock proxy | ≤ 0.757 change-rate | USGS + UN Comtrade | ❌ Not built |
| §8.2 | Food per capita unit chain | ≤ 1.108 change-rate | FAO FBS bulk + WB deflator | ⚠️ Partial (WB deflator ✅) |
| §15.3 | Industrial capital stock | — | PWT 11.0 (`cn` + asset detail) | ❌ Not built |
| §16.1 (v2.0) | EROI / energy-capital | reserved | EI Stat. Review primary energy | ❌ Not built |
| §16.2 (v2.0) | Distinct mineral stocks | reserved | USGS + UN Comtrade | ❌ Not built |

---

## Pipeline Build Progress

### Storage Layer ✅
- [x] `storage/parquet_store.py` — Raw + aligned Parquet read/write, DuckDB queries
- [x] `storage/metadata_db.py` — SQLite with source_versions, fetch_log, transform_log
- [x] `storage/cache.py` — HTTP cache with TTL, content-hash, params support

### CLI ✅
- [x] `cli.py` — Typer CLI: collect, status, clear, ls-raw, ls-aligned
- [x] `config.py` — PipelineConfig with Pydantic + env var support
- [x] `schema.py` — SourceDef, FetchResult, QualityReport models

### Connectors (3/37 built)
- [x] `world_bank.py` — 4 indicators (population, GDP, GNI, deflator)
- [x] `noaa.py` — Mauna Loa CO₂ annual/monthly
- [x] `gcp.py` — Zenodo GCB 2024 v18 fossil CO₂ emissions
- [ ] 34 remaining connectors — see phase tables above

### Test Fixtures ✅
- [x] `tests/fixtures/unido_indstat4_sample.csv`
- [x] `tests/fixtures/undp_hdr_sample.csv`
- [x] `tests/fixtures/ihme_gbd_sample.csv`
- [x] `tests/fixtures/hmd_life_table_sample.txt`

### Transforms ❌ Not started
- [ ] `transforms/reshape.py`
- [ ] `transforms/interpolation.py`
- [ ] `transforms/aggregation.py`
- [ ] `transforms/deflation.py`
- [ ] `transforms/per_capita.py`
- [ ] `transforms/unit_conversion.py`
- [ ] `transforms/gap_detection.py`
- [ ] `transforms/outlier_detection.py`
- [ ] `transforms/nebcal_transform.py`

### Quality ❌ Not started
- [ ] `quality/coverage.py`
- [ ] `quality/freshness.py`
- [ ] `quality/consistency.py`
- [ ] `quality/report.py`

### Export ❌ Not started
- [ ] `export/connector_result.py`
- [ ] `export/calibration_csv.py`
- [ ] `export/manifest.py`

---

## Bugs Fixed During Execution

1. **`cache.py` missing `params` support** — `requests.get()` wasn't receiving query parameters, causing World Bank to return XML instead of JSON. Fixed by adding `params` parameter to `fetch_with_cache()`.
2. **World Bank `Accept` header** — API returns XML by default. Fixed by adding `Accept: application/json` header.
3. **GCP URL** — Original XLSX URL was 404. Found correct CSV on Zenodo via API (`GCB2024v18_MtCO2_flat.csv/content`).

---

## What to Do Next

### You (now):
1. [ ] Get EIA API key from https://www.eia.gov/opendata/register.php
2. [ ] Register Footprint Network account
3. [ ] Register IHME GBD account
4. [ ] Register HMD account (1-2 day approval — do this first)
5. [ ] Update `.env` with EIA key when you get it

### Next coding session:
1. [ ] Build remaining Phase 1 connectors: OWID, USGS, PRIMAP, CEDS, Nebel 2023
2. [ ] Implement reshape + interpolation transforms
3. [ ] Implement transform dependency graph in `pipeline.py`
