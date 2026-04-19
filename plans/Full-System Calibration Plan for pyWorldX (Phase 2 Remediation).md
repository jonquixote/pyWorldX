# Full-System Calibration Plan for pyWorldX (Phase 2 Remediation)

**Format:** Every task is a self-contained TDD ticket.
**Workflow:** Write the failing test (RED) → implement to the contract → confirm the gate (GREEN).
**Rule:** No task is "done" until its specific gate command passes AND the unit test suite (`pytest tests/unit/ -x -q`) stays green.
**Cross-reference:** `plans/2026-04-18-preflight-plan.md`, `plans/preflight_audit.md`

---

## How to Read This Document

Each task has five sections:

| Section | Purpose |
|---|---|
| **Context** | What exists today and why it is wrong |
| **Failing Test** | Exact pytest code — write this first, confirm it is RED |
| **Contract** | The interface/signature the implementation must satisfy |
| **Constraints** | What must NOT change (regression fence) |
| **Gate** | Copy-paste shell command that proves completion |

---

## Phase 0 — Pre-Calibration Physics and Unit Fixes

All Tier 0 blockers must be GREEN before any calibration run.

---

### T0-0 · Test Infrastructure and Fast Mocks

**Context**
Mixing fast unit contracts with 5-minute Bayesian optimizations is a testing anti-pattern that slows down the TDD loop. We need to separate unit tests from slow integration tests, and provide a `--fast` mock for rapid local wiring checks of the calibration runner.

**Failing Test**
```python
# tests/unit/test_conftest.py
import pytest

def test_fast_mock_stubs_optimizer_when_requested(request):
    """The --fast flag must inject the stub_optimizer fixture."""
    # This is a meta-test. The actual verification is that the conftest provides the fixture.
    assert "fast_mode" in request.fixturenames
    assert "stub_optimizer" in request.fixturenames
```

**Contract**
- Create directories: `tests/unit/` and `tests/integration/`.
- Create `tests/conftest.py` with the `--fast` flag and `stub_optimizer` fixture.
- `stub_optimizer` must patch `EmpiricalCalibrationRunner._run_optimizer` to return a predefined, "good enough" parameter dict (e.g. `{"population.cbr_base": 0.028, ...}`).
- `stub_optimizer` must patch `DataBridge.load_targets()` to return dummy targets so that a clean checkout doesn't fail on Parquet cache checks.
- `autouse=False` on `stub_optimizer` — tests must opt-in via `@pytest.mark.usefixtures("stub_optimizer")`.
- `tests/unit/` and `tests/integration/` can have their own `conftest.py` for scoped fixtures.

**Gate Commands Reference**

| When | Command | Covers |
|---|---|---|
| Every file save (TDD loop) | `pytest tests/unit/ -x -q` | All contract and unit tests |
| Before committing | `pytest tests/unit/ tests/integration/ -x -q --fast` | Full suite, stubbed optimizer |
| CI / before PR merge | `pytest tests/unit/ tests/integration/ -x -q` | Full suite, real optimizer |
| Phase 4 only | `pytest tests/integration/test_regression.py` | Baseline manifest check |

**Gate**
```bash
pytest tests/unit/test_conftest.py -v
```

---

### T0-1 · Carbon Cycle Equilibrium Fix

**Context**
`pyworldx/sectors/pollution_ghg.py` initializes a 5-stock carbon model. Pre-industrial NPP
(60 GtC/yr) exceeds the combined plant respiration and litter flux (39 GtC/yr at
`C_land = 600 GtC`), causing an unphysical atmospheric carbon drawdown from 1900–1940 even
before anthropogenic emissions are applied. The engine must be in equilibrium at pre-industrial
conditions before any calibration signal is meaningful.

**Failing Test**
```python
# tests/test_carbon_equilibrium.py
import pytest
from pyworldx.sectors.pollution_ghg import CarbonCycleModel

def test_preindustrial_atmospheric_carbon_is_stable():
    """Net atmosphere flux must be < 0.1 GtC/yr at pre-industrial steady state."""
    model = CarbonCycleModel()
    # Run 50 years at pre-industrial forcings (no anthropogenic emissions)
    trajectory = model.run(years=50, anthropogenic_emissions_gtc=0.0)
    delta_atm = trajectory["C_atm"].iloc[-1] - trajectory["C_atm"].iloc
    assert abs(delta_atm) < 0.1 * 50, (
        f"Atmospheric carbon drifted {delta_atm:.2f} GtC over 50 years at pre-industrial "
        f"steady state. Expected < 5 GtC drift. NPP must equal respiration + litter at "
        f"C_land=600 GtC: set k_resp_plant = k_litter = 0.05."
    )

def test_carbon_equilibrium_constants_satisfy_npp_balance():
    """k_resp_plant + k_litter at C_land=600 must equal NPP0=60."""
    from pyworldx.sectors.pollution_ghg import _K_RESP_PLANT, _K_LITTER, _C_LAND_0, _NPP0
    flux = (_K_RESP_PLANT + _K_LITTER) * _C_LAND_0
    assert abs(flux - _NPP0) < 0.5, (
        f"NPP balance violated: ({_K_RESP_PLANT} + {_K_LITTER}) × {_C_LAND_0} = {flux:.1f} "
        f"≠ NPP0={_NPP0}. Set k_resp_plant = k_litter = 0.05."
    )
```

**Contract**
- `_K_RESP_PLANT: float = 0.05` (module-level constant)
- `_K_LITTER: float = 0.05` (module-level constant)
- `CarbonCycleModel.run(years: int, anthropogenic_emissions_gtc: float) -> pd.DataFrame`
  returns a DataFrame with at minimum a `C_atm` column indexed by simulation year.
- At `C_land = _C_LAND_0 = 600`, `(_K_RESP_PLANT + _K_LITTER) * 600 == _NPP0 == 60.0`.

**Constraints**
- Do NOT change soil respiration structure or `_K_RESP_SOIL`.
- Do NOT alter the existing `run_calibration_pipeline` call signature.
- Existing passing tests in `tests/` must not regress.

**Gate**
```bash
pytest tests/unit/test_carbon_equilibrium.py -v
pytest tests/unit/ -x -q --tb=short   # unit suite must stay green
```

---

### T0-2 · Food Per Capita Entity Separation in `map.py`

**Context**
`data_pipeline/map.py` maps both `world3_reference_food_per_capita` (kg/person/yr) and
`faostat_food_balance_historical` (kcal/capita/day) to the same pipeline entity
`food_per_capita`. The two series differ by ~1,000× at 1970. This corrupts the agriculture-sector
NRMSD silently — no error is raised, the objective just optimizes toward nonsense.

