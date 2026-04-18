# Non-Renewable Resources & World3-03 Calibration Audit Report

## Executive Summary

A line-by-line audit of every pyWorldX sector against the canonical Vensim `wrld3-03.mdl` file reveals that **none of our sectors are accurately calibrated to World3-03**. All five sectors contain a mixture of pre-2004 World3 tables, invented table shapes not found in any World3 version, and missing structural elements. The resource sector is the worst offender, but the problem is systemic.

---

## Part 1: Sector-by-Sector Audit

### Key: Version Attribution

| Tag | Meaning |
|---|---|
| **W3-72** | Original World3 (1972, "Limits to Growth") |
| **W3-03** | World3-03 (2004, "Limits to Growth: The 30-Year Update") |
| **CUSTOM** | Values invented for pyWorldX, not found in any World3 version |
| **MATCH** | Matches the canonical W3-03 `.mdl` file |

---

### 1.1 Population Sector ([population.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/population.py))

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| `_NORMAL_LE` | 28.0 | 28 | W3-03 | ✅ **MATCH** |
| `_LMFT` (food→LE) X | `(0,1,2,3,4,5)` | `(0,1,2,3,4,5)` | W3-03 | ✅ MATCH |
| `_LMFT` Y | `(0,1,1.43,1.5,1.5,1.5)` | `(0,1,1.43,1.5,1.5,1.5)` | W3-03 | ✅ **MATCH** |
| `_LMHS` (health→LE) X | `(0,20,40,60,80,100)` | `(0,20,40,60,80,100)` | Same | ✅ MATCH |
| `_LMHS` Y | `(1,1.4,1.6,1.8,1.95,2.0)` | **LMHS1**: `(1,1.1,1.4,1.6,1.7,1.8)` / **LMHS2**: `(1,1.5,1.9,2.0,2.0,2.0)` | **CUSTOM** | ❌ **WRONG** |
| `_LMPP` (pollution→LE) | `(1,.99,.97,.95,.90,.85,.75,.65,.55,.40,.20)` | `(1,.99,.97,.95,.90,.85,.75,.65,.55,.40,.20)` | W3-03 | ✅ **MATCH** |
| `_CBR` table | `(0.04,0.035,0.030,...)` | **Not in W3-03** — births use `total_fertility * POP / reproductive_lifetime` | **CUSTOM** | ❌ **INVENTED** |
| `_DFS` table | `(0.035,0.025,0.020,...)` | **Not in W3-03** — desired family size uses `SFSN`, `CMPLE`, `FRSN` tables | **CUSTOM** | ❌ **INVENTED** |
| `initial_population` | 1.65e9 | **Not a single stock** — W3-03 uses 4 age cohorts: P1=6.5e8, P2=7e8, P3=1.9e8, P4=6e7 | **CUSTOM** | ⚠️ **APPROXIMATION** |

> [!CAUTION]
> **Critical issue: LMHS switching**. World3-03 switches between LMHS1 (pre-1940) and LMHS2 (post-1940) at t=1940. Our code uses a single LMHS table that is neither LMHS1 nor LMHS2 — it's a blend. This materially affects life expectancy trajectory.

> [!WARNING]
> **The CBR and DFS tables are entirely invented.** World3-03 does not use a crude birth rate table. Instead, births are computed from: `births = POP_15_to_44 / reproductive_lifetime * 0.5 * total_fertility`. The `total_fertility` chain involves 7+ interconnected table functions (FM, CMPLE, SFSN, FRSN, FCE, FSAFC, NFC). Our simplified `cbr(iopc)` shortcut fundamentally changes the model's birth dynamics.

**Structural elements missing:**
- 4-cohort age structure (0-14, 15-44, 45-64, 65+)
- All 4 mortality tables (M1-M4)
- Total fertility chain (SFSN, CMPLE, FM, FRSN, FCE, NFC, FSAFC)
- Perceived life expectancy (SMOOTH3)
- Income expectation delayed variables
- Social family size / family response system

---

