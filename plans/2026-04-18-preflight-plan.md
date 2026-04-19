# Pre-Flight Remediation Plan — TDD Edition

**Branch:** `phase-2-calibration`
**Date:** 2026-04-18
**Workflow:** Write the failing test (RED) → implement to the Contract → confirm the Gate (GREEN).
**Rule:** No ticket is "done" until its specific Gate command passes AND the unit test suite (`pytest tests/unit/ -x -q`) stays green.
**Prerequisite:** All tickets in this plan must be GREEN before running `EmpiricalCalibrationRunner`.

---

## How to Read This Document

Each ticket has five sections:

| Section | Purpose |
|---|---|
| **Context** | What exists today and why it is wrong |
| **Failing Test** | Exact pytest code — write this first, confirm it is RED |
| **Contract** | The interface or behavior the implementation must satisfy |
| **Constraints** | What must NOT change (regression fence) |
| **Gate** | Copy-paste shell command that proves completion |

---

## T0-0 · Bootstrap Test Directory Structure

**Context**  
No `tests/unit/` or `tests/integration/` directories exist yet. pytest will fail to collect
any ticket test until the directory scaffold and a root `conftest.py` are in place.

**Steps**
1. Create `tests/__init__.py` (empty)
2. Create `tests/unit/__init__.py` (empty)
3. Create `tests/integration/__init__.py` (empty)
4. Create `tests/conftest.py` with shared fixtures (e.g., `tmp_path` overrides, logging capture)
5. Confirm `pytest tests/ --collect-only` exits 0 with no collection errors

**Gate**
```bash
pytest tests/ --collect-only -q
```

Expected: zero errors, zero warnings about missing `__init__.py`.

---

## Tier 1 — Hard Blockers

These four issues produce numerically nonsensical NRMSD scores. Fix in order.

---

### T1-1 · Fix Pollution Index / CO₂ Unit Mismatch in `map.py`

**Context**  
`world3_reference_pollution_index` (dimensionless, ~1.0 at 1970) and `atmospheric.co2`
(ppm, ~325 at 1970) are mapped to the same `CalibrationTarget` entity. Dividing a dimensionless
index by a ppm value produces ~0.003 instead of 1.0, corrupting NRMSD for the entire pollution
sector silently.

**Failing Test**
```python
# tests/unit/test_map_entities.py
from data_pipeline.map import ENTITY_TO_ENGINE_MAP, WORLD3_NAMESPACE

def test_pollution_index_and_co2_are_separate_entities():
    assert "pollution_index_relative" in ENTITY_TO_ENGINE_MAP, (
        "pollution_index_relative missing from ENTITY_TO_ENGINE_MAP"
    )
    assert "atmospheric_co2_ppm" in ENTITY_TO_ENGINE_MAP, (
        "atmospheric_co2_ppm missing from ENTITY_TO_ENGINE_MAP"
    )

def test_atmospheric_co2_excluded_from_objective():
    entry = ENTITY_TO_ENGINE_MAP["atmospheric_co2_ppm"]
    assert entry.get("unit_mismatch") is True
    assert entry.get("excluded_from_objective") is True, (
        "atmospheric_co2_ppm must be excluded from default objective "
        "until a ppm→index conversion is implemented."
    )

def test_pollution_index_maps_to_ppolx():
    entry = ENTITY_TO_ENGINE_MAP["pollution_index_relative"]
    assert entry["engine_var"] == "PPOLX"

def test_pollution_index_normalized_at_train_start():
    import pytest, pandas as pd
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import pathlib
    b = DataBridge(
        aligned_dir=pathlib.Path("output/aligned"),
        config=CrossValidationConfig()
    )
    targets = b.load_targets(sector="pollution")
    ppolx = next(t for t in targets if t.variable == "PPOLX")
    idx = dict(zip(ppolx.years, ppolx.values))
    assert idx[CrossValidationConfig.train_start] == pytest.approx(1.0, abs=0.05), (
        f"PPOLX index at train_start is {idx[CrossValidationConfig.train_start]:.4f}, "
        "expected 1.0 ± 0.05."
    )

def test_world3_pollution_index_namespaced():
    assert "world3.pollution_index" in WORLD3_NAMESPACE
```