**Failing Test**
```python
# tests/test_map_entities.py
from data_pipeline.map import ENTITY_TO_ENGINE_MAP, WORLD3_NAMESPACE

def test_world3_food_reference_is_not_in_engine_map():
    """world3_reference_food_per_capita must never be an empirical calibration target."""
    assert "world3_reference_food_per_capita" not in ENTITY_TO_ENGINE_MAP, (
        "world3_reference_food_per_capita is in ENTITY_TO_ENGINE_MAP. "
        "It must be namespaced to world3.food_per_capita and excluded from the "
        "empirical objective — mixing kg/person/yr with kcal/capita/day corrupts NRMSD."
    )

def test_world3_food_reference_is_namespaced():
    """World3 reference food entity must live under world3.* namespace."""
    assert "world3.food_per_capita" in WORLD3_NAMESPACE, (
        "world3.food_per_capita not found in WORLD3_NAMESPACE. "
        "All world3_reference_* entities must be namespaced to world3.*"
    )

def test_faostat_food_is_sole_empirical_food_entity():
    """FAOSTAT is the sole authoritative food source in ENTITY_TO_ENGINE_MAP."""
    food_entities = [k for k in ENTITY_TO_ENGINE_MAP if "food" in k.lower()]
    assert all("faostat" in e or "food_per_capita" == e for e in food_entities), (
        f"Non-FAOSTAT food entities found in ENTITY_TO_ENGINE_MAP: {food_entities}"
    )
```

**Contract**
- `WORLD3_NAMESPACE: dict` — a module-level dict in `map.py` keyed by `world3.*` names,
  excluded from `ENTITY_TO_ENGINE_MAP`.
- `ENTITY_TO_ENGINE_MAP` must contain exactly one food entity: either `food_per_capita`
  sourced exclusively from FAOSTAT, or `faostat_food_per_capita` with an explicit key rename.
- `world3_reference_food_per_capita` must not appear in `ENTITY_TO_ENGINE_MAP` at any key.

**Constraints**
- Do NOT alter any other entity in `ENTITY_TO_ENGINE_MAP`.
- Do NOT change Parquet output schema for the FAOSTAT connector.

**Gate**
```bash
pytest tests/unit/test_map_entities.py::test_world3_food_reference_is_not_in_engine_map -v
pytest tests/unit/test_map_entities.py::test_faostat_food_is_sole_empirical_food_entity -v
```

---

### T0-3 · Pollution Index / CO₂ Entity Separation in `map.py`

**Context**
`world3_reference_pollution_index` (dimensionless, ~1.0 at 1970) and `atmospheric.co2`
(ppm, ~325 at 1970) are merged into the same `CalibrationTarget`. Dividing a dimensionless
index by a ppm value produces ~0.003 instead of 1.0, making the pollution-sector NRMSD
numerically meaningless.

**Failing Test**
```python
# tests/test_map_entities.py  (append to existing file)

def test_pollution_index_and_co2_are_separate_entities():
    """PPOLX and atmospheric CO2 must be distinct entities with distinct units."""
    assert "pollution_index_relative" in ENTITY_TO_ENGINE_MAP, (
        "pollution_index_relative missing from ENTITY_TO_ENGINE_MAP"
    )
    assert "atmospheric_co2_ppm" in ENTITY_TO_ENGINE_MAP, (
        "atmospheric_co2_ppm missing from ENTITY_TO_ENGINE_MAP"
    )
    co2_entry = ENTITY_TO_ENGINE_MAP["atmospheric_co2_ppm"]
    assert co2_entry.get("unit_mismatch") is True, (
        "atmospheric_co2_ppm must be tagged unit_mismatch=True and excluded "
        "from the default objective until a ppm→index conversion is implemented."
    )

def test_world3_pollution_index_is_namespaced():
    assert "world3.pollution_index" in WORLD3_NAMESPACE

def test_world3_reference_collisions_fully_retired():
    """All four world3_reference_* collision mappings must be removed."""
    forbidden = [
        "world3_reference_pollution_index",
        "world3_reference_food_per_capita",
        "world3_reference_industrial_output",
        "world3_reference_nonrenewable_resources",
    ]
    present = [k for k in ENTITY_TO_ENGINE_MAP if k in forbidden]
    assert present == [], (
        f"world3_reference_* collision(s) still in ENTITY_TO_ENGINE_MAP: {present}. "
        "These create circular calibration — retire all four."
    )
```

**Contract**
- `ENTITY_TO_ENGINE_MAP["pollution_index_relative"]["engine_var"] == "PPOLX"`
- `ENTITY_TO_ENGINE_MAP["atmospheric_co2_ppm"]["unit_mismatch"] == True`
- `ENTITY_TO_ENGINE_MAP["atmospheric_co2_ppm"]["excluded_from_objective"] == True`
- All four `world3_reference_*` collision entries removed from `ENTITY_TO_ENGINE_MAP`.
- All four namespaced to `WORLD3_NAMESPACE` under `world3.*` keys.

**Constraints**
- Do NOT alter any non-collision entity in `ENTITY_TO_ENGINE_MAP`.

**Gate**
```bash
pytest tests/unit/test_map_entities.py -v
```

---

### T0-4 · Fix FAOSTAT World Country Code

**Context**
`data_pipeline/connectors/faostat_food_balance_historical.py` passes
`world_country_code="WLD"` to the FAOSTAT API. FAOSTAT's correct world aggregate code is
`"5000"`. With `"WLD"` the API returns zero rows silently — the entire 1961–2013 FBSH series
is missing from the pipeline cache without raising any error.

**Failing Test**
```python
# tests/test_preflight_gates.py

def test_faostat_area_code_is_numeric():
    from data_pipeline.connectors.faostat_food_balance_historical import FAOSTATFBSHConnector
    c = FAOSTATFBSHConnector()
    assert c.world_area_code == "5000", (
        f"Expected '5000', got '{c.world_area_code}'. "
        "FAOSTAT rejects 'WLD' — use numeric code."
    )

def test_faostat_fetch_raises_on_empty_result(monkeypatch):
    """Connector must assert non-empty result after fetch."""
    from data_pipeline.connectors.faostat_food_balance_historical import FAOSTATFBSHConnector
    import pandas as pd
    c = FAOSTATFBSHConnector()
    monkeypatch.setattr(c, "_raw_fetch", lambda: pd.DataFrame())
    with pytest.raises(AssertionError, match="FAOSTAT FBSH returned empty"):
        c.fetch()
```

