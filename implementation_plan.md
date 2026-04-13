# Implementation Plan: W3-03 Calibration Fix + Data Pipeline Integration

## Goal

Fix all pyWorldX sector implementations to match the canonical World3-03 model (from `wrld3-03.mdl`), then build the bridge between the data_pipeline and the engine's calibration system.

## User Review Required

> [!IMPORTANT]
> **Scope Decision**: This plan prioritizes fixing table values and adding missing structural elements within the existing simplified sector architecture. It does NOT propose rewriting sectors to full W3-03 fidelity (e.g., 4-cohort population). The simplified structures are kept but with correct parameters.

> [!WARNING]
> **Phase 1 will change simulation behavior.** Every sector's output trajectories will change — some significantly (pollution, capital). Existing test baselines will need updating.

---

## Phase 1: Fix Engine Tables & Constants (Critical Path)

All changes sourced from the canonical `wrld3-03.mdl` (Vensim revision September 29, 2005).

---

### Resources Sector

#### [MODIFY] [resources.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/resources.py)

1. **Fix PCRUM table** to W3-03 values:
   - X: `(0, 200, 400, 600, 800, 1000, 1200, 1400, 1600)` 
   - Y: `(0, 0.85, 2.6, 3.4, 3.8, 4.1, 4.4, 4.7, 5.0)`
2. **Fix FCAOR1 table** to W3-03 values:
   - Y: `(1, 0.9, 0.7, 0.5, 0.2, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05)`
3. **Add FCAOR2 table**:
   - Y: `(1, 0.2, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05)`
4. **Add NRUF dynamic system**:
   - `NRUF = clip(NRUF2, NRUF1, t, POLICY_YEAR)`
   - `NRUF1 = 1.0` (constant before policy year)
   - `NRUF2 = SMOOTH3(RCT, TDD)` (delayed technology)
5. **Add Resource Conservation Technology stock**:
   - `RCT = INTEG(RTCR, 1.0)`
   - `RTCR = IF(t >= POLICY_YEAR, RCT * RTCM, 0)`
   - `RTCM = table_lookup(1 - NRUR/DRUR, [(-1,0),(0,0)])` (no change in base run)
6. **Add constants**: `DRUR = 4.8e9`, `TDD = 20`, `FCAOR_switch_time = 4000`, `POLICY_YEAR = 4000`
7. **Fix NRUR equation**: `NRUR = POP * PCRUM * NRUF` (was using `pcnr_use_base`)
8. **Remove** `pcnr_use_base` parameter (replaced by NRUF system)
9. **Add writes**: `fcaor` (fraction of capital to obtaining resources — consumed by capital sector)

---

### Pollution Sector

#### [MODIFY] [pollution.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/pollution.py)

1. **Fix AHLM table** to W3-03 values:
   - X: `(1, 251, 501, 751, 1001)` 
   - Y: `(1, 11, 21, 31, 41)`
2. **Fix base_absorption_time**: `1.5` (was 20.0) — this is AHL70
3. **Fix absorption equation**: `PPOL / (AHL * 1.4)` (W3-03 uses factor 1.4)
4. **Fix pollution generation equation** to use PCRUM chain:
   - Industrial: `PCRUM * POP * FRPM * IMEF * IMTI` where FRPM=0.02, IMEF=0.1, IMTI=10
   - Agricultural: `AIPH * AL * FIPM * AMTI` where FIPM=0.001, AMTI=1
   - Total: `(ind + ag) * PPGF`
5. **Add PPGF** (persistent pollution generation factor): `= 1` in base run
6. **Add DELAY3** for pollution appearance: 20-year transmission delay
7. **Remove** custom `_PPGIO` and `_PE` tables (not in W3-03)
8. **Add constants**: `FRPM=0.02`, `IMEF=0.1`, `IMTI=10`, `AMTI=1`, `FIPM=0.001`, `PPTD=20`

---

### Capital Sector

#### [MODIFY] [capital.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/capital.py)