**Contract**
- `ENTITY_TO_ENGINE_MAP["pollution_index_relative"]["engine_var"] == "PPOLX"`
- `ENTITY_TO_ENGINE_MAP["atmospheric_co2_ppm"]["unit_mismatch"] == True`
- `ENTITY_TO_ENGINE_MAP["atmospheric_co2_ppm"]["excluded_from_objective"] == True`
- `WORLD3_NAMESPACE["world3.pollution_index"]` exists.
- `world3_reference_pollution_index` must not appear as any key in `ENTITY_TO_ENGINE_MAP`.

**Constraints**
- Do NOT alter any other entity in `ENTITY_TO_ENGINE_MAP`.
- Do NOT change any connector's Parquet output schema.

**Gate**
```bash
pytest tests/unit/test_map_entities.py -v
pytest tests/unit/ -x -q --tb=short
```

---

### T1-2 · Fix Food Per Capita Unit Collision in `map.py`

**Context**  
`world3_reference_food_per_capita` (kg/person/yr) and `faostat_food_balance_historical`
(kcal/capita/day) are merged under the single pipeline entity `food_per_capita` with no
conversion. The two series differ by ~1,000× at 1970, silently blowing out food-sector NRMSD
without raising any error.

**Failing Test**
```python
# tests/unit/test_map_entities.py  (append)

def test_world3_food_reference_not_in_engine_map():
    assert "world3_reference_food_per_capita" not in ENTITY_TO_ENGINE_MAP, (
        "world3_reference_food_per_capita is in ENTITY_TO_ENGINE_MAP. "
        "Mixing kg/person/yr with kcal/capita/day corrupts NRMSD. "
        "Namespace it to world3.food_per_capita and exclude it from the objective."
    )

def test_world3_food_reference_is_namespaced():
    assert "world3.food_per_capita" in WORLD3_NAMESPACE

def test_faostat_is_sole_empirical_food_entity():
    food_entities = [k for k in ENTITY_TO_ENGINE_MAP if "food" in k.lower()]
    assert all("faostat" in e or e == "food_per_capita" for e in food_entities), (
        f"Non-FAOSTAT food entities in ENTITY_TO_ENGINE_MAP: {food_entities}"
    )

def test_food_per_capita_normalized_at_train_start():
    import pytest, pathlib
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    b = DataBridge(
        aligned_dir=pathlib.Path("output/aligned"),
        config=CrossValidationConfig()
    )
    targets = b.load_targets(sector="agriculture")
    fpc = next((t for t in targets if "food" in t.variable.lower()), None)
    assert fpc is not None, "No food per capita target in agriculture sector"
    idx = dict(zip(fpc.years, fpc.values))
    base = CrossValidationConfig.train_start
    assert idx[base] == pytest.approx(1.0, abs=0.10), (
        f"food_per_capita index at {base} is {idx[base]:.4f}, expected 1.0 ± 0.10. "
        "Check that FAOSTAT is the sole source and _normalize_to_index uses train_start."
    )
```

**Contract**
- `world3_reference_food_per_capita` absent from `ENTITY_TO_ENGINE_MAP` at every key.
- `WORLD3_NAMESPACE["world3.food_per_capita"]` exists.
- `ENTITY_TO_ENGINE_MAP` contains at most one food entity; it must be sourced exclusively
  from FAOSTAT.
- Short-term path: keep the two series as separate entities and let
  `DataBridge._normalize_to_index()` handle alignment via index normalization.
  Do NOT silently merge before normalization.

**Constraints**
- Do NOT change the FAOSTAT connector's Parquet output schema.
- Do NOT alter any other entity in `ENTITY_TO_ENGINE_MAP`.

**Gate**
```bash
pytest tests/unit/test_map_entities.py::test_world3_food_reference_not_in_engine_map -v
pytest tests/unit/test_map_entities.py::test_food_per_capita_normalized_at_train_start -v
```

---

### T1-3 · Fix FAOSTAT World Country Code