### 1.2 Capital Sector ([capital.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/capital.py))

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| `initial_ic` | 2.1e11 | 2.1e11 | W3-03 | ✅ MATCH |
| `initial_sc` | 1.44e11 | 1.44e11 | W3-03 | ✅ MATCH |
| `icor` | 3.0 | 3.0 (ICOR1) | W3-03 | ✅ MATCH |
| `scor` | 1.0 | 1.0 (SCOR1) | W3-03 | ✅ MATCH |
| `ic_depreciation_rate` | 0.05 (1/20yr) | 1/14 ≈ 0.0714 (ALIC1=14 years) | **WRONG** | ❌ **WRONG** |
| `sc_depreciation_rate` | 0.05 (1/20yr) | 1/20 = 0.05 (ALSC1=20 years) | W3-03 | ✅ MATCH |
| `_FIOAI` table | `(0.60,0.55,...,0.30)` | **Not in W3-03** — FIOAI = 1 - FIOAA - FIOAS - FIOAC (residual) | **CUSTOM** | ❌ **INVENTED** |
| `_FIOAS` table X | `(0,0.5,1.0,1.5,2.0)` | `(0,0.5,1.0,1.5,2.0)` | W3-03 | ✅ MATCH |
| `_FIOAS` table Y | `(0.30,0.25,0.22,0.20,0.18)` | `(0.3,0.2,0.1,0.05,0)` | **CUSTOM** | ❌ **WRONG** |
| `_ICOR_PP` table | `(1.0,0.95,0.85,0.70,0.50,0.30)` | **Not in W3-03 in this form** | **CUSTOM** | ❌ **INVENTED** |
| Industrial output equation | `IC / effective_icor` | `IC * (1-FCAOR) * CUF / ICOR` | **CUSTOM** | ❌ **WRONG** |

> [!CAUTION]
> **Capital sector is fundamentally mis-structured:**
> 1. **IC depreciation rate**: W3-03 uses ALIC=14 years → depreciation=0.0714/yr. We use 0.05 (20yr lifetime). This is a **43% error** in depreciation rate.
> 2. **IO equation**: W3-03 computes IO = IC × (1 - FCAOR) × CUF / ICOR. Our code ignores FCAOR entirely (the resource-cost feedback) and has no CUF (capacity utilization fraction). The FCAOR feedback is the primary mechanism by which resource depletion causes industrial collapse — missing it breaks the resource-capital feedback loop.
> 3. **Investment fraction**: W3-03 computes FIOAI as a residual: `1 - FIOAA - FIOAS - FIOAC`. We invented a separate table that doesn't match any W3 version.

**Structural elements missing:**
- FCAOR feedback in IO equation (critical!)
- Capacity utilization fraction (CUF) from labor market
- FIOAC (consumption allocation) with FIAOCV table
- ICOR2 technology-driven capital output ratio
- Jobs subsector (JPICU, JPSCU, JPH, LUF, DLUFD)
- Industrial equilibrium time logic
- POLICY_YEAR switching for all tables

---

### 1.3 Agriculture Sector ([agriculture.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/agriculture.py))

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| `initial_arable_land` | 0.9e9 | 0.9e9 | W3-03 | ✅ MATCH |
| `potential_arable_land` | 3.2e9 | 3.2e9 | W3-03 | ✅ MATCH |
| `base_land_yield` | 600 | 600 (initial land fertility) | W3-03 | ✅ MATCH |
| `_LYMC` X | `(0,40,80,...,320)` — 9 points | `(0,40,80,...,1000)` — **26 points** | **TRUNCATED** | ❌ **WRONG** |
| `_LYMC` Y | `(1,3,4.5,5.0,...,5.95)` | `(1,3,4.5,5,...,10)` | **TRUNCATED** | ❌ **WRONG** |
| `_LYPM` table | `(1.0,0.97,0.90,0.75,0.50)` | **Not in W3-03 directly** — uses LYMAP1/LYMAP2 as f(IO/IO70) | **CUSTOM** | ❌ **INVENTED** |
| `_LERM` table | `(0,0.005,0.01,...,0.05)` | **Not in W3-03** — land erosion uses land life via LLMY tables | **CUSTOM** | ❌ **INVENTED** |
| `_FIOAA` X | `(0,0.5,1.0,1.5,2.0,2.5)` | `(0,0.5,1.0,1.5,2.0,2.5)` | W3-03 | ✅ MATCH |
| `_FIOAA` Y | `(0.40,0.30,0.22,0.15,0.10,0.08)` | `(0.4,0.2,0.1,0.025,0,0)` | **CUSTOM** | ❌ **WRONG** |
| Food equation | `AL * land_yield` | `LY * AL * LFH * (1-PL)` | **CUSTOM** | ❌ **WRONG** |