1. **Fix IC depreciation rate**: `1/14 ≈ 0.0714` (ALIC=14 years, was 0.05)
2. **Fix IO equation** to include FCAOR:
   - `IO = IC * (1 - FCAOR) * CUF / ICOR`
   - Read `fcaor` from resources sector (new dependency)
   - `CUF = 1.0` initially (simplification — full CUF requires jobs subsector)
3. **Fix FIOAS table** Y-values: `(0.3, 0.2, 0.1, 0.05, 0)` (was `(0.30,0.25,0.22,0.20,0.18)`)
4. **Replace FIOAI** with residual calculation: `FIOAI = 1 - FIOAA - FIOAS - FIOAC`
   - Add `FIOAC = 0.43` constant (fraction to consumption, base run)
5. **Add FIOAC variable table** (FIAOCV): `(0.3,0.32,0.34,0.36,0.38,0.43,0.73,0.77,0.81,0.82,0.83)`
6. **Remove** `_ICOR_PP` table (not in W3-03)
7. **Update reads**: add `fcaor` from resources, `food_per_capita` for FIOAA

---

### Agriculture Sector

#### [MODIFY] [agriculture.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/agriculture.py)

1. **Fix LYMC table** to full 26-point W3-03 table:
   - X: `(0,40,80,120,...,1000)` — 26 points
   - Y: `(1,3,4.5,5,5.3,5.6,5.9,6.1,6.35,6.6,6.9,7.2,7.4,7.6,7.8,8,8.2,8.4,8.6,8.8,9,9.2,9.4,9.6,9.8,10)`
2. **Fix FIOAA table** Y-values: `(0.4, 0.2, 0.1, 0.025, 0, 0)` (was `(0.40,0.30,0.22,0.15,0.10,0.08)`)
3. **Fix food equation**: `food = AL * land_yield * LFH * (1 - PL)` where LFH=0.7, PL=0.1
4. **Replace** `_LYPM` with W3-03 LYMAP tables (air pollution effect):
   - LYMAP1: `(0,1),(10,1),(20,0.7),(30,0.4)` — input is IO/IO70
5. **Replace** `_LERM` with W3-03 land life system:
   - LLMY1 table: `(0,1.2,1.0,0.63,0.36,0.16,0.055,0.04,0.025,0.015,0.01)`
6. **Add constants**: `LFH = 0.7`, `PL = 0.1`, `IO70 = 7.9e11`, `SFPC = 230`
7. **Add initial land fertility**: `LFERT0 = 600` (same as base_land_yield — this is correct)

---

### Population Sector

#### [MODIFY] [population.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/population.py)

1. **Fix LMHS**: Implement switching at t=1940:
   - Before 1940: LMHS1 Y = `(1, 1.1, 1.4, 1.6, 1.7, 1.8)`
   - After 1940: LMHS2 Y = `(1, 1.5, 1.9, 2.0, 2.0, 2.0)`
2. **Keep simplified CBR/CDR** approach but add note that this is an approximation
3. **Update metadata**: Change `validation_status` to `APPROXIMATION` (was `REFERENCE_MATCHED`)

---

### Adaptive Technology Sector

#### [MODIFY] [adaptive_technology.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/adaptive_technology.py)