**Context**  
The FAOSTAT Food Balance Sheet Historical connector passes `world_country_code="WLD"` to the
API. FAOSTAT's correct world-aggregate area code is `"5000"`. With `"WLD"` the API returns zero
rows silently — the entire 1961–2013 FBSH series is absent from the pipeline cache with no
error raised.

**Failing Test**
```python
# tests/unit/test_preflight_gates.py
import pytest

def test_faostat_area_code_is_numeric():
    from data_pipeline.connectors.faostat_food_balance_historical import FAOSTATFBSHConnector
    c = FAOSTATFBSHConnector()
    assert c.world_area_code == "5000", (
        f"Expected '5000', got '{c.world_area_code}'. "
        "FAOSTAT rejects 'WLD' — use numeric code."
    )

def test_faostat_world_area_code_is_named_attribute():
    """Ensure area code is a named class attribute, not an inline string literal."""
    from data_pipeline.connectors.faostat_food_balance_historical import FAOSTATFBSHConnector
    assert hasattr(FAOSTATFBSHConnector, "world_area_code"), (
        "world_area_code must be a named class attribute so it is overridable in tests."
    )

def test_faostat_fetch_raises_on_empty_result(monkeypatch):
    from data_pipeline.connectors.faostat_food_balance_historical import FAOSTATFBSHConnector
    import pandas as pd
    c = FAOSTATFBSHConnector()
    monkeypatch.setattr(c, "_raw_fetch", lambda: pd.DataFrame())
    with pytest.raises(AssertionError, match="FAOSTAT FBSH returned empty"):
        c.fetch()

def test_faostat_cache_has_sufficient_rows():
    """After fix, cached data must have at least 40 rows (expect ~52 for 1961–2013)."""
    from data_pipeline.connectors.faostat_food_balance_historical import FAOSTATFBSHConnector
    import pathlib
    cache_path = pathlib.Path("output/aligned/faostat_food_balance_historical.parquet")
    if not cache_path.exists():
        pytest.skip("Parquet cache not yet generated — run connector first")
    import pandas as pd
    df = pd.read_parquet(cache_path)
    assert len(df) > 40, (
        f"FAOSTAT FBSH cache has {len(df)} rows, expected >40. "
        "Regenerate after fixing world_area_code."
    )
```

**Contract**
- `FAOSTATFBSHConnector.world_area_code: str = "5000"` (named class attribute).
- `fetch()` calls `_raw_fetch()` internally; raises `AssertionError("FAOSTAT FBSH returned
  empty — check area_code")` when result has zero rows after filtering.
- `_raw_fetch()` is injectable (used by monkeypatch in tests).

**Constraints**
- Do NOT change the Parquet output schema.
- Do NOT change any other connector.

**Gate**
```bash
pytest tests/unit/test_preflight_gates.py::test_faostat_area_code_is_numeric -v
pytest tests/unit/test_preflight_gates.py::test_faostat_fetch_raises_on_empty_result -v
# After regenerating cache:
pytest tests/unit/test_preflight_gates.py::test_faostat_cache_has_sufficient_rows -v
```

---

### T1-4 · Fix `initial_conditions.py` Default Year

**Context**  
`target_year` defaults to `1900`. Any call site omitting `target_year` initializes World3 stocks
from pre-industrial values, causing severe divergence before the calibration window opens at 1970.
Additionally, literal `1970` integers are scattered across `pyworldx/` and `data_pipeline/`,
meaning a future `CrossValidationConfig.train_start` change will silently break window alignment.