> [!WARNING]
> **Agriculture LYMC table is severely truncated.** W3-03 has a 26-point table going from AIPH=0 to 1000, with yields reaching 10×. Our 9-point table stops at 320 and caps at 5.95×. This means our model will systematically underestimate food production as agricultural inputs increase.

> [!WARNING]
> **FIOAA values are wrong.** W3-03's FIOAA reaches 0 at FPC/IFPC=2.0 (food satiation = no more ag investment). Our table bottoms at 0.08 — we never stop investing in agriculture.

**Structural elements missing:**
- Land fertility stock (separate from land yield)
- Land fertility degradation from pollution (LFDR)
- Land fertility regeneration (LFR/LFRT)
- All 6 agriculture loops from W3-03
- Land fraction harvested (0.7)
- Processing loss (0.1)
- AIPH (agricultural input per hectare) chain
- Land development cost curve (DCPH)
- Fraction of inputs to land maintenance (FALM)
- Marginal productivity framework

---

### 1.4 Pollution Sector ([pollution.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/pollution.py))

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| `initial_ppol` | 2.5e7 | 2.5e7 | W3-03 | ✅ MATCH |
| `ppol_1970` | 1.36e8 | 1.36e8 | W3-03 | ✅ MATCH |
| `_PPGIO` table | `(0,0.1,0.3,0.5,0.7,0.8)` | **Not in W3-03** — PPGIO = PCRUM × POP × FRPM × IMEF × IMTI | **CUSTOM** | ❌ **INVENTED** |
| `_AHLM` X | `(1,2,5,10,20,50,100)` — 7 pts | `(1,251,501,751,1001)` — 5 pts | **WRONG** | ❌ **WRONG** |
| `_AHLM` Y | `(1,1.2,1.5,2.0,3.0,5.0,8.0)` | `(1,11,21,31,41)` | **WRONG** | ❌ **WRONG** |
| `base_absorption_time` | 20.0 | 1.5 (AHL70=1.5 yrs) | **WRONG** | ❌ **WRONG** |
| `_PE` table | Same as `_LMPP` | **Not in W3-03** — pollution_efficiency doesn't exist directly | **CUSTOM** | ❌ **INVENTED** |
| Pollution gen equation | `IO * intensity * ppgio + food * ag_intensity` | `(PPGIO_ind + PPGAO_ag) × PPGF` (uses NRUR not IO) | **CUSTOM** | ❌ **WRONG** |
| Absorption equation | `PPOL / absorption_time` | `PPOL / (AHL × 1.4)` | **CUSTOM** | ❌ **WRONG** |

> [!CAUTION]
> **AHLM table is catastrophically wrong.** The MDL table maps pollution index `(1,251,501,751,1001)` → multiplier `(1,11,21,31,41)`. Our table maps `(1,2,5,10,20,50,100)` → `(1,1.2,1.5,2,3,5,8)`. This means at high pollution levels, our model's absorption time barely changes, while W3-03's absorption time increases **41×**. This completely changes the pollution dynamics — the W3-03 model has a massive nonlinearity that makes persistent pollution truly persistent.

> [!CAUTION]
> **Base absorption time is 13× too high.** W3-03 uses AHL70=1.5 years (half-life). Our code uses 20 years. With the wrong AHLM table on top, our pollution dynamics are fundamentally broken.

**Structural elements missing:**
- PPGIO is computed from resource usage (PCRUM×POP), not IO directly
- PPGAO uses agricultural input per hectare, not food
- Persistent pollution generation factor (PPGF) with technology switching
- DELAY3 for pollution appearance rate (transmission delay = 20yr)
- Persistent Pollution Technology stock (for scenarios)
- Factor of 1.4 in absorption rate
- FRPM (0.02), IMEF (0.1), IMTI (10), AMTI (1), FIPM (0.001) constants