1. **Add note** that this is a pyWorldX extension, not in W3-03
2. **Update metadata**: Change `equation_source` to `PYWORLDX_EXTENSION` (not `MEADOWS_SPEC`)
3. **Add constant** `POLICY_YEAR = 4000` (default — technology doesn't activate in base run)
4. **Ensure outputs default to 1.0** when POLICY_YEAR has not been reached

---

### Calibration Parameters

#### [MODIFY] [parameters.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/parameters.py)

1. **Fix** `population.base_life_expectancy`: default `28.0` (was 32.0)
2. **Fix** `capital.ic_depreciation_rate`: default `0.0714` (was 0.05), bounds `(0.05, 0.10)`
3. **Fix** `pollution.base_absorption_time`: default `1.5` (was 20.0), bounds `(0.5, 5.0)`
4. **Fix** `pollution.industrial_pollution_intensity`: default `0.02` (was 0.01)
5. **Remove** `population.food_le_multiplier` (not a W3-03 parameter)
6. **Remove** `resources.pcnr_use_base` (replaced by NRUF system)
7. **Add** `resources.policy_year`: default `4000`, bounds `(1975, 4000)`
8. **Add** `resources.nri`: default `1e12`, bounds `(5e11, 2e12)`

---

## Phase 2: Data Pipeline ↔ Engine Bridge

### DataBridge Module

#### [NEW] [bridge.py](file:///Users/johnny/pyWorldX/pyworldx/data/bridge.py)

- `CalibrationTarget` dataclass: variable_name, years, values, unit, weight, source
- `DataBridge` class: loads aligned Parquet data, maps entities to engine variables, builds NRMSD objective
- `ENTITY_TO_ENGINE_MAP` constant: maps pipeline entity names to engine variable names
- Normalization logic: both engine and observed data normalized to 1970 baseline

#### [NEW] [world3_reference.py](file:///Users/johnny/pyWorldX/data_pipeline/connectors/world3_reference.py)

- Parses `wrld3-03.mdl` table functions into structured dict
- Stores canonical table values as embedded JSON
- Provides `fetch()` interface returning W3-03 reference trajectories
- Links to PyWorld3-03 validation data as secondary source

#### [MODIFY] [map.py](file:///Users/johnny/pyWorldX/data_pipeline/alignment/map.py)

- Add `world3_reference` source mappings for all 5 sector variables
- Map reference trajectories to canonical entity names

---

### Empirical Calibration Runner

#### [NEW] [empirical.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/empirical.py)

- `EmpiricalCalibrationRunner` class
- Loads targets from DataBridge
- Builds composite NRMSD objective function
- Runs full calibration pipeline (profile likelihood → Morris → Nelder-Mead → Sobol)
- Reports per-variable and composite NRMSD scores

---

## Phase 3: USGS Cross-Validation

#### [MODIFY] [usgs.py](file:///Users/johnny/pyWorldX/data_pipeline/connectors/usgs.py)

- Add `resource_extraction_index` variable: aggregated world production index (1996=100)
- Add `reserve_depletion_ratio` variable: weighted average cumulative_extraction/reserves
- These map to `resources.nrur_proxy` and `resources.nrfr_proxy` in the ontology

#### [MODIFY] [map.py](file:///Users/johnny/pyWorldX/data_pipeline/alignment/map.py)

- Add USGS proxy entity mappings

---

## Open Questions

> [!IMPORTANT]
> **Q1: Baseline year for calibration?**
> Most empirical data starts in 1960. Recommend (a): calibrate against 1960-2024, run from 1900 with W3-03 initial conditions.

> [!IMPORTANT]
> **Q2: Which scenarios to support initially?**
> Recommend (b): Standard Run only (POLICY_YEAR=4000). Scenario system can be added later via parameter presets.

> [!IMPORTANT]
> **Q3: NRMSD weighting?**
> Recommend (a): equal weights initially, then refine with Sobol sensitivity analysis.

---

## Verification Plan

### Automated Tests

1. **Table value tests**: For each sector, assert that every lookup table matches the MDL canonical values exactly
2. **Initial condition smoke test**: Run engine 1 timestep, verify IO/POP/food are non-zero and reasonable
3. **Conservation test**: Verify NR stock depletion equals cumulative extraction
4. **Reference comparison**: Run base scenario 1900-2100, compare against PyWorld3-03 validation data via NRMSD
5. **Regression tests**: Update existing test baselines to new table values

### Manual Verification

- Plot key trajectories (POP, IO, NR, PPOL, food) against PyWorld3-03 reference
- Verify qualitative behavior: S-shaped population, industrial peak, resource depletion
- Compare pollution dynamics — should now show correct nonlinear absorption scaling

---

## References & External Sources

### Primary Source for All Table Values

1. **`wrld3-03.mdl`** — Every table value, constant, and equation in Phase 1 of this plan is sourced from this file.
   - URL: `https://vensim.com/documentation/Models/Sample/WRLD3-03/wrld3-03.mdl`
   - Revision: September 29, 2005
   - Format: Plain text (Vensim `.mdl`)

### Cross-Reference Sources

2. **PyWorld3-03** — Python reference implementation. Use to validate our corrected tables produce matching trajectories.
   - GitHub: `https://github.com/cvanwynsberghe/pyworld3`
   - Validation notebook: `https://github.com/cvanwynsberghe/pyworld3/blob/master/notebooks/world3_standard_run.ipynb`

3. **MetaSD World3-03 model package** — Alternative download of the same model files.
   - URL: `https://metasd.com/2010/04/world3-03/`

### Books (for equation number cross-references)

4. **Meadows, D.H., Randers, J. & Meadows, D.L. (2004).** *Limits to Growth: The 30-Year Update.* Chelsea Green Publishing.
   - ISBN: 978-1-931498-58-6
   - Describes all structural additions to W3-03 (RCT, PPT, LYT technology stocks, POLICY_YEAR switching)

5. **Meadows, D.L. et al. (1974).** *Dynamics of Growth in a Finite World.* Wright-Allen Press.
   - ISBN: 978-0-96040-0-4
   - Equation numbers in MDL comments (e.g., `PCRUM#130`, `FCAOR#135`, `AHLM#145.1`) refer to this book

6. **Herrington, G. (2021).** "Update to limits to growth." *Journal of Industrial Ecology*, 25(3), 614–626.
   - DOI: `https://doi.org/10.1111/jiec.13084`
   - Provides empirical validation data (2020) for comparison after table fixes

### Data Sources for Phase 2 & 3

7. **World Bank Open Data** — Population, GDP, manufacturing VA.
   - URL: `https://data.worldbank.org/`

8. **FAOSTAT** — Food supply, arable land, agricultural inputs.
   - URL: `https://www.fao.org/faostat/en/`

9. **EDGAR** — CO2 emissions by sector.
   - URL: `https://edgar.jrc.ec.europa.eu/`

10. **NOAA Mauna Loa CO2** — Atmospheric CO2.
    - URL: `https://gml.noaa.gov/ccgg/trends/data.html`

11. **USGS Mineral Commodity Summaries** — Production and reserves for 93 minerals.
    - URL: `https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries`

12. **Penn World Tables** — Capital stocks, GDP.
    - URL: `https://www.rug.nl/ggdc/productivity/pwt/`

13. **Maddison Project Database** — Historical GDP (1820-2022).
    - URL: `https://www.rug.nl/ggdc/historicaldevelopment/maddison/`

14. **Global Carbon Project** — Global carbon budget.
    - URL: `https://www.globalcarbonproject.org/carbonbudget/`

15. **UNDP Human Development Reports** — HDI data.
    - URL: `https://hdr.undp.org/data-center/human-development-index`

### Internal Project Files Modified by This Plan

16. **Engine sector files** (Phase 1 targets):
    - [resources.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/resources.py)
    - [pollution.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/pollution.py)
    - [capital.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/capital.py)
    - [agriculture.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/agriculture.py)
    - [population.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/population.py)
    - [adaptive_technology.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/adaptive_technology.py)
    - [parameters.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/parameters.py)

17. **Pipeline integration files** (Phase 2 & 3 targets):
    - [bridge.py](file:///Users/johnny/pyWorldX/pyworldx/data/bridge.py) — NEW
    - [world3_reference.py](file:///Users/johnny/pyWorldX/data_pipeline/connectors/world3_reference.py) — NEW
    - [empirical.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/empirical.py) — NEW
    - [usgs.py](file:///Users/johnny/pyWorldX/data_pipeline/connectors/usgs.py) — MODIFY
    - [map.py](file:///Users/johnny/pyWorldX/data_pipeline/alignment/map.py) — MODIFY

### Companion Reports

18. **Calibration Audit Report** — Full sector-by-sector table comparison:
    - [resource_integration_report.md](file:///Users/johnny/.gemini/antigravity/brain/c2b94c59-5a81-44ff-a197-801491893a27/resource_integration_report.md)

19. **Data Pipeline Integration Report** — Architecture gap analysis and connector mapping:
    - [data_pipeline_integration_report.md](file:///Users/johnny/.gemini/antigravity/brain/c2b94c59-5a81-44ff-a197-801491893a27/data_pipeline_integration_report.md)