**Failing Test**
```python
# tests/unit/test_preflight_gates.py  (append)
import pytest
from pyworldx.calibration.initial_conditions import get_initial_conditions
from pyworldx.calibration.metrics import CrossValidationConfig

def test_initial_conditions_default_year_is_train_start():
    ic = get_initial_conditions()
    assert ic["year"] == CrossValidationConfig.train_start, (
        f"Default IC year is {ic['year']}, expected {CrossValidationConfig.train_start}. "
        "Any call without target_year must initialize at train_start."
    )

def test_initial_conditions_1970_values_are_plausible():
    ic = get_initial_conditions()
    assert 3e9 < ic["POP"] < 4e9,    f"POP={ic['POP']:.2e}, expect ~3.5e9 at 1970"
    assert ic["NR"] > 1e11,           f"NR={ic['NR']:.2e}, expect ~1e12 at 1970"
    assert 0.8 < ic["PPOLX"] < 1.2,  f"PPOLX={ic['PPOLX']:.3f}, expect ~1.0 at 1970"

def test_initial_conditions_explicit_1900_still_works():
    ic = get_initial_conditions(target_year=1900)
    assert ic["year"] == 1900

def test_initial_conditions_rejects_invalid_years():
    with pytest.raises(ValueError):
        get_initial_conditions(target_year=1800)
    with pytest.raises(ValueError):
        get_initial_conditions(target_year=2200)

def test_train_start_shift_propagates_to_initial_conditions():
    from unittest.mock import patch
    from pyworldx.calibration import metrics, initial_conditions
    with patch.object(metrics.CrossValidationConfig, "train_start", 1971):
        ic = initial_conditions.get_initial_conditions()
        assert ic["year"] == 1971

def test_no_hardcoded_1970_in_source():
    """All literal 1970 ints in pyworldx/ and data_pipeline/ must be replaced with
    CrossValidationConfig.train_start or a config reference."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", r"\b1970\b", "pyworldx/", "data_pipeline/",
         "--include=*.py", "--exclude-dir=__pycache__"],
        capture_output=True, text=True
    )
    hits = [
        line for line in result.stdout.splitlines()
        if not line.strip().startswith("#")
        and "test_preflight_gates" not in line
        and "CrossValidationConfig" not in line  # config definition itself is allowed
    ]
    assert hits == [], (
        "Literal 1970 integers found in source — replace with "
        "CrossValidationConfig.train_start:\n" + "\n".join(hits)
    )

def test_cross_validation_config_ordering():
    """train_start < train_end < validation_end must hold."""
    cfg = CrossValidationConfig()
    assert cfg.train_start < cfg.train_end < cfg.validation_end, (
        f"CrossValidationConfig ordering violated: "
        f"train_start={cfg.train_start}, train_end={cfg.train_end}, "
        f"validation_end={cfg.validation_end}"
    )
```

**Contract**
- `get_initial_conditions(target_year: int = CrossValidationConfig.train_start) -> dict`
- Raises `ValueError` if `target_year < 1900` or `target_year > 2100`.
- Returns dict containing at minimum: `year`, `POP`, `NR`, `PPOLX`.
- `CrossValidationConfig.__post_init__` asserts `train_start < train_end < validation_end`.
- No literal `1970` integer in `pyworldx/` or `data_pipeline/` source files (comments excluded).

**Constraints**
- `get_initial_conditions(target_year=1900)` must continue to work when explicitly requested.
- Do NOT change the return type of `get_initial_conditions`.

**Gate**
```bash
pytest tests/unit/test_preflight_gates.py -v
pytest tests/unit/ -x -q --tb=short
```

---

## Tier 2 — Pre-Calibration Data Quality

These issues do not crash calibration but silently degrade fit quality or produce misleading
NRMSD scores. Fix before the first optimizer run.

---

### T2-1 · Deterministic Source Arbitration for SC, IC, AL

**Context**  
`service_capital`, `industrial_capital`, and `arable_land` each receive data from 2–3 connectors
with no arbitration logic. Python dict iteration order determines the winner — non-deterministic
across Python versions, making calibration results unreproducible.