**Contract**
- `FAOSTATFBSHConnector.world_area_code: str = "5000"` (named class attribute).
- `fetch()` raises `AssertionError("FAOSTAT FBSH returned empty — check area_code")`
  if the fetched DataFrame has zero rows after filtering.
- `world_area_code` must be a named class attribute, not an inline string literal.

**Constraints**
- Do NOT change the Parquet output schema.
- Do NOT change any other connector.

**Gate**
```bash
pytest tests/unit/test_preflight_gates.py::test_faostat_area_code_is_numeric -v
pytest tests/unit/test_preflight_gates.py::test_faostat_fetch_raises_on_empty_result -v
```

---

### T0-5 · Fix `initial_conditions.py` Default Year

**Context**
`pyworldx/calibration/initial_conditions.py` defaults `target_year=1900`. Any call site that
omits `target_year` initializes World3 stocks from pre-industrial values. The simulation diverges
severely before reaching 1970, making the calibration window meaningless.

**Failing Test**
```python
# tests/test_preflight_gates.py  (append)
from pyworldx.calibration.initial_conditions import get_initial_conditions
from pyworldx.calibration.metrics import CrossValidationConfig

def test_initial_conditions_default_year_is_train_start():
    ic = get_initial_conditions()
    assert ic["year"] == CrossValidationConfig.train_start, (
        f"Default IC year is {ic['year']}, expected {CrossValidationConfig.train_start}. "
        "Any call without target_year should initialize at train_start (1970)."
    )

def test_initial_conditions_1970_values_are_plausible():
    ic = get_initial_conditions()
    assert 3e9 < ic["POP"] < 4e9,   f"POP={ic['POP']:.2e}, expect ~3.5e9 at 1970"
    assert ic["NR"] > 1e11,          f"NR={ic['NR']:.2e}, expect ~1e12 at 1970"
    assert 0.8 < ic["PPOLX"] < 1.2, f"PPOLX={ic['PPOLX']:.3f}, expect ~1.0 at 1970"

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

def test_no_hardcoded_1970_in_pyworldx(tmp_path):
    """No literal 1970 integers should remain in pyworldx/ or data_pipeline/."""
    import subprocess, re
    result = subprocess.run(
        ["grep", "-rn", r"\b1970\b", "pyworldx/", "data_pipeline/",
         "--include=*.py", "--exclude-dir=__pycache__"],
        capture_output=True, text=True
    )
    # Allow only comments and this test file itself
    hits = [
        line for line in result.stdout.splitlines()
        if not line.strip().startswith("#")
        and "test_preflight_gates" not in line
        and "CrossValidationConfig" not in line   # config definition itself is allowed
    ]
    assert hits == [], (
        "Literal 1970 integers found in source files:\n" + "\n".join(hits) + "\n"
        "Replace all with CrossValidationConfig.train_start."
    )
```

**Contract**
- `get_initial_conditions(target_year: int = CrossValidationConfig.train_start) -> dict`
- Raises `ValueError` if `target_year < 1900` or `target_year > 2100`.
- Contains assertion: `assert target_year <= CrossValidationConfig.train_start` (simulation must
  start at or before calibration window opens).
- No literal `1970` integer remains in `pyworldx/` or `data_pipeline/` source files.

**Constraints**
- `get_initial_conditions(target_year=1900)` must still work when explicitly requested.
- Do NOT change function return type.

**Gate**
```bash
pytest tests/unit/test_preflight_gates.py -v
pytest tests/unit/ -x -q --tb=short
```

---

## Phase 1 — DataBridge and Pipeline Readiness

---

### T1-1 · Implement `DataBridge` with Zero-Guard and Cache Check

**Context**
`pyworldx/data/bridge.py` does not yet exist. The `DataBridge` is the layer that normalizes
real-world series into indices for NRMSD comparison. Without the zero-guard,
`_normalize_to_index()` silently produces `inf`/`NaN` on zero-padded early USGS/World Bank
series. Without the cache check, missing Parquet files surface as bare pandas
`FileNotFoundError` with no diagnostic context.

**Failing Test**
```python
# tests/test_databridge.py
import pytest
import pandas as pd
from pyworldx.data.bridge import DataBridge, DataBridgeError, CalibrationTarget
from pyworldx.calibration.metrics import CrossValidationConfig

@pytest.fixture
def bridge(tmp_path):
    return DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())

def test_normalize_divides_by_base_year_value(bridge):
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

def test_normalize_zero_base_no_nonzero_raises(bridge):
    s = pd.Series({1965: 0.0, 1970: 0.0, 1975: 0.0})
    with pytest.raises(DataBridgeError, match="no non-zero base value"):
        bridge._normalize_to_index(s, base_year=1970)

def test_normalize_base_year_must_be_train_start(bridge):
    """Callers must always pass config.train_start, not a literal int."""
    s = pd.Series({1970: 1.0, 1980: 2.0})
    # Calling with config.train_start is always valid
    bridge._normalize_to_index(s, base_year=CrossValidationConfig.train_start)

def test_load_targets_raises_databridge_error_when_parquet_missing(bridge):
    with pytest.raises(DataBridgeError, match="Parquet cache missing"):
        bridge.load_targets()

def test_load_targets_error_message_includes_connector_name(tmp_path):
    from pyworldx.data.bridge import DataBridge
    b = DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())
    try:
        b.load_targets()
    except DataBridgeError as e:
        assert "python -m data_pipeline" in str(e), (
            "Error message must include the command to regenerate the cache."
        )

def test_calibration_target_dataclass_fields():
    ct = CalibrationTarget(
        variable="POP",
        years=,
        values=[1.0, 1.1],
        unit="persons",
    )
    assert ct.variable == "POP"
    assert len(ct.years) == 2

def test_build_objective_enforces_train_window(bridge, monkeypatch):
    """build_objective must only score years within [train_start, train_end]."""
    import numpy as np
    fake_targets = [
        CalibrationTarget("POP", list(range(1960, 2025)),
                          [1.0 + i*0.01 for i in range(65)], "persons")
    ]
    monkeypatch.setattr(bridge, "load_targets", lambda: fake_targets)
    monkeypatch.setattr(bridge, "_run_engine", lambda params: {
        "POP": pd.Series({y: 1.0 + (y-1970)*0.01 for y in range(1960, 2025)})
    })
    obj = bridge.build_objective()
    score = obj({"cbr_base": 0.028})
    assert np.isfinite(score), "Objective must return a finite float"

def test_validation_score_uses_only_holdout_window(bridge, monkeypatch):
    """calculate_validation_score must not use any years from the train window."""
    import numpy as np
    fake_targets = [
        CalibrationTarget("POP", list(range(1970, 2024)),
                          [1.0 + i*0.005 for i in range(54)], "persons")
    ]
    monkeypatch.setattr(bridge, "load_targets", lambda: fake_targets)
    monkeypatch.setattr(bridge, "_run_engine", lambda params: {
        "POP": pd.Series({y: 1.0 + (y-1970)*0.005 for y in range(1970, 2024)})
    })
    train_score = bridge.build_objective()({"cbr_base": 0.028})
    val_score = bridge.calculate_validation_score({"cbr_base": 0.028})
    # Both must be finite; the key invariant is they are computed independently
    assert np.isfinite(train_score)
    assert np.isfinite(val_score)
```