---

### 1.5 Resources Sector ([resources.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/resources.py))

*(Detailed in previous report — summary here)*

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| `initial_nr` | 1.0e12 | 1.0e12 | W3-03 | ✅ MATCH |
| `_PCRUM` X | `(0,10,20,40,...,150)` | `(0,200,400,...,1600)` | **CUSTOM** | ❌ **WRONG** |
| `_PCRUM` Y | `(0,0.85,2.6,4.4,...,7.0)` | `(0,0.85,2.6,3.4,...,5.0)` | **Pre-2004** | ❌ **WRONG** |
| `_FCAOR` Y | `(1,.9,.7,.5,.3,.15,.08,.05,.03,.02,.01)` | **FCAOR1**: `(1,.9,.7,.5,.2,.1,.05,.05,.05,.05,.05)` | **CUSTOM** | ❌ **WRONG** |
| FCAOR2 | Not implemented | Different table with early saturation | — | ❌ **MISSING** |
| NRUF system | Not implemented | `clip(NRUF2, 1, t, PYEAR)` | — | ❌ **MISSING** |
| NRUR equation | `POP × PCRUM × pcnr_base` | `POP × PCRUM × NRUF` | **CUSTOM** | ❌ **WRONG** |

---

### 1.6 Adaptive Technology Sector ([adaptive_technology.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/adaptive_technology.py))

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| All 5 table functions | Custom tables | **Not in W3-03 as a single sector** | **CUSTOM** | ❌ **INVENTED** |
| Sector structure | Single TECH stock | W3-03 has 3 separate tech stocks: RCT, PPT, LYT | **CUSTOM** | ❌ **WRONG** |

> [!IMPORTANT]
> **The adaptive technology sector is entirely custom.** World3-03 does NOT have a unified technology sector. Instead, it has three separate technology systems embedded in their respective sectors:
> 1. **Resource Conservation Technology** (in Resource sector) — stock RCT with RTCR/RTCM
> 2. **Persistent Pollution Technology** (in Pollution sector) — stock PPT with PTCR/PTCM
> 3. **Land Yield Technology** (in Agriculture sector) — stock LYT with LYTCR/LYTCM
>
> Each has its own `POLICY_YEAR` switch, its own change rate multiplier table, and its own SMOOTH3 delay. Our unified sector fundamentally changes how technology responds to crises.

---

### 1.7 Welfare Sector ([welfare.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/welfare.py))

| Variable | Our Value | MDL Value (W3-03) | Attribution | Verdict |
|---|---|---|---|---|
| HWI equation | Geometric mean of 3 components | W3-03 uses `HWI = (LE_index + education_index + GDP_index) / 3` | **CUSTOM** | ⚠️ **DIFFERENT** |
| HEF equation | Custom footprint sum | W3-03 uses `HEF = ALIC + PPOL_footprint + URBAN_land` | **CUSTOM** | ⚠️ **DIFFERENT** |
| All 6 tables | Custom tables | Supplementary variables in MDL, simpler formulas | **CUSTOM** | ⚠️ **DIFFERENT** |

The welfare sector is mostly observational, so discrepancies here don't affect system dynamics but they do affect validation comparisons.

---

### 1.8 Calibration Parameters ([parameters.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/parameters.py))

| Parameter | Our Default | MDL Value | Verdict |
|---|---|---|---|
| `population.base_life_expectancy` | 32.0 | 28.0 (LEN) | ❌ **WRONG** |
| `population.food_le_multiplier` | 10.0 | Not a parameter — it's the LMFT table | ❌ **INVENTED** |
| `capital.ic_depreciation_rate` | 0.05 | 1/14 ≈ 0.0714 | ❌ **WRONG** |
| `pollution.base_absorption_time` | 20.0 | 1.5 (AHL70) | ❌ **CATASTROPHICALLY WRONG** |
| `pollution.industrial_pollution_intensity` | 0.01 | FRPM×IMEF×IMTI = 0.02×0.1×10 = 0.02 | ❌ **WRONG** |