**Failing Test**
```python
# tests/unit/test_map_entities.py  (append)
import random

def test_source_priority_defined_for_multi_source_entities():
    multi = ["service_capital", "industrial_capital", "arable_land"]
    for entity in multi:
        assert entity in ENTITY_TO_ENGINE_MAP, f"{entity} missing from map"
        entry = ENTITY_TO_ENGINE_MAP[entity]
        assert "source_priority" in entry, (
            f"{entity} has no source_priority. Multi-source entities must "
            "define explicit priority to prevent non-deterministic arbitration."
        )
        assert len(entry["source_priority"]) >= 2

def test_load_targets_is_deterministic(tmp_path):
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import pandas as pd
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    for source in ["penn_world_table", "world_bank_capital_stock"]:
        path = aligned / f"service_capital__{source}.parquet"
        pd.DataFrame({"year": , "value": [1.0, 1.5]}).to_parquet(path)
    results = []
    for _ in range(5):
        b = DataBridge(aligned_dir=aligned, config=CrossValidationConfig())
        targets = b.load_targets()
        sc = next(t for t in targets if t.variable == "SC")
        results.append(sc.values)
    assert all(r == results for r in results), (
        "load_targets returned different series across calls — arbitration is non-deterministic."
    )

def test_source_selection_is_logged(tmp_path, caplog):
    import logging, pandas as pd
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    pd.DataFrame({"year": , "value": [1.0]}).to_parquet(
        aligned / "service_capital__penn_world_table.parquet"
    )
    b = DataBridge(aligned_dir=aligned, config=CrossValidationConfig())
    with caplog.at_level(logging.INFO):
        b.load_targets()
    assert any("service_capital" in r.message and "penn_world_table" in r.message
               for r in caplog.records), (
        "DataBridge must log which source was selected for each entity."
    )
```

**Contract**
- Each multi-source entity in `ENTITY_TO_ENGINE_MAP` must define `"source_priority": [str, ...]`.
- `DataBridge.load_targets()` implements a priority waterfall: use highest-priority source where
  non-null; fall back in order; log selection at `INFO` level.
- Authoritative priority order:

  | Entity | Priority 1 | Priority 2 | Priority 3 |
  |---|---|---|---|
  | `service_capital` | `penn_world_table` | `world_bank_capital_stock` | `gapminder_gdp_per_capita` |
  | `industrial_capital` | `penn_world_table` | `world_bank_capital_stock` | `unido` |
  | `arable_land` | `faostat_rl` | `world_bank_land` | — |

**Constraints**
- Do NOT change `ENTITY_TO_ENGINE_MAP` for single-source entities.
- PWT deflator step (2017 vs. 2015 base) must be applied before normalization — not silently skipped.

**Gate**
```bash
pytest tests/unit/test_map_entities.py::test_source_priority_defined_for_multi_source_entities -v
pytest tests/unit/test_map_entities.py::test_load_targets_is_deterministic -v
```

---

### T2-2 · Add BP Statistical Review Connector for Nonrenewable Resources

**Context**  
No continuous observed NR stock series exists in the pipeline. `world3_reference_nonrenewable_resources`
is the only current NR input — using it as a calibration target is circular. The resource sector
is entirely synthetic without an empirical anchor.

**Failing Test**
```python
# tests/unit/test_bp_connector.py
import pytest
from unittest.mock import patch
import pandas as pd

def test_bp_connector_exists():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector is not None

def test_bp_connector_schema():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    with patch.object(c, "_raw_fetch") as mock:
        mock.return_value = pd.DataFrame({
            "year": list(range(1965, 2024)),
            "proved_reserves_ej": [500.0 + i * 5 for i in range(59)],
        })
        df = c.fetch()
    assert "year" in df.columns
    assert "proved_reserves_ej" in df.columns
    assert df["year"].min() <= 1970
    assert df["year"].max() >= 2020

def test_bp_connector_no_gap_over_three_years():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    with patch.object(c, "_raw_fetch") as mock:
        years = list(range(1965, 2024))
        mock.return_value = pd.DataFrame({
            "year": years,
            "proved_reserves_ej": [500.0] * len(years),
        })
        df = c.fetch()
    year_set = set(df["year"])
    for y in range(1965, 2021):
        gap = sum(1 for d in range(4) if (y + d) not in year_set)
        assert gap < 4, f"Gap >3 years starting at {y}"

def test_bp_connector_tagged_layer_1():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector.layer == 1, (
        "BP proved reserves is an observed proxy (Layer 1), not a structural reference (Layer 0)."
    )

def test_world3_nr_reference_not_in_engine_map():
    from data_pipeline.map import ENTITY_TO_ENGINE_MAP, WORLD3_NAMESPACE
    assert "world3_reference_nonrenewable_resources" not in ENTITY_TO_ENGINE_MAP
    assert "world3.nr_fraction" in WORLD3_NAMESPACE
```