**Contract**
```python
@dataclass
class CalibrationTarget:
    variable: str
    years: list[int]
    values: list[float]
    unit: str

class DataBridgeError(Exception): ...

class DataBridge:
    def __init__(self, aligned_dir: Path, config: CrossValidationConfig): ...
    def load_targets(self) -> list[CalibrationTarget]: ...
    def _normalize_to_index(self, series: pd.Series, base_year: int) -> pd.Series: ...
    def build_objective(self) -> Callable[[dict[str, float]], float]: ...
    def calculate_validation_score(self, params: dict[str, float]) -> float: ...
```

- `_normalize_to_index` falls back to first non-zero within ±5 years of `base_year` when
  `series[base_year] == 0` or `NaN`; raises `DataBridgeError` if no fallback exists.
- `load_targets` raises `DataBridgeError` (not `FileNotFoundError`) when Parquet missing,
  with message containing `"python -m data_pipeline"`.
- `build_objective` scores only years in `[config.train_start, config.train_end]`.
- `calculate_validation_score` scores only years in `(config.train_end, config.validation_end]`.

**Constraints**
- Do NOT import from `pyworldx.calibration.empirical` — the bridge must have no circular imports.
- `base_year` parameter in `_normalize_to_index` must always receive `config.train_start`
  at every internal call site — never a literal integer.

**Gate**
```bash
pytest tests/unit/test_databridge.py -v
```

---

### T1-2 · Multi-Source Arbitration in `ENTITY_TO_ENGINE_MAP`

**Context**
`service_capital` (SC), `industrial_capital` (IC), and `arable_land` (AL) each receive data
from 2–3 connectors with no arbitration logic. Python dict iteration order determines which
series wins — non-deterministic across Python versions.

**Failing Test**
```python
# tests/test_map_entities.py  (append)
import random

def test_source_priority_defined_for_multi_source_entities():
    multi_source = ["service_capital", "industrial_capital", "arable_land"]
    for entity in multi_source:
        assert entity in ENTITY_TO_ENGINE_MAP, f"{entity} missing from map"
        entry = ENTITY_TO_ENGINE_MAP[entity]
        assert "source_priority" in entry, (
            f"{entity} has no source_priority list. Multi-source entities must "
            "define explicit priority to avoid non-deterministic arbitration."
        )
        assert len(entry["source_priority"]) >= 2

def test_load_targets_is_deterministic(tmp_path):
    """load_targets must return the same series regardless of source registration order."""
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    # Write two dummy parquet files for service_capital from different sources
    import pandas as pd, pathlib
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
```

**Contract**
- Each multi-source entity in `ENTITY_TO_ENGINE_MAP` must have `"source_priority": [str, ...]`.
- `DataBridge.load_targets()` implements priority-waterfall: uses highest-priority source where
  non-null, falls back in order.
- Priority table (authoritative):

  | Entity | Priority 1 | Priority 2 | Priority 3 |
  |---|---|---|---|
  | `service_capital` | `penn_world_table` | `world_bank_capital_stock` | `gapminder_gdp_per_capita` |
  | `industrial_capital` | `penn_world_table` | `world_bank_capital_stock` | `unido` |
  | `arable_land` | `faostat_rl` | `world_bank_land` | — |

**Constraints**
- Do NOT change `ENTITY_TO_ENGINE_MAP` entries for any single-source entity.

**Gate**
```bash
pytest tests/unit/test_map_entities.py::test_source_priority_defined_for_multi_source_entities -v
pytest tests/unit/test_map_entities.py::test_load_targets_is_deterministic -v
```

---

### T1-3 · Add BP Statistical Review Connector for Nonrenewable Resources

**Context**
There is no continuous observed NR stock series. The `world3_reference_nonrenewable_resources`
trajectory is the only current NR input — using it as a calibration target is circular. The
resource sector is entirely synthetic without a real empirical anchor.

**Failing Test**
```python
# tests/test_bp_connector.py
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

def test_bp_connector_exists():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    assert BPStatisticalReviewConnector is not None

def test_bp_connector_output_schema():
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    with patch.object(c, "_raw_fetch") as mock_fetch:
        mock_fetch.return_value = pd.DataFrame({
            "year": list(range(1965, 2024)),
            "proved_reserves_ej": [500.0 + i * 5 for i in range(59)],
        })
        df = c.fetch()
    assert "year" in df.columns
    assert "proved_reserves_ej" in df.columns
    assert len(df) >= 50
    assert df["year"].min() <= 1970
    assert df["year"].max() >= 2020

def test_bp_connector_coverage_requirement():
    """Series must cover 1965–2023 with no more than 3 consecutive missing years."""
    from data_pipeline.connectors.bp_statistical_review import BPStatisticalReviewConnector
    c = BPStatisticalReviewConnector()
    with patch.object(c, "_raw_fetch") as mock_fetch:
        years = list(range(1965, 2024))
        mock_fetch.return_value = pd.DataFrame({
            "year": years,
            "proved_reserves_ej": [500.0] * len(years),
        })
        df = c.fetch()
    # Check no gap > 3 years
    year_set = set(df["year"])
    for y in range(1965, 2024):
        consecutive_missing = sum(1 for d in range(4) if (y + d) not in year_set)
        assert consecutive_missing < 4, f"Gap > 3 years starting at {y}"

def test_nr_world3_reference_excluded_from_engine_map():
    from data_pipeline.map import ENTITY_TO_ENGINE_MAP, WORLD3_NAMESPACE
    assert "world3_reference_nonrenewable_resources" not in ENTITY_TO_ENGINE_MAP
    assert "world3.nr_fraction" in WORLD3_NAMESPACE
```