---

## Part 2: Why the Discrepancies?

### Explanation of patterns observed:

1. **Pre-2004 tables mixed with 2004 constants**: The PCRUM table Y-values `(0,0.85,2.6,4.4,5.4,6.2,6.8,7.0)` match the original 1972 World3, not World3-03 which recalibrated them downward. This suggests tables were copied from an older source.

2. **Simplified structural substitutions**: Where World3-03 uses multi-stage computation chains (e.g., 7-table fertility chain), our code substitutes single lookup tables. This was likely done to get a working prototype quickly, but the dynamic behavior differs significantly.

3. **Missing X-axis scaling**: Our PCRUM X-axis uses `(0,10,20,40,...,150)` while the MDL uses `(0,200,400,...,1600)`. In the MDL, IOPC is in $/person/year, computed as IO/POP. With POP≈1.65e9 and IO≈7e10, IOPC≈42 in 1900. Our X-axis was likely rescaled to match this, but the Y-values were kept from the wrong source.

4. **Invented approximation tables**: Tables like `_CBR`, `_ICOR_PP`, `_PPGIO`, and all adaptive technology tables don't correspond to any World3 version. They appear to be reasonable-looking approximations designed to produce qualitatively correct behavior.

---

## Part 3: Impact Assessment

### Severity Ranking

| # | Issue | Impact | Severity |
|---|---|---|---|
| 1 | Pollution AHLM table + AHL70 | Pollution dynamics fundamentally broken — absorption doesn't scale with pollution level | 🔴 **CRITICAL** |
| 2 | Missing FCAOR in IO equation | Resource-capital feedback loop broken — depletion can't cause industrial decline | 🔴 **CRITICAL** |
| 3 | IC depreciation rate (0.05 vs 0.0714) | Capital grows too fast, IO trajectory diverges | 🟡 **HIGH** |
| 4 | Population CBR invented | Birth dynamics qualitatively different | 🟡 **HIGH** |
| 5 | FIOAS/FIOAA tables wrong | IO allocation among sectors incorrect | 🟡 **HIGH** |
| 6 | LYMC truncated | Ag output saturates too early | 🟡 **HIGH** |
| 7 | PCRUM values (pre-2004) | Resource usage 40% too high | 🟡 **HIGH** |
| 8 | Unified adaptive tech sector | Technology response dynamics differ | 🟠 **MEDIUM** |
| 9 | LMHS no switching at 1940 | Life expectancy trajectory slightly off 1900-1940 | 🟠 **MEDIUM** |
| 10 | Missing age cohorts | Demographic momentum absent | 🟠 **MEDIUM** |

---

## Part 4: Recommended Path Forward

### Option A: Full W3-03 Fidelity (Recommended)

Rewrite all sectors to precisely match the Vensim `.mdl`. This gives us:
- Exact table values from the authoritative source
- Complete structural elements (all feedback loops)
- Ability to validate against PyWorld3-03 runs
- Foundation for USGS/empirical data overlay

### Option B: Progressive Refinement

Fix the most critical issues first (AHLM, FCAOR, IC depreciation) while keeping simplified structures. Risk: perpetual technical debt and unreliable calibration.

### Priority 1 Fixes (Critical path):
1. Fix pollution AHLM table and AHL70 constant
2. Add FCAOR to IO equation
3. Fix IC depreciation to 1/14
4. Fix PCRUM table to W3-03 values
5. Fix FIOAS and FIOAA tables

### Priority 2 Fixes (Structural):
6. Add FCAOR1/FCAOR2 switching
7. Add NRUF/RCT system to resources
8. Fix food equation (add LFH, PL)
9. Fix pollution generation (use NRUR, not IO)
10. Split adaptive tech into 3 sector-embedded systems

---

## Appendix: MDL Table Cross-Reference

All canonical table values are from the fetched `wrld3-03.mdl` (Vensim revision date: September 29, 2005).