**Contract**
```python
class BPStatisticalReviewConnector:
    entity: str = "nonrenewable_resources_proved_reserves"
    unit: str = "EJ"
    layer: int = 1
    source_url: str   # OWID/BP mirror URL — must be a named attribute

    def fetch(self) -> pd.DataFrame:
        """Columns: year (int), proved_reserves_ej (float). Covers 1965–2023."""

    def _raw_fetch(self) -> pd.DataFrame:
        """Injectable for testing."""
```

- Output entity key: `nonrenewable_resources_proved_reserves`.
- `world3_reference_nonrenewable_resources` → `WORLD3_NAMESPACE["world3.nr_fraction"]`.
  Absent from `ENTITY_TO_ENGINE_MAP`.
- Conversion note: `EJ → World3 NR units` (scalar calibrated against 1970 World3-03 NR ≈ 1.0×10¹²)
  applied in `DataBridge`, not in the connector.

**Constraints**
- Do NOT alter any existing connector.
- Do NOT include `world3.nr_fraction` in `ENTITY_TO_ENGINE_MAP` at any weight.

**Gate**
```bash
pytest tests/unit/test_bp_connector.py -v
pytest tests/unit/test_map_entities.py::test_world3_nr_reference_not_in_engine_map -v
```

---

### T2-3 · Zero-Guard in `DataBridge._normalize_to_index()`

**Context**  
Several USGS and early World Bank series have zero-padded years before 1960. If
`X(train_start) = 0`, the normalization `X(t) / X(train_start)` produces `inf` or `NaN`,
which propagates silently through the NRMSD calculation with no error.

**Failing Test**
```python
# tests/unit/test_databridge.py
import pytest
import pandas as pd
from pyworldx.data.bridge import DataBridge, DataBridgeError
from pyworldx.calibration.metrics import CrossValidationConfig

@pytest.fixture
def bridge(tmp_path):
    return DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())

def test_normalize_divides_by_base_year(bridge):
    s = pd.Series({1968: 2.0, 1970: 4.0, 1975: 8.0})
    result = bridge._normalize_to_index(s, base_year=1970)
    assert result == pytest.approx(1.0)
    assert result == pytest.approx(2.0)
    assert result == pytest.approx(0.5)

def test_normalize_zero_base_falls_back_to_nearby_nonzero(bridge):
    s = pd.Series({1969: 0.0, 1970: 0.0, 1971: 3.5, 1975: 7.0})
    result = bridge._normalize_to_index(s, base_year=1970)
    assert result == pytest.approx(1.0)
    assert result == pytest.approx(2.0)

def test_normalize_no_nonzero_raises_databridge_error(bridge):
    s = pd.Series({1965: 0.0, 1970: 0.0, 1975: 0.0})
    with pytest.raises(DataBridgeError, match="no non-zero base value"):
        bridge._normalize_to_index(s, base_year=1970)

def test_normalize_result_contains_no_inf_or_nan(bridge):
    import numpy as np
    s = pd.Series({1970: 1.0, 1980: 2.0, 1990: 0.0})  # zero mid-series is fine
    result = bridge._normalize_to_index(s, base_year=1970)
    assert not result.isin([np.inf, -np.inf]).any()

def test_normalize_base_year_is_config_train_start(bridge):
    """Callers must pass config.train_start — never a literal int."""
    s = pd.Series({CrossValidationConfig.train_start: 1.0, 1980: 2.0})
    bridge._normalize_to_index(s, base_year=CrossValidationConfig.train_start)
```

**Contract**
```python
def _normalize_to_index(self, series: pd.Series, base_year: int) -> pd.Series:
    """
    Returns series / series[base_year].
    - If series[base_year] is 0 or NaN, falls back to first non-zero value
      within ±5 years of base_year, emitting a WARNING log.
    - Raises DataBridgeError("no non-zero base value near {base_year}")
      if no fallback exists.
    - Result must contain no inf or NaN values introduced by the normalization itself.
    - base_year must always be CrossValidationConfig.train_start at every internal call site.
    """
```

**Constraints**
- Do NOT apply any unit conversions inside `_normalize_to_index` — it must be unit-agnostic.
- The fallback window is exactly ±5 years — not configurable without a separate PR.