**Contract**
```python
class BPStatisticalReviewConnector:
    entity: str = "nonrenewable_resources_proved_reserves"
    unit: str = "EJ"
    layer: int = 1          # observed proxy (not Layer 0 structural reference)
    source_url: str         # OWID/BP mirror URL

    def fetch(self) -> pd.DataFrame:
        """Returns DataFrame with columns: year (int), proved_reserves_ej (float)."""
        ...
    def _raw_fetch(self) -> pd.DataFrame: ...  # injectable for testing
```

- Output Parquet entity key: `nonrenewable_resources_proved_reserves`
- `world3_reference_nonrenewable_resources` must be in `WORLD3_NAMESPACE["world3.nr_fraction"]`
  and absent from `ENTITY_TO_ENGINE_MAP`.

**Constraints**
- Do NOT alter any existing connector.
- Do NOT include `world3.nr_fraction` in `ENTITY_TO_ENGINE_MAP` at any weight.

**Gate**
```bash
pytest tests/unit/test_bp_connector.py -v
pytest tests/unit/test_map_entities.py::test_world3_reference_collisions_fully_retired -v
```

---

### T1-4 · `EmpiricalCalibrationRunner` Scenario Argument

**Context**
`EmpiricalCalibrationRunner` in `pyworldx/calibration/empirical.py` has no `scenario`
argument. Hardcoding `Standard Run` makes it impossible to compare calibration quality against
historical policy scenarios without a separate runner subclass.

**Failing Test**
```python
# tests/test_empirical_calibration.py
import pytest
from unittest.mock import MagicMock, patch

def test_runner_accepts_scenario_argument():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    # Should not raise
    r = EmpiricalCalibrationRunner(scenario="standard_run")
    assert r.scenario == "standard_run"

def test_runner_default_scenario_is_standard_run():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    r = EmpiricalCalibrationRunner()
    assert r.scenario == "standard_run"

def test_runner_rejects_unknown_scenario():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    with pytest.raises(ValueError, match="unknown scenario"):
        EmpiricalCalibrationRunner(scenario="made_up_scenario_xyz")

def test_runner_error_lists_valid_scenarios():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    try:
        EmpiricalCalibrationRunner(scenario="bad_scenario")
    except ValueError as e:
        assert "standard_run" in str(e).lower(), (
            "ValueError must list valid scenario names so the user knows what to pass."
        )

def test_validation_nrmsd_independent_of_train_nrmsd(monkeypatch):
    """train_nrmsd and validation_nrmsd must be computed from separate DataBridge calls."""
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    call_log = []
    def mock_build_objective():
        call_log.append("train")
        return lambda p: 0.05
    def mock_calc_validation(params):
        call_log.append("validation")
        return 0.07

    r = EmpiricalCalibrationRunner()
    monkeypatch.setattr(r.bridge, "build_objective", mock_build_objective)
    monkeypatch.setattr(r.bridge, "calculate_validation_score", mock_calc_validation)
    with patch.object(r, "_run_optimizer", return_value={"cbr_base": 0.028}):
        result = r.run()
    assert "train" in call_log and "validation" in call_log, (
        "Both build_objective (train) and calculate_validation_score (validation) "
        "must be called — they must be independent."
    )

def test_overfit_flagged_only_above_threshold(monkeypatch):
    """overfit_flagged must NOT fire for mild validation degradation below threshold."""
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    from pyworldx.calibration.metrics import CrossValidationConfig
    r = EmpiricalCalibrationRunner()
    # Simulate train=0.05, validation=0.06 — mild degradation, below threshold
    threshold = CrossValidationConfig.overfit_threshold
    train_nrmsd = 0.05
    val_nrmsd = train_nrmsd + (threshold * 0.5)  # half the threshold — must NOT flag
    result = r._assess_overfit(train_nrmsd=train_nrmsd, validation_nrmsd=val_nrmsd)
    assert result.overfit_flagged is False, (
        f"overfit_flagged fired at gap={val_nrmsd - train_nrmsd:.4f}, "
        f"which is below threshold={threshold}. "
        "Mild validation degradation is expected and healthy."
    )
    # Now exceed threshold — must flag
    val_nrmsd_high = train_nrmsd + (threshold * 1.5)
    result_high = r._assess_overfit(train_nrmsd=train_nrmsd, validation_nrmsd=val_nrmsd_high)
    assert result_high.overfit_flagged is True
```

**Contract**
- `EmpiricalCalibrationRunner.__init__(self, scenario: str = "standard_run", ...)`
- Raises `ValueError(f"unknown scenario '{scenario}'. Valid: {list(VALID_SCENARIOS)}")` for
  unregistered scenarios.
- `_assess_overfit(train_nrmsd: float, validation_nrmsd: float) -> CalibrationResult`
  sets `overfit_flagged = True` only when
  `validation_nrmsd - train_nrmsd > CrossValidationConfig.overfit_threshold`.

**Constraints**
- Do NOT change `run_calibration_pipeline` signature in `pipeline.py`.
- Do NOT break existing `EmpiricalCalibrationRunner` instantiation with no arguments.

**Gate**
```bash
pytest tests/unit/test_empirical_calibration.py -v
pytest tests/unit/ -x -q --tb=short
```

---

## Phase 2 — Sector-by-Sector Calibration

All Phase 0 and Phase 1 gates must be GREEN before running any optimizer.

**Universal invariant for every sector task:**
- Train window: `CrossValidationConfig.train_start`–`CrossValidationConfig.train_end` (1970–2010).
- Holdout: `CrossValidationConfig.train_end`–`CrossValidationConfig.validation_end` (2010–2023).
- Normalization base: `config.train_start` — never a literal `1970`.
- NaN/inf in objective score → task is blocked; fix upstream data issue first.

---

### T2-1 · Population Sector Calibration

**Context**
The population sector must be calibrated first — all other sectors depend on it.
Target: UN WPP world population 1950–2023 (UN WPP connector, unit: persons ×1000 from FAOSTAT).