| MDL Table Name | MDL Section | Our Variable | Match? |
|---|---|---|---|
| LMFT | Population.Death | `_LMFT` | ✅ |
| LMHS1T | Population.Death | `_LMHS` (partial) | ❌ |
| LMHS2T | Population.Death | `_LMHS` (partial) | ❌ |
| LMPT | Population.Death | `_LMPP` | ✅ |
| CMIT | Population.Death | N/A | ❌ Missing |
| FPUT | Population.Death | N/A | ❌ Missing |
| PCRUMT | Resource | `_PCRUM` | ❌ |
| FCAOR1T | Resource | `_FCAOR` (partial) | ❌ |
| FCAOR2T | Resource | N/A | ❌ Missing |
| NRCMT | Resource | N/A | ❌ Missing |
| LYMCT | Agriculture.Loop2 | `_LYMC` (truncated) | ❌ |
| FIOAA1T | Agriculture.Loop1 | `_FIOAA` | ❌ |
| DCPHT | Agriculture.Loop1 | N/A | ❌ Missing |
| FIOAS1T | Capital.Service | `_FIOAS` | ❌ |
| FIAOCVT | Capital.Industry | N/A | ❌ Missing |
| CUFT | Capital.Jobs | N/A | ❌ Missing |
| AHLMT | Pollution | `_AHLM` | ❌ |
| LFDRT | Agriculture.Loop4 | N/A | ❌ Missing |
| FALMT | Agriculture.Loop6 | N/A | ❌ Missing |

---

## References & External Sources

### Primary Source: Vensim World3-03 Model File

1. **`wrld3-03.mdl`** — The authoritative, machine-readable World3-03 model file hosted on the Vensim documentation server. Contains all equations, table functions, constants, and initial conditions. This is the single source of truth for every table value cited in this report.
   - URL: `https://vensim.com/documentation/Models/Sample/WRLD3-03/wrld3-03.mdl`
   - Revision date: September 29, 2005
   - Format: Vensim `.mdl` (plain text, readable without Vensim software)

2. **Vensim World3-03 sample models page** — Index page linking to all World3-03 model files and documentation.
   - URL: `https://vensim.com/documentation/sample_models.html`

3. **Vensim PLE (free edition)** — Required to *run* the `.mdl` file interactively, though all equations are readable as plain text.
   - URL: `https://vensim.com/free-download/`

### Books & Academic Publications

4. **Meadows, D.H., Meadows, D.L., Randers, J. & Behrens, W.W. III (1972).** *The Limits to Growth.* Universe Books, New York.
   - The original World3 model. Contains all 1972-version table values. Our pre-2004 PCRUM values trace back to this edition.
   - ISBN: 978-0-87663-165-2

5. **Meadows, D.H., Randers, J. & Meadows, D.L. (2004).** *Limits to Growth: The 30-Year Update.* Chelsea Green Publishing.
   - Defines World3-03 (the "30-year update"). Chapter 4 describes all structural changes from World3 to World3-03, including the addition of Resource Conservation Technology (RCT), Persistent Pollution Technology (PPT), and Land Yield Technology (LYT).
   - ISBN: 978-1-931498-58-6

6. **Herrington, G. (2021).** "Update to limits to growth: Comparing the World3 model with empirical data." *Journal of Industrial Ecology*, 25(3), 614–626.
   - Validates World3-03 scenarios against 2020 empirical data. Notes that the MetaSD World3-03 package (Vensim/STELLA zip) is available for download. Provides trajectory comparison data for population, industrial output, food, pollution, etc.
   - DOI: `https://doi.org/10.1111/jiec.13084`