**Gate**
```bash
pytest tests/unit/test_databridge.py -v
```

---

### T2-4 · `DataBridge.load_targets()` Parquet Cache Staleness Check

**Context**  
If a connector's Parquet cache is missing, `DataBridge` currently raises a bare pandas
`FileNotFoundError` with no diagnostic context, making the manual verification step slow to
debug.

**Failing Test**
```python
# tests/unit/test_databridge.py  (append)

def test_load_targets_raises_databridge_error_when_parquet_missing(bridge):
    with pytest.raises(DataBridgeError, match="Parquet cache missing"):
        bridge.load_targets()

def test_load_targets_error_names_the_connector(tmp_path):
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    b = DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())
    try:
        b.load_targets()
    except DataBridgeError as e:
        assert "python -m data_pipeline" in str(e), (
            "DataBridgeError must include the command to regenerate the cache."
        )

def test_load_targets_warns_on_stale_cache(tmp_path, caplog):
    import logging, pandas as pd, time, pathlib
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    # Create a parquet that is artificially old
    p = aligned / "population__un_wpp.parquet"
    pd.DataFrame({"year": , "value": [3.5e9]}).to_parquet(p)
    # Back-date modification time by 40 days
    old_time = time.time() - (40 * 86400)
    import os
    os.utime(p, (old_time, old_time))
    b = DataBridge(aligned_dir=aligned, config=CrossValidationConfig())
    with caplog.at_level(logging.WARNING):
        try:
            b.load_targets()
        except DataBridgeError:
            pass  # other caches missing; we only care about the stale warning
    assert any("stale" in r.message.lower() or "days old" in r.message.lower()
               for r in caplog.records), (
        "DataBridge must warn when a cached Parquet file is older than cache_ttl days."
    )
```

**Contract**
- Before loading each Parquet, check `Path(parquet_path).exists()`.
- Missing → raise `DataBridgeError(f"Parquet cache missing for '{entity}'. "
  f"Run: python -m data_pipeline.connectors.{connector_name}")`.
- Present but older than `cache_ttl` (default: 30 days) → emit `logger.warning(...)` with
  file age in days and the connector refresh command.
- `cache_ttl` must be a named class attribute on `DataBridge`, not a magic number.

**Constraints**
- Do NOT raise on stale cache — warn only; caller decides whether to abort.
- Do NOT change any connector's fetch logic.

**Gate**
```bash
pytest tests/unit/test_databridge.py::test_load_targets_raises_databridge_error_when_parquet_missing -v
pytest tests/unit/test_databridge.py::test_load_targets_error_names_the_connector -v
pytest tests/unit/test_databridge.py::test_load_targets_warns_on_stale_cache -v
```

---

### T2-5 · `CrossValidationConfig.train_start` Propagation Audit

**Context**  
`CrossValidationConfig.train_start = 1970` is defined in `metrics.py` but not verified to
propagate to all downstream consumers. Hardcoded literal `1970` integers exist throughout
`pyworldx/` and `data_pipeline/`. A future config change will silently break window alignment
without raising any error.

**Failing Test**
```python
# tests/unit/test_preflight_gates.py  (append)

def test_config_ordering_invariant_holds():
    from pyworldx.calibration.metrics import CrossValidationConfig
    cfg = CrossValidationConfig()
    assert cfg.train_start < cfg.train_end, (
        f"train_start={cfg.train_start} must be < train_end={cfg.train_end}"
    )
    assert cfg.train_end < cfg.validation_end, (
        f"train_end={cfg.train_end} must be < validation_end={cfg.validation_end}"
    )

def test_train_start_shift_propagates_to_initial_conditions():
    """Changing train_start must shift the IC default year automatically."""
    from unittest.mock import patch
    from pyworldx.calibration import metrics, initial_conditions
    with patch.object(metrics.CrossValidationConfig, "train_start", 1971):
        ic = initial_conditions.get_initial_conditions()
        assert ic["year"] == 1971, (
            "get_initial_conditions() default year did not shift with train_start. "
            "It must read CrossValidationConfig.train_start dynamically."
        )

def test_no_hardcoded_1970_in_source():
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", r"\b1970\b", "pyworldx/", "data_pipeline/",
         "--include=*.py", "--exclude-dir=__pycache__"],
        capture_output=True, text=True
    )
    hits = [
        line for line in result.stdout.splitlines()
        if not line.strip().startswith("#")
        and "test_preflight_gates" not in line
        and "CrossValidationConfig" not in line
    ]
    assert hits == [], (
        "Literal 1970 integers in source — replace with CrossValidationConfig.train_start:\n"
        + "\n".join(hits)
    )
```