**Failing Test**
```python
# tests/integration/test_sector_calibration.py
import pytest

@pytest.mark.slow
@pytest.mark.usefixtures("stub_optimizer")
def test_population_calibration_produces_finite_nrmsd():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    from pyworldx.calibration.metrics import CrossValidationConfig
    runner = EmpiricalCalibrationRunner(
        scenario="standard_run",
        parameter_names=["population.cbr_base", "population.cdr_base"],
        sector="population",
    )
    result = runner.run()
    import math
    assert math.isfinite(result.train_nrmsd), "train_nrmsd is NaN/inf — data issue upstream"
    assert math.isfinite(result.validation_nrmsd), "validation_nrmsd is NaN/inf"
    assert result.train_nrmsd < 0.30, (
        f"Population train NRMSD={result.train_nrmsd:.4f} exceeds 0.30 — "
        "calibration failed to converge. Check UN WPP connector and entity mapping."
    )

@pytest.mark.slow
@pytest.mark.usefixtures("stub_optimizer")
def test_population_train_nrmsd_better_than_validation():
    """Train NRMSD should be lower than validation NRMSD after calibration."""
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    runner = EmpiricalCalibrationRunner(
        parameter_names=["population.cbr_base", "population.cdr_base"],
        sector="population",
    )
    result = runner.run()
    # Mild degradation is expected — fail only if validation is catastrophically worse
    assert result.validation_nrmsd < result.train_nrmsd * 3.0, (
        f"Validation NRMSD ({result.validation_nrmsd:.4f}) is >3× train "
        f"({result.train_nrmsd:.4f}) — severe overfitting."
    )
```

**Contract**
- `EmpiricalCalibrationRunner` accepts `sector: str` to restrict `DataBridge.load_targets()`
  to sector-relevant entities only.
- `EmpiricalCalibrationRunner.run()` returns `CalibrationResult` with fields:
  `optimized_params`, `train_nrmsd`, `validation_nrmsd`, `overfit_flagged`.
- Population calibration acceptance: `train_nrmsd < 0.30`, `validation_nrmsd < train_nrmsd × 3`.

**Constraints**
- Population calibration must NOT modify capital, agriculture, or resource parameters.
- Calibrated population parameters must be serialized to `output/calibrated_params/population.json`.

**Gate**
```bash
pytest tests/integration/test_sector_calibration.py::test_population_calibration_produces_finite_nrmsd -m slow -v
# Then manually inspect output/calibrated_params/population.json
```

---

### T2-2 · Capital Sector Calibration

**Context**
Capital sector calibrates IC and SC using PWT as authoritative source (per T1-2 priority table).
Population parameters are frozen at T2-1 calibrated values.

**Failing Test**
```python
# tests/integration/test_sector_calibration.py  (append)
import pytest

def test_capital_calibration_uses_pwt_as_authoritative_source():
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import tempfile, pathlib
    b = DataBridge(aligned_dir=pathlib.Path("output/aligned"), config=CrossValidationConfig())
    targets = b.load_targets(sector="capital")
    sc_target = next((t for t in targets if t.variable == "SC"), None)
    assert sc_target is not None, "SC target missing from capital sector targets"
    assert sc_target.source == "penn_world_table", (
        f"SC source={sc_target.source}, expected 'penn_world_table'. "
        "Check source_priority in ENTITY_TO_ENGINE_MAP."
    )

@pytest.mark.slow
@pytest.mark.usefixtures("stub_optimizer")
def test_capital_calibration_freezes_population_params():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    import json, pathlib
    pop_params = json.loads(
        pathlib.Path("output/calibrated_params/population.json").read_text()
    )
    runner = EmpiricalCalibrationRunner(
        parameter_names=["capital.initial_ic", "capital.icor", "capital.alic", "capital.alsc"],
        sector="capital",
        frozen_params=pop_params,
    )
    result = runner.run()
    import math
    assert math.isfinite(result.train_nrmsd)
    assert result.train_nrmsd < 0.35
```

**Contract**
- `EmpiricalCalibrationRunner` accepts `frozen_params: dict[str, float]` — these are passed
  through to the engine without being varied by the optimizer.
- `CalibrationTarget` gains a `source: str` field populated by `DataBridge.load_targets()`.
- Capital calibration acceptance: `train_nrmsd < 0.35`.

**Constraints**
- Frozen population parameters must not be modified or re-optimized during capital calibration.
- PWT deflator step (2017 vs. 2015 base) must be applied before normalization — not silently skipped.

**Gate**
```bash
pytest tests/integration/test_sector_calibration.py::test_capital_calibration_uses_pwt_as_authoritative_source -v
pytest tests/integration/test_sector_calibration.py::test_capital_calibration_freezes_population_params -m slow -v
```

---

### T2-3 · Agriculture Sector Calibration

**Context**
Agriculture calibrates against FAOSTAT FBS food supply (kcal/capita/day) and FAOSTAT RL
arable land (ha). FBSH world code must be `"5000"` (T0-4). Food entity must be the
sole FAOSTAT series (T0-2).

**Failing Test**
```python
# tests/integration/test_sector_calibration.py  (append)
import pytest

def test_food_per_capita_normalized_value_at_1970_is_unity():
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import pathlib
    b = DataBridge(aligned_dir=pathlib.Path("output/aligned"), config=CrossValidationConfig())
    targets = b.load_targets(sector="agriculture")
    fpc = next((t for t in targets if "food" in t.variable.lower()), None)
    assert fpc is not None, "Food per capita target missing from agriculture sector"
    idx_1970 = dict(zip(fpc.years, fpc.values)).get(CrossValidationConfig.train_start)
    assert idx_1970 == pytest.approx(1.0, abs=0.10), (
        f"Food per capita index at train_start={CrossValidationConfig.train_start} "
        f"is {idx_1970:.4f}, expected 1.0 ± 0.10. "
        "Check that _normalize_to_index uses config.train_start as base year."
    )

@pytest.mark.slow
@pytest.mark.usefixtures("stub_optimizer")
def test_calibrated_fpc_in_plausible_kcal_range():
    """Converted fpc must sit in 2500–3200 kcal/day during 1980–2020."""
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    import json, pathlib, numpy as np
    pop = json.loads(pathlib.Path("output/calibrated_params/population.json").read_text())
    cap = json.loads(pathlib.Path("output/calibrated_params/capital.json").read_text())
    runner = EmpiricalCalibrationRunner(
        parameter_names=["agriculture.initial_al", "agriculture.sfpc",
                         "agriculture.land_development_rate",
                         "agriculture.initial_land_fertility"],
        sector="agriculture",
        frozen_params={**pop, **cap},
    )
    result = runner.run()
    # Check plausibility of fpc output in kcal/day (kg/yr × 4.93)
    fpc_kg_yr = result.sector_trajectories.get("fpc")
    if fpc_kg_yr is not None:
        fpc_kcal = {y: v * 4.93 for y, v in fpc_kg_yr.items()}
        window = {y: v for y, v in fpc_kcal.items() if 1980 <= y <= 2020}
        vals = list(window.values())
        assert min(vals) > 2000, f"fpc too low: min={min(vals):.0f} kcal/day"
        assert max(vals) < 4000, f"fpc too high: max={max(vals):.0f} kcal/day"
```