7. **Meadows, D.L. et al. (1974).** *Dynamics of Growth in a Finite World.* Wright-Allen Press.
   - Contains the full technical documentation for World3: every equation, every table, every constant with equation numbers (e.g., PCRUM#130, FCAOR#135). The equation numbers cited in the `.mdl` comments (e.g., `#130.1`) refer to this book.
   - ISBN: 978-0-96040-0-4

### Python Reference Implementations

8. **PyWorld3-03** — Complete Python port of the World3-03 model (2004 version) by Charles Vanwynsberghe.
   - GitHub: `https://github.com/cvanwynsberghe/pyworld3`
   - The `pyworld3/` directory contains `resource.py`, `capital.py`, `population.py`, `agriculture.py`, `pollution.py` with all tables stored as JSON arrays. However, **note**: some PyWorld3 tables may be sourced from the 1974 Dynamics of Growth book rather than the 2004 `.mdl`, so always verify against `wrld3-03.mdl`.
   - License: CeCILL-B
   - Key files for cross-reference:
     - `pyworld3/resource.py` — NR sector tables (PCRUM, FCAOR, NRUF, RCT)
     - `pyworld3/capital.py` — IC/SC sector tables (FIOAS, FIOAC, ICOR, CUF)
     - `pyworld3/population.py` — Mortality and fertility tables (LMHS, LMFT, CMPLE, SFSN)
     - `pyworld3/agriculture.py` — Land/food tables (LYMC, FIOAA, DCPH, LFDR, FALM)
     - `pyworld3/pollution.py` — Pollution tables (AHLM, PPGIO, PPGAO)

9. **PyWorld3 validation notebook** — Jupyter notebook comparing PyWorld3 output to Vensim reference runs.
   - GitHub: `https://github.com/cvanwynsberghe/pyworld3/blob/master/notebooks/world3_standard_run.ipynb`

### MetaSD (System Dynamics Community Resources)

10. **MetaSD World3-03 model package** — Downloadable zip containing World3-03 for Vensim and STELLA, hosted by Tom Fiddaman.
    - URL: `https://metasd.com/2010/04/world3-03/`
    - Contains: Vensim `.mdl`/`.vpm`, STELLA `.stm`, documentation PDFs
    - The same model files served by the Vensim documentation server (#1 above)

11. **Fiddaman, T. (2010).** Blog post describing World3-03 model availability and structural differences from World3.
    - URL: `https://metasd.com/2010/04/world3-03/`

### USGS Data Sources (for resource sector cross-validation)

12. **USGS Mineral Commodity Summaries** — Annual publication with production, reserves, and price data for 93 mineral commodities worldwide.
    - URL: `https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries`
    - Coverage: 1996–2026 (annual)
    - Used for: `NR` proxy via aggregate extraction index

13. **USGS National Minerals Information Center** — Historical statistics and data series.
    - URL: `https://www.usgs.gov/centers/national-minerals-information-center`

### Data Pipeline Connector Sources

14. **World Bank Open Data** — Population (`SP.POP.TOTL`), GDP (`NY.GDP.MKTP.CD`), manufacturing value added.
    - URL: `https://data.worldbank.org/`

15. **FAOSTAT** — Food supply (Food Balance Sheets), arable land, agricultural inputs.
    - URL: `https://www.fao.org/faostat/en/`

16. **EDGAR (Emissions Database for Global Atmospheric Research)** — CO2 emissions by sector.
    - URL: `https://edgar.jrc.ec.europa.eu/`

17. **Global Carbon Project** — Global carbon budget, fossil CO2 emissions.
    - URL: `https://www.globalcarbonproject.org/`

18. **NOAA Global Monitoring Laboratory** — Mauna Loa CO2 concentration data.
    - URL: `https://gml.noaa.gov/ccgg/trends/`

19. **Maddison Project Database** — Historical GDP per capita (from 1 CE).
    - URL: `https://www.rug.nl/ggdc/historicaldevelopment/maddison/`

20. **Penn World Tables (PWT)** — GDP, capital stocks, productivity.
    - URL: `https://www.rug.nl/ggdc/productivity/pwt/`

### Internal Sources (Project Files)

21. **Fetched MDL content** — The raw `wrld3-03.mdl` file was fetched and stored during this investigation at:
    - Local path within this conversation's step cache (step 366)
    - Every table value in this report was extracted from that fetched content

22. **pyWorldX sector source files** — All sector implementations compared in this audit:
    - [resources.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/resources.py)
    - [capital.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/capital.py)
    - [agriculture.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/agriculture.py)
    - [pollution.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/pollution.py)
    - [population.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/population.py)
    - [adaptive_technology.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/adaptive_technology.py)
    - [welfare.py](file:///Users/johnny/pyWorldX/pyworldx/sectors/welfare.py)
    - [parameters.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/parameters.py)
