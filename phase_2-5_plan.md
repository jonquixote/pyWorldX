# Phase 2–5 Plan: From Bridge to Multi-Version Calibration

## Checklist

### Phase 2: Data Pipeline ↔ Engine Bridge ✅
- [x] `pyworldx/data/bridge.py` — DataBridge, CalibrationTarget, BridgeResult, NRMSD
- [x] `data_pipeline/connectors/world3_reference.py` — W3-03 Standard Run trajectories
- [x] `pyworldx/calibration/empirical.py` — EmpiricalCalibrationRunner
- [x] `data_pipeline/alignment/map.py` — 8 world3_reference ONTOLOGY_MAP entries
- [x] `tests/unit/test_data_bridge.py` — 42 passed, 4 skipped (pyarrow/duckdb)
- [x] Guard `load_targets()` import for graceful degradation without pipeline extras

> **Note:** 4 tests skipped in Phase 2 (`test_load_from_aligned_parquet`, `test_skips_short_series`,
> `test_quick_evaluate`, `test_run_no_targets_returns_empty_report`) because they require
> `pyarrow` and `duckdb` which are pipeline extras not installed in the core poetry venv.
> These tests pass when run with `pip install pyworldx[pipeline]`. This is by design — the
> core engine should not depend on heavy pipeline dependencies.

### Phase 3: ModelPreset System ✅
- [x] `pyworldx/presets.py` — ModelPreset dataclass + PRESETS registry
- [x] World3-03 preset (baseline — uses registry defaults)
- [x] Nebel 2024 preset (parameter overrides from Table S2/S3)
- [x] Herrington validation targets (not a preset — validation data only)
- [x] `tests/unit/test_presets.py` — 28/28 passed
- [x] Wire presets into Scenario system (`Scenario.from_preset()`)
- [x] Widen `pollution.pptd` bounds (10,40)→(10,150) for Nebel's 111.8

### Phase 4: USGS Cross-Validation (Layer 3)
- [ ] `data_pipeline/connectors/usgs.py` — Add `resource_extraction_index` aggregate
- [ ] `data_pipeline/connectors/usgs.py` — Add `reserve_depletion_ratio` variable
- [ ] `data_pipeline/alignment/map.py` — USGS proxy entity mappings
- [ ] Wire USGS proxies into DataBridge as Layer 3 targets

### Phase 5: Integration & Verification
- [ ] Run full calibration: W3-03 preset + empirical targets
- [ ] Run full calibration: Nebel preset + empirical targets
- [ ] Compare trajectories across presets
- [ ] Update walkthrough.md with final results
- [ ] Commit and push

---

## Phase 3: ModelPreset System

### Design

All World3 model versions share the same structural equations. Differences are purely
parametric (~35 scalar constants). The preset system layers on top of the existing
`ParameterRegistry` and `Scenario` infrastructure.

```
Engine (one set of equations)
  × ModelPreset (selects parameter values)
  × Scenario (selects POLICY_YEAR switches, resource doubling, etc.)
  × DataOverlay (pipeline data for further recalibration)
```

### ModelPreset Dataclass

```python
@dataclass
class ModelPreset:
    name: str
    description: str
    parameter_overrides: dict[str, float]
    source: str  # citation / DOI
    year: int    # publication year
```

### Presets

**World3-03** (our current baseline):
- Uses registry defaults — no overrides needed
- Source: wrld3-03.mdl (Vensim, September 29, 2005)

**Nebel 2024** (recalibrated to 1990-2022 data):
- ~35 parameter overrides from Table S2/S3 (DOI: 10.1111/jiec.13442)
- Key changes: `capital.alic` 14→15.24, `pollution.pptd` 20→111.8
- All table functions unchanged (same as W3-03)

**Herrington 2021** (NOT a preset):
- She ran stock W3-03 in 4 scenarios without changing any parameters
- Her contribution: empirical trajectory comparison data (validation targets)
- Goes into the World3ReferenceConnector as additional validation data

### Nebel Parameter Values

From the paper (DOI: 10.1111/jiec.13442, Table S2):

| Parameter | W3-03 Default | Nebel Value | Description |
|---|---|---|---|
| `capital.alic` | 14.0 | 15.24 | Avg lifetime industrial capital (years) |
| `pollution.pptd` | 20.0 | 111.8 | Persistent pollution transmission delay (years) |
| `agriculture.land_development_rate` | 0.005 | TBD | Urban-industrial land dev time |
| (up to ~32 more) | ... | ... | From Supporting Information S1 |

> **Research task**: Extract full parameter list from Nebel Supporting Information S1.
> For now, we include the two parameters explicitly cited in the paper abstract.
> Rest will be filled in when the supplementary data is obtained.

---

## Phase 4: USGS Cross-Validation

Add aggregate resource extraction metrics from our USGS mineral data as Layer 3
cross-validation targets:

- `resource_extraction_index`: weighted world production index (1996=100)
- `reserve_depletion_ratio`: weighted cumulative_extraction/reserves ratio

These map to `resources.nrur_proxy` and `resources.nrfr_proxy` in the engine.

---

## Phase 5: Integration & Verification

Run the full calibration pipeline with each preset and compare:
1. W3-03 Standard Run vs. reference trajectories (NRMSD target < 0.05)
2. Nebel23 vs. 1990-2022 empirical data (should improve fit)
3. Cross-preset trajectory comparison plots

---

## What NOT to Do

1. **Don't build separate sector implementations per version.** Same equations, different constants.
2. **Don't treat Herrington as a model variant.** Validation data, not a new calibration.
3. **Don't implement W3-1972 backward compat now.** Low priority, table function refactoring needed.

---

## References

- Nebel et al. (2024). DOI: `10.1111/jiec.13442`
- Herrington (2021). DOI: `10.1111/jiec.13084`
- Meadows et al. (2004). ISBN: 978-1-931498-58-6
- wrld3-03.mdl: `https://vensim.com/documentation/Models/Sample/WRLD3-03/wrld3-03.mdl`