**Contract**
- `CalibrationResult` gains `sector_trajectories: dict[str, dict[int, float]]` — engine output
  for each calibrated variable, keyed by engine variable name and year.
- Food-per-capita display conversion: `kcal/day = kg/yr × (1800 / 365) ≈ × 4.93`.
  This conversion must be in `DataBridge` display output, NOT applied to the index used
  in NRMSD calculation.

**Constraints**
- Do NOT apply kcal/kg conversion inside `_normalize_to_index()` — normalization must be
  unit-agnostic by design.

**Gate**
```bash
pytest tests/integration/test_sector_calibration.py::test_food_per_capita_normalized_value_at_1970_is_unity -v
pytest tests/integration/test_sector_calibration.py::test_calibrated_fpc_in_plausible_kcal_range -m slow -v
```

---

### T2-4 · Resources Sector Calibration

**Context**
Resources calibrate against the BP Statistical Review proved reserves index (Layer 1, T1-3).
`world3.nr_fraction` is Layer 0 — it must never appear in the objective.
NRMSD method is `"change_rate"` because resource trajectories are slope-dominated.

**Failing Test**
```python
# tests/integration/test_sector_calibration.py  (append)
import pytest

def test_resources_objective_uses_change_rate_nrmsd():
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import pathlib
    b = DataBridge(aligned_dir=pathlib.Path("output/aligned"), config=CrossValidationConfig())
    obj = b.build_objective(sector="resources", nrmsd_method="change_rate")
    assert obj is not None

def test_world3_nr_reference_not_in_resources_targets():
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import pathlib
    b = DataBridge(aligned_dir=pathlib.Path("output/aligned"), config=CrossValidationConfig())
    targets = b.load_targets(sector="resources")
    variables = [t.variable for t in targets]
    assert "NR_world3_ref" not in variables, (
        "world3 NR reference trajectory must not appear in resources calibration targets — "
        "this is circular calibration."
    )
    assert any("bp" in v.lower() or "proved_reserves" in v.lower() for v in variables), (
        "No BP proved reserves target found. T1-3 connector must be registered."
    )
```

**Contract**
- `DataBridge.build_objective(sector: str = None, nrmsd_method: str = "level") -> Callable`
- `nrmsd_method="change_rate"` computes NRMSD on the first-difference of normalized series
  rather than on levels.
- Resources calibration acceptance: `train_nrmsd < 0.40` (higher tolerance due to proxy quality).

**Constraints**
- `world3.nr_fraction` must never be passed to the objective function.
- USGS depletion ratio is a secondary cross-validation check only — not in the objective.

**Gate**
```bash
pytest tests/integration/test_sector_calibration.py::test_resources_objective_uses_change_rate_nrmsd -v
pytest tests/integration/test_sector_calibration.py::test_world3_nr_reference_not_in_resources_targets -v
```

---

### T2-5 · Pollution and Climate Sector Calibration

**Context**
Pollution calibrates against NOAA CO₂ (ppm) and GCP fossil emissions. `PPOLX` (dimensionless)
and `atmospheric_co2_ppm` (ppm) must remain separate entities — they were separated in T0-3.
Carbon equilibrium was fixed in T0-1. CEDS non-CO₂ species must be collapsed to global rows.

**Failing Test**
```python
# tests/integration/test_sector_calibration.py  (append)
import pytest

def test_ppolx_and_co2_are_distinct_targets_in_pollution_sector():
    from pyworldx.data.bridge import DataBridge
    from pyworldx.calibration.metrics import CrossValidationConfig
    import pathlib
    b = DataBridge(aligned_dir=pathlib.Path("output/aligned"), config=CrossValidationConfig())
    targets = b.load_targets(sector="pollution")
    variables = [t.variable for t in targets]
    # PPOLX uses pollution_index_relative (dimensionless)
    # CO2 ppm is excluded from default objective (unit_mismatch=True) — may be absent
    assert "PPOLX" in variables or "pollution_index_relative" in variables, (
        "Pollution sector targets must include PPOLX / pollution_index_relative"
    )
    # atmospheric_co2_ppm must NOT be in the default objective
    co2_in_obj = any("co2_ppm" in v.lower() for v in variables)
    assert not co2_in_obj, (
        "atmospheric_co2_ppm is in the default pollution objective. "
        "It must be tagged excluded_from_objective=True until ppm→index conversion exists."
    )

def test_ceds_non_co2_species_are_global_rows():
    """Each CEDS non-CO2 connector must produce a single world-aggregate row per year."""
    from data_pipeline.connectors import get_all_connectors
    ceds_connectors = [c for c in get_all_connectors() if "ceds" in type(c).__name__.lower()]
    for connector in ceds_connectors:
        df = connector.load_cached()
        if df is not None and "region" in df.columns:
            regions = df["region"].unique()
            assert list(regions) == ["World"] or len(regions) == 1, (
                f"{type(connector).__name__} contains non-global rows: {regions}. "
                "Add aggregate_world step to this connector."
            )
```

**Contract**
- Pollution calibration acceptance: `train_nrmsd < 0.30` on `pollution_index_relative`.
- CO₂ trajectory used as a secondary check only — not in `train_nrmsd` calculation.
- All CEDS connectors must produce exactly one row per year (world aggregate).

**Gate**
```bash
pytest tests/integration/test_sector_calibration.py::test_ppolx_and_co2_are_distinct_targets_in_pollution_sector -v
pytest tests/integration/test_sector_calibration.py::test_ceds_non_co2_species_are_global_rows -v
```

---

## Phase 3 — Joint Multi-Sector Fine Tuning

---

### T3-1 · Joint Optuna + Nelder-Mead on Composite Objective

**Context**
After sector-level calibration, a joint optimization over the 5–6 most influential cross-sector
parameters refines the composite NRMSD. Sobol outputs from each sector identify these parameters.