**Contract**
- `CrossValidationConfig.__post_init__` asserts `train_start < train_end < validation_end`.
- `get_initial_conditions()` reads `CrossValidationConfig.train_start` dynamically at call time,
  not at import time.
- Zero literal `1970` integers remain in `pyworldx/` or `data_pipeline/` source files
  (excluding comments and the config class definition itself).

**Constraints**
- Existing behavior of all functions that explicitly pass `target_year=1970` must not change.
- Do NOT change `CrossValidationConfig.train_start` value — this is an audit-only ticket.

**Gate**
```bash
pytest tests/unit/test_preflight_gates.py::test_config_ordering_invariant_holds -v
pytest tests/unit/test_preflight_gates.py::test_train_start_shift_propagates_to_initial_conditions -v
pytest tests/unit/test_preflight_gates.py::test_no_hardcoded_1970_in_source -v
pytest tests/unit/ -x -q --tb=short
```

---

## Verification Gates

Run in order after all Tier 1 and Tier 2 tickets are GREEN.

### Gate 1 — Unit Audit
```bash
python -m pyworldx.data.bridge --audit-units
```

Expected: zero `UNIT_MISMATCH` entries. Any remaining mismatches must be tagged
`excluded_from_objective=True` with a documented reason before proceeding.

### Gate 2 — Initial Conditions Smoke Test
```bash
python -c "
from pyworldx.calibration.initial_conditions import get_initial_conditions
from pyworldx.calibration.metrics import CrossValidationConfig
ic = get_initial_conditions()
assert ic['year'] == CrossValidationConfig.train_start
print('IC year:', ic['year'])
print('POP:', ic['POP'])    # expect ~3.5e9
print('NR:', ic['NR'])      # expect ~1e12
print('PPOLX:', ic['PPOLX']) # expect ~1.0
"
```

### Gate 3 — Pipeline Data Coverage Report
```bash
python -m pyworldx.data.bridge --report-coverage --aligned-dir ./output/aligned
```

Expected columns: `entity | source | years_covered | gap_count | base_year_value |
base_year_nonzero`. Any `base_year_nonzero=False` row is an unresolved blocker.

### Gate 4 — Full Test Suite
```bash
pytest tests/ -x -q --tb=short
```

Expected: all tests pass. Zero `XFAIL` items that were passing before.

### Gate 5 — End-to-End Dry Run
```bash
python -m pyworldx.calibration.empirical \
  --dry-run \
  --train-window 1970-2010 \
  --holdout-window 2010-2023
```

Expected: completes without `UnitMismatchError`, `DataBridgeError`, or `NaN` in reported NRMSD.
`--dry-run` skips the optimizer and reports data coverage only.

---

## Open Decision Log

| # | Decision | Options | Status |
|---|---|---|---|
| 1 | Scenario for empirical calibration | `Standard Run` only vs. accept `scenario` arg | **Recommended: accept arg, default `standard_run`** |
| 2 | NR proxy layer weighting | BP reserves as sole Layer 1 vs. blend with WEO data | Unresolved — defer to post-preflight |
| 3 | `World3ReferenceConnector` scope | Layer 0 (structural only, excluded from objective) vs. Layer 1 | **Recommended: Layer 0 only** |

---

## Completion Criteria

This plan is complete when:
- [x] T0-0 directory scaffold GREEN
- [x] All 4 Tier 1 tickets GREEN and committed
- [x] All 5 Tier 2 tickets GREEN and committed
- [x] All 5 Verification Gates pass in a clean environment
- [x] `plans/implementation_audit_report.md` updated with resolved status for each finding
- [x] PR description references this file: `plans/2026-04-18-preflight-plan.md`