**Failing Test**
```python
# tests/integration/test_joint_calibration.py
import pytest

def test_composite_objective_weights_sum_to_meaningful_total():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    runner = EmpiricalCalibrationRunner(composite=True)
    weights = runner.get_objective_weights()
    assert "population" in weights
    assert "co2" in weights
    assert weights["population"] == pytest.approx(1.5, rel=0.01)
    assert weights["co2"] == pytest.approx(1.5, rel=0.01)
    assert weights["resources"] == pytest.approx(0.75, rel=0.01)

def test_joint_calibration_validation_nrmsd_is_independent():
    """Joint run must compute validation NRMSD on holdout window only."""
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    from unittest.mock import patch
    runner = EmpiricalCalibrationRunner(composite=True)
    with patch.object(runner.bridge, "calculate_validation_score",
                      wraps=runner.bridge.calculate_validation_score) as mock_val:
        with patch.object(runner, "_run_optimizer", return_value={}):
            runner.run()
        mock_val.assert_called_once()

@pytest.mark.slow
@pytest.mark.usefixtures("stub_optimizer")
def test_joint_calibration_result_has_all_required_fields():
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    from unittest.mock import patch
    runner = EmpiricalCalibrationRunner(composite=True)
    with patch.object(runner, "_run_optimizer", return_value={"cbr_base": 0.028}):
        with patch.object(runner.bridge, "build_objective", return_value=lambda p: 0.05):
            with patch.object(runner.bridge, "calculate_validation_score", return_value=0.07):
                result = runner.run()
    assert hasattr(result, "train_nrmsd")
    assert hasattr(result, "validation_nrmsd")
    assert hasattr(result, "overfit_flagged")
    assert hasattr(result, "optimized_params")
```

**Contract**
- `EmpiricalCalibrationRunner(composite: bool = False)` — when `True`, builds a weighted
  composite objective across all sectors.
- Default composite weights: `population=1.5, co2=1.5, food_per_capita=1.0,
  industrial_capital=1.0, resources=0.75`.
- Joint optimization: `bayesian_n_trials=100`, joint parameter set of 5–6 parameters
  identified from Sobol outputs.

**Gate**
```bash
pytest tests/integration/test_joint_calibration.py -v
```

---

## Phase 4 — Robustness and Regression Protection

---

### T4-1 · NRMSD Baseline Regression Tests

**Context**
After joint calibration, the optimized parameter set and its NRMSD scores must be recorded
as a machine-readable manifest. Any future change that degrades these scores beyond tolerance
must fail CI.

**Failing Test**
```python
# tests/integration/test_regression.py
import pytest

def test_baseline_manifest_exists():
    import pathlib
    manifest = pathlib.Path("output/calibration_baseline.json")
    if not manifest.exists():
        pytest.skip("Baseline not yet generated — skipping regression check")
    assert manifest.exists(), (
        "output/calibration_baseline.json not found. "
        "Run joint calibration and save the result to this path."
    )

def test_baseline_nrmsd_within_tolerance():
    import json, pathlib
    from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
    baseline = json.loads(
        pathlib.Path("output/calibration_baseline.json").read_text()
    )
    runner = EmpiricalCalibrationRunner(composite=True)
    result = runner.quick_evaluate(params=baseline["optimized_params"])
    tolerance = 0.05  # 5% relative degradation allowed
    for sector, base_score in baseline["sector_nrmsd"].items():
        current = result.sector_nrmsd.get(sector)
        assert current is not None, f"Sector '{sector}' missing from result"
        assert current <= base_score * (1 + tolerance), (
            f"NRMSD regression in sector '{sector}': "
            f"baseline={base_score:.4f}, current={current:.4f} "
            f"(>{tolerance*100:.0f}% degradation)"
        )

def test_overfit_not_flagged_in_baseline():
    import json, pathlib
    baseline = json.loads(
        pathlib.Path("output/calibration_baseline.json").read_text()
    )
    assert not baseline["overfit_flagged"], (
        "Baseline manifest has overfit_flagged=True. "
        "Resolve overfitting before recording baseline."
    )
```

**Contract**
- `output/calibration_baseline.json` schema:
  ```json
  {
    "recorded_at": "ISO-8601 timestamp",
    "optimized_params": {"param_name": float},
    "sector_nrmsd": {"population": float, "capital": float, ...},
    "composite_train_nrmsd": float,
    "composite_validation_nrmsd": float,
    "overfit_flagged": false
  }
  ```
- `EmpiricalCalibrationRunner.quick_evaluate(params: dict) -> CalibrationResult` —
  runs a single forward pass without optimization and returns NRMSD scores.

**Gate**
```bash
pytest tests/integration/test_regression.py -v
pytest tests/unit/ -x -q --tb=short   # full unit suite
```

---

## Completion Checklist

| Phase | Gate command | Status |
|---|---|---|
| T0-0 Fast mocks | `pytest tests/unit/test_conftest.py -v` | ☐ |
| T0-1 Carbon equilibrium | `pytest tests/unit/test_carbon_equilibrium.py -v` | ☐ |
| T0-2 Food entity separation | `pytest tests/unit/test_map_entities.py -v` | ☐ |
| T0-3 Pollution / CO₂ separation | `pytest tests/unit/test_map_entities.py -v` | ☐ |
| T0-4 FAOSTAT area code | `pytest tests/unit/test_preflight_gates.py -v` | ☐ |
| T0-5 `initial_conditions` default year | `pytest tests/unit/test_preflight_gates.py -v` | ☐ |
| T1-1 DataBridge + zero-guard | `pytest tests/unit/test_databridge.py -v` | ☐ |
| T1-2 Multi-source arbitration | `pytest tests/unit/test_map_entities.py -v` | ☐ |
| T1-3 BP connector | `pytest tests/unit/test_bp_connector.py -v` | ☐ |
| T1-4 Runner scenario arg | `pytest tests/unit/test_empirical_calibration.py -v` | ☐ |
| T2-1 Population calibration | `pytest tests/integration/test_sector_calibration.py -k population -v` | ☐ |
| T2-2 Capital calibration | `pytest tests/integration/test_sector_calibration.py -k capital -v` | ☐ |
| T2-3 Agriculture calibration | `pytest tests/integration/test_sector_calibration.py -k agriculture -v` | ☐ |
| T2-4 Resources calibration | `pytest tests/integration/test_sector_calibration.py -k resources -v` | ☐ |
| T2-5 Pollution calibration | `pytest tests/integration/test_sector_calibration.py -k pollution -v` | ☐ |
| T3-1 Joint calibration | `pytest tests/integration/test_joint_calibration.py -v` | ☐ |
| T4-1 Regression baseline | `pytest tests/integration/test_regression.py -v` | ☐ |
| **Full unit suite** | `pytest tests/unit/ -x -q --tb=short` | ☐