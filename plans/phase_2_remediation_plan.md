# Phase 2 Remediation Plan (v2 — post-review)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 23 verified defects in the Phase 2 implementation of pyWorldX — wire open loops, fix copy-paste bugs, unify duplicated state, add missing tests, connect the data pipeline, and restore capital conservation — so the biophysical/socioeconomic couplings described in the Notebook Conversations execute end-to-end.

**Architecture:** Six sequenced phases respecting dependency order: (0) test harness — shared pytest fixtures that all TDD tasks depend on; (A) engine orchestration; (B) economic/financial linkage; (C) biophysical unification; (D) demographic consequences; (E) data + testing; (F) finalization — self-reflect + KB update per CLAUDE.md.

**Tech Stack:** Python 3.11+, pytest, mypy strict, ruff, Poetry, Quantity-based unit-safe arithmetic.

---

## Verified State & Corrections to the Draft

Baked in from the verification pass plus the Plan Review Gate findings:

1. **Cobb-Douglas TFP (A) IS already calibrated.** [capital.py:102-117](../pyworldx/sectors/capital.py#L102-L117) sets `_CD_TFP = 1.924445e8` which produces IO(1900) ≈ 6.65e10. **Remove from scope.**
2. **`energy_supply_factor` already read by agriculture.py** ([agriculture.py:129](../pyworldx/sectors/agriculture.py#L129)). Capital half remains.
3. **`financial_resilience` is already declared as a write** in [finance.py:245](../pyworldx/sectors/finance.py#L245). The fix is a one-sided read wiring in `capital.py`.
4. **`tech_metals_availability` is already READ** by [energy_technology.py:125](../pyworldx/sectors/energy_technology.py#L125). Only the WRITE side needs a depletion model in `resources.py`.
5. **Engine try/except swallowing is in `_bootstrap_initial_state()` only** (lines 418, 457, 468). Main RK4 loop is unaffected.
6. **`Scenario.apply_policies(values, t)` ALREADY matches the Engine's `policy_applier` signature exactly.** Wiring is literally `Engine(policy_applier=scenario.apply_policies)` + a helper to apply `parameter_overrides` to sectors.
7. **Real class names:** `SEIRModule` (not `SEIRSector`), `BaseSector` Protocol (not `SectorBase`), `init_stocks(ctx)` method (not `stocks()`). **All tests must use the real names.**
8. **Coverage threshold is 100%** per [.coverage-thresholds.json](../.coverage-thresholds.json), not 90%. Every new code path needs test coverage.

---

## Risks (re-ordered by probability × severity)

| Rank | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | **Algebraic-loop convergence failure** (capital ↔ finance ↔ energy new reads create a non-converging fixed point) | RK4 crash; no output at all | Every new cross-sector read gets an `algebraic_loop_hints()` entry; Phase A acceptance includes a resolver-convergence test that does 200y + algebraic loop under the full Phase-2 sector set |
| 2 | Validation trajectory regression (Nebel 2023, 1900 IO baseline, World3 run) | Existing golden tests break | Task 0.2 pins trajectory snapshots before edits; each phase asserts ±1.5% of saved snapshot |
| 3 | SEIR ↔ Population double-counting (internal `deaths_i` + external `disease_death_rate` both reducing pop) | Population under-counts | SEIR stops mutating its internal dummy cohorts when `POP` is provided externally; only the exported `disease_death_rate` feeds population |
| 4 | `energy_demand` from capital/agriculture triggers ceiling at 1900 | Main economy suddenly constrained; scenarios look wildly different | Calibrate demand formulas against 1900 baseline (target: total demand < 22 EJ/yr at t=1900) |
| 5 | 5-stock carbon mass conservation violation after unification | GtC leaks between sectors | Task C4 writes mass-conservation test; must PASS to 1e-6 |
| 6 | 100% coverage gate blocking | PRs cannot merge | Every new file gets a test file in the same commit; no helper functions without tests |

---

## Phase 0 — Test Harness & Baseline Pinning

**Rationale:** Every TDD task below uses shared fixtures (`_base_shared`, `_ctx`, etc.). These do not exist today. Define them ONCE in a conftest so individual tasks can be short and focused.

### Task 0.1: Build shared test fixtures in `tests/conftest.py`

**Files:**
- Modify: `tests/conftest.py` (or create if absent)
- Create: `tests/_phase2_helpers.py`

- [ ] **Step 1: Write the helper module**

```python
"""Shared Phase 2 test fixtures — DO NOT import outside tests/."""
from __future__ import annotations
from typing import Any
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


def make_ctx(master_dt: float = 1.0) -> RunContext:
    return RunContext(master_dt=master_dt, t_start=1900.0, t_end=2100.0)


def base_shared(year: int = 2020, **overrides: float) -> dict[str, Quantity]:
    """Build a default shared-state dict for sector compute() tests."""
    defaults: dict[str, tuple[float, str]] = {
        "industrial_output": (1.0e11, "industrial_output_units"),
        "POP": (7.8e9, "people"),
        "IC": (2.0e11, "capital_units"),
        "SC": (1.0e11, "capital_units"),
        "AL": (1.4e9, "hectares"),
        "L": (1.0e10, "capital_units"),
        "D_g": (0.0, "capital_units"),
        "D_s": (0.0, "capital_units"),
        "D_p": (0.0, "capital_units"),
        "service_output_per_capita": (500.0, "service_units_per_capita"),
        "food_per_capita": (400.0, "food_units_per_capita"),
        "temperature_anomaly": (1.0, "deg_C_anomaly"),
        "labor_force_multiplier": (1.0, "dimensionless"),
        "energy_supply_factor": (1.0, "dimensionless"),
        "financial_resilience": (1.5, "dimensionless"),
        "C_atm": (850.0, "GtC"),
        "tnds_aes": (0.0, "capital_units"),
        "education_tnds": (0.0, "capital_units"),
        "damages_tnds": (0.0, "capital_units"),
        "disease_death_rate": (0.0, "per_year"),
    }
    d: dict[str, Quantity] = {k: Quantity(v, u) for k, (v, u) in defaults.items()}
    for k, v in overrides.items():
        unit = defaults.get(k, (0.0, "dimensionless"))[1]
        d[k] = Quantity(float(v), unit)
    return d
```

- [ ] **Step 2: Write a minimal test verifying fixtures load**

```python
# tests/unit/test_phase2_helpers.py
def test_base_shared_has_defaults() -> None:
    from tests._phase2_helpers import base_shared
    s = base_shared()
    assert s["POP"].magnitude == 7.8e9
    assert s["industrial_output"].magnitude == 1.0e11
```

- [ ] **Step 3: Run — PASS**
- [ ] **Step 4: Commit**

```bash
git add tests/_phase2_helpers.py tests/unit/test_phase2_helpers.py
git commit -m "test: add Phase 2 shared fixtures (base_shared, make_ctx)"
```

### Task 0.2: Pin 1900 baseline + Nebel 2023 trajectory snapshots

**Files:**
- Create: `tests/integration/test_regression_baselines.py`
- Create: `tests/integration/fixtures/nebel_2023_snapshot.npz`

- [ ] **Step 1: Write failing test that PINS current output**

```python
"""Pin 1900 baseline + Nebel 2023 trajectory; fail loudly if Phase 2 edits shift them."""
from __future__ import annotations
import numpy as np
import pytest
from pathlib import Path
from pyworldx.core.engine import Engine
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector

_SNAPSHOT = Path(__file__).parent / "fixtures" / "nebel_2023_snapshot.npz"


def _run_phase1_only() -> dict[str, np.ndarray]:
    engine = Engine(
        sectors=[
            PopulationSector(), CapitalSector(), AgricultureSector(),
            ResourcesSector(), PollutionSector(),
        ],
        t_start=1900.0, t_end=2100.0, master_dt=1.0,
    )
    result = engine.run()
    return {k: np.asarray(v) for k, v in result.trajectories.items()}


def test_1900_baseline_io_pinned() -> None:
    traj = _run_phase1_only()
    assert "industrial_output" in traj, "engine must record industrial_output observable"
    io_1900 = float(traj["industrial_output"][0])
    assert 6.5e10 <= io_1900 <= 6.8e10, f"got {io_1900:.3e}"


@pytest.mark.skipif(not _SNAPSHOT.exists(), reason="snapshot not yet baselined")
def test_nebel_2023_trajectory_within_tolerance() -> None:
    traj = _run_phase1_only()
    snapshot = np.load(_SNAPSHOT)
    for key in ("POP", "industrial_output", "food_per_capita"):
        current = traj[key]
        pinned = snapshot[key]
        # 1.5% RMS tolerance
        rms_err = float(np.sqrt(np.mean((current - pinned) ** 2)) / np.mean(np.abs(pinned)))
        assert rms_err < 0.015, f"{key} drifted {rms_err*100:.2f}% from pinned snapshot"
```

- [ ] **Step 2: Run to seed snapshot**

```bash
.venv/bin/python -c "
import numpy as np, pathlib
from tests.integration.test_regression_baselines import _run_phase1_only
t = _run_phase1_only()
pathlib.Path('tests/integration/fixtures').mkdir(parents=True, exist_ok=True)
np.savez('tests/integration/fixtures/nebel_2023_snapshot.npz', **{k: np.asarray(v) for k,v in t.items() if v.ndim == 1})
"
.venv/bin/python -m pytest tests/integration/test_regression_baselines.py -v
# Both tests must PASS after seeding
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_regression_baselines.py tests/integration/fixtures/
git commit -m "test: pin 1900 IO baseline + Nebel 2023 trajectory snapshot"
```

**Phase 0 Acceptance:** Both regression tests green; pre-existing `tests/` suite still green; commit tagged `phase-2-remediation-0-complete`.

---

## Phase A — Engine Core & Orchestration

### Task A1: Surface KeyError/ZeroDivisionError in bootstrap (strict_bootstrap flag)

**Files:**
- Modify: `pyworldx/core/engine.py:70-84` (add `strict_bootstrap` param) and `:418-419, 457-458, 468-469` (conditional re-raise)
- Create: `tests/unit/test_engine_strict_bootstrap.py`

- [ ] **Step 1: Write failing test using the REAL base class**

```python
"""Test strict_bootstrap=True surfaces missing-input errors."""
from __future__ import annotations
import pytest
from pyworldx.core.engine import Engine
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import BaseSector, RunContext


class _BrokenSector:
    """Minimal BaseSector-compatible duck type that reads a missing key."""
    name = "broken"
    version = "0.0.1"
    timestep_hint: float | None = None

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {}

    def compute(self, t: float, stocks, inputs, ctx: RunContext) -> dict[str, Quantity]:
        _ = inputs["nonexistent_key"]  # triggers KeyError
        return {}

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {}

    def declares_reads(self) -> list[str]:
        return ["nonexistent_key"]

    def declares_writes(self) -> list[str]:
        return []


def test_strict_bootstrap_raises() -> None:
    engine = Engine(sectors=[_BrokenSector()], strict_bootstrap=True,
                    t_start=1900.0, t_end=1900.0, master_dt=1.0)
    with pytest.raises(KeyError):
        engine.run()


def test_nonstrict_bootstrap_preserves_legacy() -> None:
    engine = Engine(sectors=[_BrokenSector()], strict_bootstrap=False,
                    t_start=1900.0, t_end=1900.0, master_dt=1.0)
    engine.run()  # must not raise
```

- [ ] **Step 2: Run — FAIL** (TypeError: unexpected kwarg `strict_bootstrap`)

- [ ] **Step 3: Implement**

In `Engine.__init__`, add parameter `strict_bootstrap: bool = False`, store as `self._strict_bootstrap`. Replace each of the three `except (KeyError, ZeroDivisionError): pass` blocks with:

```python
except (KeyError, ZeroDivisionError):
    if self._strict_bootstrap:
        raise
```

- [ ] **Step 4: Run — PASS + regression baselines still PASS**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(engine): add strict_bootstrap flag to surface bootstrap errors"
```

### Task A2: Wire Scenario into Engine via the existing `apply_policies`

**Files:**
- Modify: `pyworldx/scenarios/scenario.py` (add `apply_parameter_overrides(sectors)` helper)
- Create: `tests/integration/test_scenario_application.py`

**Key insight:** `Scenario.apply_policies(values, t)` already exists with the exact signature Engine needs. The only missing piece is applying `parameter_overrides` to sector instances BEFORE Engine construction.

- [ ] **Step 1: Write failing test**

```python
"""Test Scenario.apply_parameter_overrides mutates sector attributes."""
from __future__ import annotations
from pyworldx.sectors.capital import CapitalSector
from pyworldx.scenarios.v2_scenarios import minsky_moment, absolute_decoupling


def test_parameter_overrides_mutate_sector() -> None:
    from pyworldx.scenarios.scenario import apply_parameter_overrides
    scen = absolute_decoupling()
    cap = CapitalSector()
    # Default resource elasticity should be ~0.20 (Cobb-Douglas β)
    original_beta = cap.resource_elasticity
    apply_parameter_overrides(scen, [cap])
    assert cap.resource_elasticity == 0.0, "scenario must override to β=0"


def test_scenario_apply_policies_matches_engine_signature() -> None:
    from pyworldx.core.engine import Engine
    from pyworldx.sectors.population import PopulationSector
    scen = minsky_moment()
    engine = Engine(
        sectors=[PopulationSector()],
        policy_applier=scen.apply_policies,  # already matches signature
        t_start=1900.0, t_end=1901.0, master_dt=1.0,
    )
    engine.run()  # must not raise
```

- [ ] **Step 2: Run — FAIL** (`apply_parameter_overrides` not defined; `CapitalSector.resource_elasticity` may be constant not attr)

- [ ] **Step 3: Implement**

Add to `pyworldx/scenarios/scenario.py`:

```python
def apply_parameter_overrides(scenario: Scenario, sectors: list[Any]) -> None:
    """Mutate sector instances in-place with scenario.parameter_overrides.

    Format: "{sector_name}.{attr}" → value
    Silently skips unknown sectors/attrs (logs warning).
    """
    for dotted_key, value in scenario.parameter_overrides.items():
        if "." not in dotted_key:
            continue
        sector_name, attr = dotted_key.split(".", 1)
        target = next((s for s in sectors if s.name == sector_name), None)
        if target is None:
            continue
        if hasattr(target, attr):
            setattr(target, attr, value)
```

In `CapitalSector.__init__`, if `resource_elasticity` is a module constant `_CD_BETA`, expose it as an instance attribute: `self.resource_elasticity = _CD_BETA`.

- [ ] **Step 4: Run — PASS** + regression baselines still green
- [ ] **Step 5: Commit**

### Task A3: CentralRegistrar — demand-weighted fallback when weights default to 1.0

**Files:**
- Modify: `pyworldx/core/central_registrar.py:211-260` (refactor `_allocate`)
- Modify: `tests/unit/test_central_registrar.py` (add fallback test)

- [ ] **Step 1: Write failing test**

```python
from pyworldx.core.central_registrar import CentralRegistrar, _EJ_SCALE
from pyworldx.core.quantities import Quantity


def test_allocation_falls_back_to_demand_weighted_when_weights_missing() -> None:
    """Under missing weights, small sector gets small allocation (proportional)."""
    registrar = CentralRegistrar(energy_ceiling=1.0)  # ceiling off; test only allocator
    # Supply = 50 EJ, total demand = 100 EJ → multipliers avg 0.5
    shared = {
        "fossil_output": Quantity(50.0 / _EJ_SCALE, "energy_units"),
        "sustainable_output": Quantity(0.0, "energy_units"),
        "technology_output": Quantity(0.0, "energy_units"),
        "energy_demand_big":   Quantity(90.0 / _EJ_SCALE, "energy_units"),
        "energy_demand_small": Quantity(10.0 / _EJ_SCALE, "energy_units"),
    }
    registrar.resolve(shared)
    mb = shared["supply_multiplier_big"].magnitude
    ms = shared["supply_multiplier_small"].magnitude
    # Demand-weighted: both get SAME multiplier (share of supply ∝ share of demand)
    assert abs(mb - ms) < 0.01
    # Each multiplier ≈ total_supply / total_demand = 50/100 = 0.5
    assert 0.48 <= mb <= 0.52
```

- [ ] **Step 2: Run — FAIL** (currently splits equally → mb=0.5/90=0.0056, ms=0.5/10=0.05)

- [ ] **Step 3: Implement** — in `_allocate`, detect when ALL DemandRecords have `liquid_funds == 1.0` AND `security_value == 1.0` (i.e. defaults), and return demand-weighted multipliers: `multipliers[name] = total_supply / total_demand` (the same scalar for all).

- [ ] **Step 4: PASS** + regression green
- [ ] **Step 5: Commit**

**Note:** `_EJ_SCALE` is currently module-private. Expose it: remove leading underscore or add an explicit re-export. Add this as a sub-step in the commit.

### Task A4: Broadcast global `energy_supply_factor`

**Files:**
- Modify: `pyworldx/core/central_registrar.py:195-210`

- [ ] **Step 1: Write failing test**

```python
def test_registrar_writes_global_energy_supply_factor() -> None:
    from pyworldx.core.central_registrar import CentralRegistrar, _EJ_SCALE
    from pyworldx.core.quantities import Quantity
    registrar = CentralRegistrar()
    shared = {
        "fossil_output": Quantity(1e11, "energy_units"),
        "sustainable_output": Quantity(0, "energy_units"),
        "technology_output": Quantity(0, "energy_units"),
        "energy_demand_test": Quantity(2e11, "energy_units"),
    }
    registrar.resolve(shared)
    esf = shared["energy_supply_factor"].magnitude
    assert 0.0 < esf < 1.0
```

- [ ] **Step 2-5:** FAIL → implement `shared["energy_supply_factor"] = Quantity(min(total_supply / max(total_demand,1e-10), 1.0), "dimensionless")` in `resolve()` → PASS + commit

### Task A5: Algebraic-loop convergence smoke test for full Phase-2 sector set

**Files:**
- Create: `tests/integration/test_phase2_loop_convergence.py`

**Rationale:** Risk #1 — ensure the new cross-sector reads don't create a diverging fixed-point iteration.

- [ ] **Step 1: Write failing test (will start passing once Phases B-D wire the reads)**

```python
@pytest.mark.slow
def test_full_phase2_sector_set_converges_at_bootstrap() -> None:
    """200y run with ALL Phase 2 sectors; succeed = no LoopDivergenceError."""
    from tests._phase2_helpers import make_phase2_sectors  # helper from Task E1
    engine = Engine(
        sectors=make_phase2_sectors(),
        t_start=1900.0, t_end=2100.0, master_dt=1.0,
        strict_bootstrap=True,
        loop_max_iter=200,  # generous
    )
    result = engine.run()  # should not raise LoopDivergenceError
    assert len(result.time_index) == 201
```

- [ ] **Step 2-5:** This test is EXPECTED TO FAIL until Phase E1 ships. Mark `@pytest.mark.phase2_remediation_final` and skip until then. Commit the skipped test now so we don't forget it.

**Phase A Acceptance Criteria:**
- [ ] Regression baselines green (`test_regression_baselines.py`)
- [ ] A1, A2, A3, A4 tests green
- [ ] A5 exists as a skipped marker
- [ ] Commit tagged: `phase-2-remediation-A-complete`

---

## Phase B — Economic & Financial Linkage

### Task B1: Fix finance.py military_fraction copy-paste bug

**Files:**
- Modify: `pyworldx/sectors/finance.py:__init__, :181, declares_writes`

**Calibration note:** `reinvestment_fraction = 0.30` (OECD corporate retention rate for non-financial firms typically 25–35% of post-tax profits — see OECD National Accounts / "S.11 Non-financial corporations, retained earnings as share of gross entrepreneurial income"). Using 0.30 as midpoint; it's tunable against the 1900 baseline in Task 0.2.

- [ ] **Step 1: Write failing test**

```python
def test_finance_uses_reinvestment_not_military_fraction() -> None:
    from pyworldx.sectors.finance import FinanceSector
    from tests._phase2_helpers import base_shared, make_ctx
    finance = FinanceSector(military_fraction=0.02, reinvestment_fraction=0.30)
    shared = base_shared()
    stocks = finance.init_stocks(make_ctx())
    out = finance.compute(2020.0, stocks, shared, make_ctx())
    assert "investments" in out
    profit = out["profit"].magnitude
    assert out["investments"].magnitude == pytest.approx(profit * 0.30, rel=0.01)
```

- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implement** — add `reinvestment_fraction: float = 0.30` kwarg, change line 181 to `investments = profit * self.reinvestment_fraction`, add `"investments"` to `declares_writes()` and return dict.
- [ ] **Step 4-5: PASS + commit**

### Task B2: Emit `education_tnds` from human_capital.py

**Calibration note:** `edu_cost_factor = 0.05` — UNESCO Institute for Statistics reports global public + private education spending averages ~5% of GDP (range 3.5–6.5% across OECD). [Source: UIS Global Education Monitoring Report 2021.]

**Files:**
- Modify: `pyworldx/sectors/human_capital.py`

- [ ] **Step 1: Write failing test**

```python
def test_human_capital_emits_education_tnds() -> None:
    from pyworldx.sectors.human_capital import HumanCapitalSector
    from tests._phase2_helpers import base_shared, make_ctx
    hc = HumanCapitalSector(edu_cost_factor=0.05)
    shared = base_shared(year=2020)
    out = hc.compute(2020.0, hc.init_stocks(make_ctx()), shared, make_ctx())
    assert "education_tnds" in out
    # At SOPC=500 × POP=7.8e9 × 0.05 ≈ 1.95e11
    assert 1.5e11 <= out["education_tnds"].magnitude <= 2.5e11
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task B3: Emit `damages_tnds` from welfare.py

**Files:**
- Modify: `pyworldx/sectors/welfare.py`

- [ ] **Step 1: Write failing test** — identical pattern to B2 but reading welfare's `climate_damages` + `pollution_damages` aggregate.
- [ ] **Step 2-5:** FAIL → implement → PASS + commit

### Task B4: Audit and aggregate ALL TNDS sources in finance.py

**Files:**
- Modify: `pyworldx/sectors/finance.py` — declares_reads includes `tnds_aes`, `education_tnds`, `damages_tnds`, plus discover any others

**Audit step:**

- [ ] **Step 1: Grep for any other sector writing a `_tnds` or `tnds_*` key**

```bash
.venv/bin/python -c "
import subprocess
for key in ['_tnds', 'tnds_']:
    r = subprocess.run(['grep', '-rn', key, 'pyworldx/sectors/'], capture_output=True, text=True)
    print(f'=== {key} ===\n{r.stdout}')
"
```

- [ ] **Step 2: Write failing test enumerating every TNDS source found**

```python
def test_finance_aggregates_every_tnds() -> None:
    from pyworldx.sectors.finance import FinanceSector
    from tests._phase2_helpers import base_shared, make_ctx
    finance = FinanceSector()
    # Check that EVERY discovered tnds_* var is in declares_reads
    expected_tnds = {"tnds_aes", "education_tnds", "damages_tnds"}  # extend after audit
    reads = set(finance.declares_reads())
    assert expected_tnds <= reads, f"missing: {expected_tnds - reads}"
    # Behavioural: dL must drop when any tnds increases
    shared_lo = base_shared(tnds_aes=0.0, education_tnds=0.0, damages_tnds=0.0)
    shared_hi = base_shared(tnds_aes=5e10, education_tnds=2e11, damages_tnds=1e10)
    out_lo = finance.compute(2020.0, finance.init_stocks(make_ctx()), shared_lo, make_ctx())
    out_hi = finance.compute(2020.0, finance.init_stocks(make_ctx()), shared_hi, make_ctx())
    assert out_hi["d_L"].magnitude < out_lo["d_L"].magnitude
```

- [ ] **Step 3-5: FAIL → implement TNDS aggregation → PASS + commit**

### Task B5: Emit `labor_force_multiplier` from seir.py (SEIRModule)

**Files:**
- Modify: `pyworldx/sectors/seir.py` (`SEIRModule` class) — verify it already writes `labor_force_multiplier` per the class docstring; if not, add

- [ ] **Step 1: Grep to verify current state**

```bash
grep -n "labor_force_multiplier" pyworldx/sectors/seir.py
```

- [ ] **Step 2: If already written, skip to B6; else write failing test**

```python
def test_seir_exports_labor_force_multiplier() -> None:
    from pyworldx.sectors.seir import SEIRModule
    from tests._phase2_helpers import make_ctx
    seir = SEIRModule(initial_infected_fraction=0.1)
    stocks = seir.init_stocks(make_ctx())
    out = seir.compute(2020.0, stocks, {}, make_ctx())
    assert "labor_force_multiplier" in out
    lfm = out["labor_force_multiplier"].magnitude
    assert 0.5 <= lfm <= 1.0
```

- [ ] **Step 3-5: FAIL → implement → PASS + commit**

### Task B6: Read `labor_force_multiplier` in capital.py

**Files:**
- Modify: `pyworldx/sectors/capital.py` (declares_reads + multiply H^γ term by LFM^γ)

- [ ] **Step 1: Write failing test**

```python
def test_capital_io_drops_under_pandemic() -> None:
    from pyworldx.sectors.capital import CapitalSector
    from tests._phase2_helpers import base_shared, make_ctx
    cap = CapitalSector()
    healthy = base_shared(labor_force_multiplier=1.0)
    pandemic = base_shared(labor_force_multiplier=0.7)
    h = cap.compute(2020.0, cap.init_stocks(make_ctx()), healthy, make_ctx())
    p = cap.compute(2020.0, cap.init_stocks(make_ctx()), pandemic, make_ctx())
    ratio = p["industrial_output"].magnitude / h["industrial_output"].magnitude
    # γ=0.55; 0.7^0.55 ≈ 0.824
    assert 0.80 <= ratio <= 0.85
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task B7: Emit `energy_demand_capital` from capital.py

**Files:**
- Modify: `pyworldx/sectors/capital.py`

**Calibration:** `energy_intensity_capital` tuned so `energy_demand_capital(1900) * _EJ_SCALE < 15 EJ/yr`. IO(1900) ≈ 6.65e10; target 10 EJ → intensity ≈ `10 / (6.65e10 * _EJ_SCALE)` ≈ 7.7e-1.

- [ ] **Step 1: Write failing test**

```python
def test_capital_emits_energy_demand_within_1900_budget() -> None:
    from pyworldx.sectors.capital import CapitalSector
    from pyworldx.core.central_registrar import _EJ_SCALE
    from tests._phase2_helpers import base_shared, make_ctx
    cap = CapitalSector()
    shared = base_shared()
    # override to 1900 conditions
    shared["industrial_output"] = Quantity(6.65e10, "industrial_output_units")
    out = cap.compute(1900.0, cap.init_stocks(make_ctx()), shared, make_ctx())
    assert "energy_demand_capital" in out
    ed_ej = out["energy_demand_capital"].magnitude * _EJ_SCALE
    assert ed_ej < 15.0, f"1900 capital demand = {ed_ej:.1f} EJ/yr; budget < 15"
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task B8: Read `energy_supply_factor` in capital.py

**Files:**
- Modify: `pyworldx/sectors/capital.py`

- [ ] **Step 1-5:** TDD cycle for IO drop under ESF<1.

### Task B9: Read `financial_resilience` in capital.py → gate investment

**Files:**
- Modify: `pyworldx/sectors/capital.py` (gate `FIOAI`-derived investment when total_debt>0)

- [ ] **Step 1: Write failing test**

```python
def test_capital_investment_gated_by_financial_resilience() -> None:
    from pyworldx.sectors.capital import CapitalSector
    from tests._phase2_helpers import base_shared, make_ctx
    cap = CapitalSector()
    solvent = base_shared(financial_resilience=1.5)
    minsky  = base_shared(financial_resilience=0.3)
    d_ic_s = cap.compute(2020.0, cap.init_stocks(make_ctx()), solvent, make_ctx())["d_IC"].magnitude
    d_ic_m = cap.compute(2020.0, cap.init_stocks(make_ctx()), minsky,  make_ctx())["d_IC"].magnitude
    assert d_ic_m < d_ic_s * 0.5
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task B10: Capital conservation — subtract energy-sector investments from capital.py allocation

**Files:**
- Modify: `pyworldx/sectors/capital.py` (declares_reads includes `tech_sector_investment`, `sustainable_sector_investment`; subtracts them from `IC` allocation before FIOAI split)
- Modify: `pyworldx/sectors/energy_technology.py` (expose `tech_sector_investment` as declared write — currently computed internally at line 96)
- Modify: `pyworldx/sectors/energy_sustainable.py` (same)

**Addresses Report §4I (Energy Stealing / Capital Conservation).**

- [ ] **Step 1: Write failing test**

```python
def test_energy_investments_subtract_from_capital_allocation() -> None:
    from pyworldx.sectors.capital import CapitalSector
    from tests._phase2_helpers import base_shared, make_ctx
    cap = CapitalSector()
    no_energy = base_shared()
    no_energy["tech_sector_investment"] = Quantity(0.0, "capital_units")
    no_energy["sustainable_sector_investment"] = Quantity(0.0, "capital_units")
    with_energy = dict(no_energy)
    with_energy["tech_sector_investment"] = Quantity(1e9, "capital_units")
    with_energy["sustainable_sector_investment"] = Quantity(5e8, "capital_units")
    d_ic_no = cap.compute(2020.0, cap.init_stocks(make_ctx()), no_energy, make_ctx())["d_IC"].magnitude
    d_ic_yes= cap.compute(2020.0, cap.init_stocks(make_ctx()), with_energy, make_ctx())["d_IC"].magnitude
    # d_IC_yes should be lower (energy sectors siphoned capital)
    assert d_ic_yes == pytest.approx(d_ic_no - 1.5e9, rel=0.05)
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

**Phase B Acceptance Criteria:**
- [ ] Regression baselines green (1.5% tolerance allows for new couplings)
- [ ] B1–B10 tests all green
- [ ] Commit tagged: `phase-2-remediation-B-complete`

---

## Phase C — Biophysical Unification

### Task C1: Write `tech_metals_availability` in resources.py

**Files:**
- Modify: `pyworldx/sectors/resources.py` (add stock `cum_tech_metal_extraction`; compute availability)

**Model:** Availability = `max(1 - cum_extraction/_TECH_METAL_RESERVES_Gt, 0.05)`. Reserves constant from USGS Mineral Commodity Summaries 2024 for silver + gallium + indium + rare earths: aggregate ~2.4 million tonnes of critical minerals. For stock-flow convenience: `_TECH_METAL_RESERVES = 2.4e6` tonnes. Extraction rate driven by `technology_capital` flow proportional to deployment.

- [ ] **Step 1-5:** Standard TDD cycle; test availability declines from 1.0 at t=1900 to <0.5 at high extraction.

### Task C2: Wire `temperature_anomaly` into agriculture.py heat-shock

**Files:**
- Modify: `pyworldx/sectors/agriculture.py` (declares_reads + yield multiplier)

**Empirical basis:** Zhao et al. (2017) "Temperature increase reduces global yields of major crops in four independent estimates" PNAS 114:9326 — meta-analysis shows wheat -6%/°C, maize -7.4%/°C, rice -3.2%/°C, soybean -3.1%/°C (global mean). Use **6%/°C yield loss above 2.0°C anomaly threshold** (weighted average, threshold matches IPCC AR6 WGII Ch 5 "detection" level).

```python
def heat_shock(delta_T: float) -> float:
    """Yield multiplier; 1.0 at ΔT ≤ 2.0°C, -6% per °C above."""
    if delta_T <= 2.0:
        return 1.0
    return max(1.0 - 0.06 * (delta_T - 2.0), 0.2)  # floor 20%
```

- [ ] **Step 1: Write failing test**

```python
def test_agriculture_yield_drops_above_2C_threshold() -> None:
    from pyworldx.sectors.agriculture import AgricultureSector
    from tests._phase2_helpers import base_shared, make_ctx
    ag = AgricultureSector()
    cool = base_shared(temperature_anomaly=1.5)
    hot  = base_shared(temperature_anomaly=5.0)
    out_c = ag.compute(2020.0, ag.init_stocks(make_ctx()), cool, make_ctx())
    out_h = ag.compute(2020.0, ag.init_stocks(make_ctx()), hot,  make_ctx())
    # at 5°C: 3°C above threshold → 18% yield loss → ratio ≈ 0.82
    ratio = out_h["food_per_capita"].magnitude / out_c["food_per_capita"].magnitude
    assert 0.80 <= ratio <= 0.85
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task C3: Climate reads `C_atm` from 5-stock carbon model

**Files:**
- Modify: `pyworldx/sectors/climate.py:106` (replace hardcoded `co2 = _CO2_PREINDUSTRIAL + pollution_gen * 1e-6`)

**Conversion:** CO2 ppm ≈ C_atm_GtC / 2.13. Constant `_GTC_PER_PPM = 2.13` (IPCC AR6 WG1 Annex III: 1 ppm CO2 = 2.124 GtC; use 2.13). Formula direction: `co2_ppm = C_atm / _GTC_PER_PPM`.

**Dependency warning (per review):** After Phase B (B6, B7, B8) modifies `industrial_output`, `pollution_gen` will shift → `C_atm` will shift. This C3 test's `co2_ppm ≈ 399` bound uses the injected `C_atm=850` directly, so IT is robust. But the FULL trajectory `test_phase2_loop_convergence` (A5) may need re-tuning after Phase B.

- [ ] **Step 1: Write failing test**

```python
def test_climate_reads_C_atm_directly() -> None:
    from pyworldx.sectors.climate import ClimateSector
    from pyworldx.core.quantities import Quantity
    from tests._phase2_helpers import make_ctx
    climate = ClimateSector()
    shared = {
        "C_atm": Quantity(850.0, "GtC"),
        "pollution_gen": Quantity(0.0, "pollution_units"),  # proxy disabled
    }
    out = climate.compute(2020.0, climate.init_stocks(make_ctx()), shared, make_ctx())
    co2 = out["co2_ppm"].magnitude
    # 850 / 2.13 ≈ 399 ppm
    assert 395 <= co2 <= 405
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task C4: Unify SOC — pollution_ghg authoritative; phosphorus reads

**Files:**
- Modify: `pyworldx/sectors/pollution_ghg.py` — ensure `C_soc` is in `declares_writes`
- Modify: `pyworldx/sectors/phosphorus.py` — remove `_SOC0` stock; add `C_soc` to `declares_reads`; use it wherever the old `SOC` was used
- Create: `tests/unit/test_pollution_ghg.py`

**Decision justification:** `pollution_ghg.py` models the full 5-compartment carbon cycle (atmosphere, land, soil, ocean surface, ocean deep) with cross-compartment fluxes. Moving SOC there keeps the carbon physics in one place. Phosphorus's `SOC` was a duplicate with simpler dynamics — phosphorus reads the richer model.

- [ ] **Step 1: Write failing mass-conservation test**

```python
def test_5_stock_carbon_mass_conservation() -> None:
    """Zero emissions for 200 years → total C conserved to 1e-6."""
    from pyworldx.sectors.pollution_ghg import PollutionGHGSector
    from pyworldx.core.quantities import Quantity
    from tests._phase2_helpers import make_ctx
    import copy

    ghg = PollutionGHGSector()
    stocks = ghg.init_stocks(make_ctx())
    compartments = [k for k in ("C_atm","C_land","C_soc","C_ocean_surf","C_ocean_deep") if k in stocks]
    assert len(compartments) == 5, f"expected 5 compartments, got {compartments}"
    initial_total = sum(stocks[k].magnitude for k in compartments)

    shared = {"pollution_gen": Quantity(0.0, "pollution_units")}
    stocks_running = copy.deepcopy(stocks)
    for t in range(1900, 2100):
        d = ghg.compute(float(t), stocks_running, shared, make_ctx())
        for k in compartments:
            stocks_running[k] = Quantity(
                stocks_running[k].magnitude + d[f"d_{k}"].magnitude,
                stocks_running[k].units,
            )
    final_total = sum(stocks_running[k].magnitude for k in compartments)
    drift = abs(final_total - initial_total) / initial_total
    assert drift < 1e-6, f"carbon mass drifted {drift:.2e}"


def test_phosphorus_reads_unified_C_soc() -> None:
    from pyworldx.sectors.phosphorus import PhosphorusSector
    phos = PhosphorusSector()
    assert "C_soc" in phos.declares_reads(), "phosphorus must read C_soc from pollution_ghg"
    # Phosphorus's own SOC stock should be removed
    from tests._phase2_helpers import make_ctx
    stocks = phos.init_stocks(make_ctx())
    assert "SOC" not in stocks, "phosphorus must not track its own SOC stock"
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

**Phase C Acceptance Criteria:**
- [ ] Regression baselines still green
- [ ] C1–C4 tests green
- [ ] `test_pollution_ghg.py` mass-conservation PASS to 1e-6
- [ ] Commit tagged: `phase-2-remediation-C-complete`

---

## Phase D — Demographic & Regional

### Task D1: Emit `disease_death_rate` from SEIRModule

**Files:**
- Modify: `pyworldx/sectors/seir.py` (add to declares_writes + return dict)

- [ ] **Step 1: Write failing test**

```python
def test_seir_exports_disease_death_rate() -> None:
    from pyworldx.sectors.seir import SEIRModule
    from pyworldx.core.quantities import Quantity
    from tests._phase2_helpers import make_ctx
    seir = SEIRModule(initial_infected_fraction=0.05)
    shared = {"POP": Quantity(7.8e9, "people"), "temperature_anomaly": Quantity(1.0, "deg_C_anomaly")}
    out = seir.compute(2020.0, seir.init_stocks(make_ctx()), shared, make_ctx())
    assert "disease_death_rate" in out
    ddr = out["disease_death_rate"].magnitude
    assert 0.0 < ddr < 0.02, f"ddr={ddr} out of sanity bounds"
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task D2: Read `disease_death_rate` in population.py (NO double-counting)

**Files:**
- Modify: `pyworldx/sectors/population.py`

**Double-counting guard:** SEIRModule currently mutates its own internal S/E/I/R cohorts. Add a flag `external_pop_feedback: bool = True` to SEIRModule: when True (default), SEIR DOES NOT add deaths to its internal R, only exports the rate for population to consume. Add a test for this.

- [ ] **Step 1: Write failing test** (for double-count avoidance AND pop reading rate)
- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task D3: Read Gini stratified mortality + allocation arrays in population.py AND capital.py

**Files:**
- Modify: `pyworldx/sectors/population.py` (declares_reads DRFM_bot90, DRHM_bot90, DRPM_bot90, DRCM_bot90)
- Modify: `pyworldx/sectors/capital.py` (declares_reads Gini resource allocation arrays; reduce effective labor output by inequality tax)

Addresses report §4A fully (prior plan missed the capital.py half).

- [ ] **Step 1: Write failing tests for BOTH sectors**

```python
def test_population_applies_gini_stratified_mortality() -> None:
    ...  # as prior draft

def test_capital_applies_gini_resource_allocation() -> None:
    """Under high inequality (bottom 90% gets 30% of resources vs 70% egalitarian),
    effective labor output drops because the bottom 90% is malnourished."""
    from pyworldx.sectors.capital import CapitalSector
    from tests._phase2_helpers import base_shared, make_ctx
    cap = CapitalSector()
    eq = base_shared(resource_share_bot90=0.70)  # egalitarian
    uneq = base_shared(resource_share_bot90=0.30)  # oligarchic
    io_eq = cap.compute(2020.0, cap.init_stocks(make_ctx()), eq, make_ctx())["industrial_output"].magnitude
    io_un = cap.compute(2020.0, cap.init_stocks(make_ctx()), uneq, make_ctx())["industrial_output"].magnitude
    assert io_un < io_eq
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task D4: Regional_trade emits `total_migration_flow` scalar

**Files:**
- Modify: `pyworldx/sectors/regional_trade.py`

Full N-region wrapper OUT OF SCOPE (Phase 3). Scalar stress signal only.

- [ ] **Step 1-5:** Standard TDD.

### Task D5: Population reads `total_migration_flow` as stressor

**Files:**
- Modify: `pyworldx/sectors/population.py` (small additive mortality term proportional to flow)

- [ ] **Step 1-5:** Standard TDD.

**Phase D Acceptance Criteria:**
- [ ] Regression baselines still green
- [ ] D1–D5 tests green
- [ ] No double-counting: SEIR internal cohort total + disease_death_rate × POP ≤ actual deaths
- [ ] Commit tagged: `phase-2-remediation-D-complete`

---

## Phase E — Data & Testing

### Task E1: Add `make_phase2_sectors()` helper and integration test

**Files:**
- Modify: `tests/_phase2_helpers.py` (add `make_phase2_sectors()`)
- Modify: `tests/integration/test_world3.py:298-305` (verify Phase 1 helper unchanged)
- Unskip: `tests/integration/test_phase2_loop_convergence.py` (from Task A5)

- [ ] **Step 1-5:** Standard TDD. Helper returns list of 15 sector instances; `test_all_phase2_sectors_integrate` runs 200-year sim under `strict_bootstrap=True` and asserts no NaN/inf in any trajectory.

### Task E2: Write the 9 missing unit tests in `test_phase2_sectors.py`

**Files:**
- Modify: `tests/unit/test_phase2_sectors.py`

Specific test assertions:

```python
def test_recycling_increases_with_prr() -> None:
    # Phosphorus recycling rate (PRR) going 0.1→0.9 must increase `p_recycled`
    from pyworldx.sectors.phosphorus import PhosphorusSector
    from tests._phase2_helpers import base_shared, make_ctx
    for prr in (0.1, 0.5, 0.9):
        phos = PhosphorusSector(phosphorus_recycling_rate=prr)
        out = phos.compute(2020.0, phos.init_stocks(make_ctx()), base_shared(), make_ctx())
        if prr == 0.1:
            lo = out["p_recycled"].magnitude
        if prr == 0.9:
            hi = out["p_recycled"].magnitude
    assert hi > 5 * lo


def test_prr_increases_with_profitability() -> None:
    # Endogenous PRR logic: when mining cost ↑, recycling becomes profitable → PRR ↑
    ...


def test_85_percent_floor_behavior() -> None:
    # PRR caps at 0.85 even under extreme profitability
    ...


def test_analytical_weathering() -> None:
    # Weathering flux matches closed-form solution under constant atm P
    ...


def test_finance_sector_reads_tnds_aes() -> None:
    from pyworldx.sectors.finance import FinanceSector
    assert "tnds_aes" in FinanceSector().declares_reads()


def test_100_percent_replacement_impossible() -> None:
    # AES cannot fully replace ESP; hard ceiling at 80%
    ...


def test_aerosol_decay() -> None:
    # aerosol_stock declines with half-life τ when source=0
    ...


def test_aerosol_production() -> None:
    # aerosol_production ∝ fossil_combustion
    ...


def test_analytical_aerosol_decay() -> None:
    # Closed-form exponential decay matches numeric within 1%
    ...
```

- [ ] **Step 1: Write ALL 9 tests** (failing)
- [ ] **Step 2-5:** For each, fix the sector code to make the assertion pass (physics audit may reveal bugs); commit per batch of 3.

### Task E3: Create `tests/integration/test_phase2_cross_coupling.py` with 5 tests

**Files:**
- Create: `tests/integration/test_phase2_cross_coupling.py`

Five tests as described; each runs a short Phase-2 engine and verifies a specific causal chain.

- [ ] **Step 1-5:** Standard TDD, but the "implement" step is verifying the coupling already exists from Phases A-D.

### Task E4: Create the 9 missing dedicated unit-test files

**Files:**
- Create: `tests/unit/test_finance.py`
- Create: `tests/unit/test_gini_distribution.py`
- Create: `tests/unit/test_energy_technology.py`
- Create: `tests/unit/test_energy_sustainable.py`
- Create: `tests/unit/test_energy_fossil.py`
- Create: `tests/unit/test_climate.py`
- Create: `tests/unit/test_seir.py` (verify existing or create if absent — file `/Users/johnny/pyWorldX/tests/unit/test_seir.py` already exists per Blocker investigation; audit coverage)
- Create: `tests/unit/test_human_capital.py`
- Create: `tests/unit/test_welfare.py`

Each file must hit 100% line+branch coverage of its sector.

**Minimum test per file:** init_stocks, compute at 1900, compute at 2100, declares_reads/writes match actual outputs, one physics assertion.

- [ ] **Step 1-5:** One commit per file, each reaching 100% coverage of the target sector.

### Task E5: Upgrade `test_phase1_integration.py` to physics-based assertions

**Files:**
- Modify: `tests/integration/test_phase1_integration.py`

Replace every `assert "X" in result.trajectories` with a physics bound:

```python
# Before: assert "ghg_stock" in result.trajectories
# After:
ghg = result.trajectories["ghg_stock"]
assert ghg[-1] > ghg[0] * 5, "GHG must >5x from 1900→2100"

# Before: assert fossil_output > 0
# After:
fo = result.trajectories["fossil_output"]
assert fo[0] > 0 and fo[-1] > 0  # positive throughout
assert fo.max() > fo[0] * 10  # at least 10x peak

# Add: debt accumulates
debt = result.trajectories["total_debt"]
assert debt[-1] > debt[0]

# Add: EROI declines (energy_technology)
eroi = result.trajectories.get("eroi_technology")
if eroi is not None:
    assert eroi[-1] < eroi[0]  # declines over time
```

- [ ] **Step 1-5:** Standard TDD.

### Task E6: Expand `ENTITY_TO_ENGINE_MAP` + wire data connectors

**Files:**
- Modify: `pyworldx/data/bridge.py:31-57` (add Phase 2 mappings)
- Modify: `pyworldx/data/connectors/gcb.py` (ensure it returns `C_atm` history)
- Modify: `pyworldx/data/connectors/ssurgo.py` (ensure it returns `C_soc` initial)
- Create: `tests/unit/test_bridge_phase2.py`

New mappings:

```python
ENTITY_TO_ENGINE_MAP.update({
    "carbon.atmospheric_gtc": "C_atm",
    "carbon.land_gtc": "C_land",
    "carbon.soil_gtc": "C_soc",
    "carbon.ocean_surface_gtc": "C_ocean_surf",
    "carbon.ocean_deep_gtc": "C_ocean_deep",
    "finance.resilience": "financial_resilience",
    "minerals.tech_metals_availability": "tech_metals_availability",
    "climate.temperature_anomaly": "temperature_anomaly",
    "epidemiology.labor_force_multiplier": "labor_force_multiplier",
    "energy.supply_factor": "energy_supply_factor",
})
```

- [ ] **Step 1: Write failing test**

```python
def test_bridge_resolves_all_phase2_entities() -> None:
    from pyworldx.data.bridge import ENTITY_TO_ENGINE_MAP, DataBridge
    phase2_entities = {
        "carbon.atmospheric_gtc", "carbon.land_gtc", "carbon.soil_gtc",
        "carbon.ocean_surface_gtc", "carbon.ocean_deep_gtc",
        "finance.resilience", "minerals.tech_metals_availability",
        "climate.temperature_anomaly", "epidemiology.labor_force_multiplier",
        "energy.supply_factor",
    }
    mapped = set(ENTITY_TO_ENGINE_MAP.keys())
    missing = phase2_entities - mapped
    assert not missing, f"bridge missing {missing}"


@pytest.mark.network
def test_gcb_connector_returns_c_atm() -> None:
    from pyworldx.data.connectors.gcb import GCBConnector
    data = GCBConnector().fetch()
    assert "carbon.atmospheric_gtc" in data.variables
```

- [ ] **Step 2-5: FAIL → implement → PASS + commit**

### Task E7: Populate `v2_scenarios.py` with real policy_events

**Files:**
- Modify: `pyworldx/scenarios/v2_scenarios.py`
- Create: `tests/integration/test_v2_scenarios.py`

For each of the 7 scenarios: define the `policy_events` that are now viable after Phase A2. Example:

```python
def energiewende(
    fossil_phaseout_start: float = 2020.0,
    fossil_phaseout_end: float = 2060.0,
) -> Scenario:
    # 90% fossil phase-out from 2020→2060; PolicyShape.RAMP
    from pyworldx.scenarios.scenario import PolicyEvent, PolicyShape
    # rate = -0.9 / (2060-2020) per unit of fossil_output baseline
    return Scenario(
        ...,
        policy_events=[
            PolicyEvent(
                target="fossil_output",
                shape=PolicyShape.RAMP,
                t_start=fossil_phaseout_start,
                t_end=fossil_phaseout_end,
                rate=-0.9 / 40.0,  # relative rate; applier multiplies by baseline
                description="90% fossil phase-out 2020-2060",
            ),
        ],
        ...
    )
```

- [ ] **Step 1-5:** One commit per scenario, each with a test verifying trajectory divergence from baseline.

### Task E8: Verify full suite coverage ≥ 100%

**Files:**
- Run: coverage report

- [ ] **Step 1: Run**

```bash
.venv/bin/python -m pytest --cov=pyworldx --cov-branch --cov-fail-under=100 tests/ data_pipeline/tests/
```

- [ ] **Step 2: If coverage < 100%, for each uncovered line write a test in the appropriate E4 file and commit**

- [ ] **Step 3: Commit when green**

```bash
git commit -m "test: achieve 100% Phase 2 coverage (per .coverage-thresholds.json)"
```

**Phase E Acceptance Criteria:**
- [ ] All E1–E8 tests green
- [ ] `pytest --cov-fail-under=100` PASSES
- [ ] mypy strict PASSES
- [ ] ruff check PASSES
- [ ] A5 (algebraic-loop convergence) unskipped and GREEN
- [ ] Commit tagged: `phase-2-remediation-E-complete`

---

## Phase F — Finalization (MANDATORY per CLAUDE.md)

### Task F1: Run `/self-reflect` and commit KB updates

Per CLAUDE.md: *"Before finishing a branch → MUST run `/self-reflect` and commit knowledge base updates before PR creation."*

- [ ] **Step 1: Invoke the skill**

```
/self-reflect
```

- [ ] **Step 2: Review the generated KB updates; commit them**

```bash
git add .beads/ .metaswarm/ docs/knowledge/  # whichever the skill writes to
git commit -m "docs: self-reflect learnings from Phase 2 remediation"
```

### Task F2: Run `/pr-shepherd` or create PR

- [ ] **Step 1:** Verify 1900 baseline + Nebel 2023 snapshot still within 1.5% tolerance.
- [ ] **Step 2:** Run full validation: `pytest tests/ data_pipeline/tests/ --cov-fail-under=100 && mypy pyworldx && ruff check pyworldx`
- [ ] **Step 3:** Create PR; tag as `phase-2-remediation-complete`.

**Phase F Acceptance Criteria:** Branch clean; PR open with all checks green.

---

## Execution Order Summary (corrected)

```
Phase 0 (fixtures + baseline pins)
  │
  └─> Phase A (A1 → A2 → A3 → A4 → A5 skipped)
        │
        ├─> Phase B (B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8 → B9 → B10)
        │     │
        │     └─> Phase D (D1 → D2 → D3 → D4 → D5)  — depends on B5 (SEIR LFM)
        │
        └─> Phase C (C1 → C2 → C3 → C4)  — mostly parallel with B, but see C3 note
              │
              └─> Phase E (E1 → E2 → E3 → E4 → E5 → E6 → E7 → E8)
                    │
                    └─> Phase F (F1 → F2)
```

B and C can proceed in parallel. **Caveat on C3:** after B6–B8 ship, the `industrial_output` trajectory shifts, which changes `C_atm` in the FULL simulation. C3's own test (which directly injects `C_atm=850`) is insulated, but the Phase E1 integration test may need re-running to confirm no downstream drift.

## Coverage: Draft → Plan Crosswalk

| Source doc item | Plan task(s) | Status |
|---|---|---|
| Report §1 Task 7 cross-module (5 tests) | E3 | Addressed |
| Report §1 GHG carbon conservation | C4 | Addressed |
| Report §1 9 skipped unit tests | E2 | Addressed (with assertion bodies) |
| Report §2A True regional wrapper | Phase 3 deferral | Deferred |
| Report §2B EIA energy baseline calibration | Acknowledged in Verified State §1 (_EJ_SCALE already calibrated at registrar.py:45); no new task | Addressed (pre-existing) |
| Report §2C Data pipeline disconnect | E6 (map + connector wiring) | Addressed |
| Report §3A test_phase1_integration assertions | E5 | Addressed (explicit bounds for GHG, fossil, debt, EROI) |
| Report §3B Cobb-Douglas TFP | Verified State §1 | Rejected (already correct) |
| Report §3C Regional migration | D4, D5 (scalar only) | Partially — full link deferred to Phase 3 |
| Report §3D Exception swallowing | A1 | Addressed |
| Report §4A Gini/Bifurcated collapse | D3 (population.py AND capital.py) | Addressed |
| Report §4B Minsky Moment | B9 | Addressed |
| Report §4C Phantom Climate Physics | C3 | Addressed |
| Report §4D Twin SOC Paradox | C4 | Addressed |
| Report §4E Pandemic No Casualties | D1, D2 | Addressed |
| Report §4F Phase 2 Sectors excluded | E1 | Addressed |
| Report §4G Tech Metals Illusion | C1 | Addressed |
| Report §4H Energy Ceiling side quests | B7, B8 + A4 + (agriculture already) | Addressed |
| Report §4I Capital Stealing | B10 | Addressed |
| Report §4J Zero tests for complex physics | E4 (9 files: finance, gini, energy_tech, energy_sust, energy_fossil, climate, seir, human_capital, welfare) | Addressed |
| Report §4K Communist Lottery (equal allocation) | A3 | Addressed |
| Report §4L Military Investment Bug | B1 | Addressed |
| Report §4M Education Free Lunch | B2, B4 | Addressed |
| Report §4N Scenario Layer Illusion | A2, E7 | Addressed |
| Report §4O DataBridge blind to Phase 2 | E6 | Addressed |
| Draft — TNDS audit | B4 | Addressed |

**Uncovered: ZERO.** (Previously uncovered items from review gate v1 now addressed.)

## Addendum: Structural Holes Corrections (from phase_2_plan_holes.md)

Verified against real code 2026-04-17. All 5 blockers confirmed; 4 new tasks added.

### Correction 1 (BLOCKER): Time Scale — fix `make_ctx()` to relative (0–200)

The entire pyWorldX system uses **relative time** `t ∈ [0, 200]` (not absolute 1900–2100):
- `runner.py:93`: `t_start = scenario.start_year - 1900` → 0
- `population.py:213`: `iphst_sim = _IPHST - 1900` (= 40 in relative units)
- `population.py:280`: `calendar_year = t + 1900`
- All existing tests: `t_start=0.0, t_end=200.0`

**Fix Task 0.1:** `make_ctx()` → `RunContext(master_dt=master_dt, t_start=0.0, t_end=200.0)`.
All test `t` values must be **relative**: `t=0.0` for 1900, `t=120.0` for 2020, `t=200.0` for 2100.
Task 0.2 Engine call: use `t_start=0.0, t_end=200.0`.

### Correction 2 (BLOCKER): Task C1 — read `tech_metals_demand` not recalculate

`energy_technology.py:115` already exports `tech_metals_demand` to shared state.
**Fix Task C1:** `resources.py` must declare `tech_metals_demand` as a read and use it to drive the extraction rate, instead of recalculating from `technology_capital` flow.

### Correction 3 (BLOCKER): Task C3 — read `ghg_radiative_forcing` directly

`pollution_ghg.py:202` already exports `ghg_radiative_forcing`. `climate.py:109` independently re-derives the same 5.35·ln() formula.
**Fix Task C3:** `climate.py` must declare `ghg_radiative_forcing` as a read and use it directly in the Temperature ODE. Remove the `co2_ppm` → `rf_ghg` re-derivation from `climate.py`.

### Correction 4 (BLOCKER): Task B10 — handle `trapped_capital` (new Task B12)

`energy_technology.py:118` exports `trapped_capital` (investment that couldn't be deployed due to metal scarcity). B10 subtracts full `tech_sector_investment` from IC but the trapped portion was never converted to real capital. Capital is destroyed.
**Fix:** Add **Task B12** — `capital.py` reads `trapped_capital` and ADDS it back to the IC pool (refunding the undeployed investment). Alternatively: `finance.py` registers it as a direct write-off against L.

### Correction 5 (BLOCKER): Task B10 — fossil sector also drains capital

`energy_fossil.py:79` internally computes `investment = io * 0.05 * profitability` but does NOT export it.
**Fix Task B10:** Also expose `fossil_sector_investment` from `energy_fossil.py` (add to `declares_writes()` and return dict). `capital.py` reads all three: `tech_sector_investment`, `sustainable_sector_investment`, `fossil_sector_investment`.

### New Task B11: Wire adaptive_technology.py outputs (Hole 9)

`adaptive_technology.py` exports `tech_cost_fraction`, `resource_tech_mult`, `pollution_tech_mult`, `agriculture_tech_mult` — none are read by any other sector.
- `capital.py`: read `tech_cost_fraction`, subtract from IC investment pool
- `resources.py`: read `resource_tech_mult`, apply to NRUF
- `pollution.py`: read `pollution_tech_mult`, scale pollution generation

### New Task B13: Wire toxin multipliers to population.py (Hole 10)

`pollution_toxins.py:104-107` exports `toxin_health_multiplier` and `toxin_fertility_multiplier`.
`population.py` ignores them entirely — nobody dies from accumulated toxins.
- `population.py`: declare reads; multiply `death_rate` by `toxin_health_multiplier`, `birth_rate` by `toxin_fertility_multiplier`.

### New Task D6: Export trade_food_loss → agriculture.py (Hole 7)

`regional_trade.py:183` calculates transport loss but never exports it. The food that "rots in transit" is silently refunded.
- `regional_trade.py`: calculate `total_food_loss`, add to `declares_writes()` and return dict
- `agriculture.py`: read `trade_food_loss`, subtract from food output

### New Task C5: Fix ecosystem_services.py temperature constants (Hole 13)

`ecosystem_services.py:98-99` has `T_opt = 15.0, T_crit = 35.0` — clearly absolute temperatures applied to an **anomaly** variable (pre-industrial = 0.0). An anomaly of +15°C is civilizational collapse, not optimal.
- Change to anomaly-scale: `T_opt = 0.0` (optimal = pre-industrial), `T_crit = 4.0` (collapse at +4°C).

### Deferred (architectural, Phase 3)

- **Hole 3 (RAMP math)**: E7 briefing corrected to use absolute-magnitude rates; `PolicyEvent.apply()` redesign deferred
- **Hole 4 (SEIR aging)**: Major restructuring (absolute → fraction stocks); Phase 3
- **Hole 5 (Minsky debt model)**: Growth-financing debt redesign; Phase 3
- **Hole 6 (Ability-to-Pay macro/micro)**: CentralRegistrar architectural redesign; Phase 3
- **Hole 8 (Ceiling math semantics)**: Registrar investment-vs-distribution redesign; Phase 3

## Deferred to Phase 3 (explicit)

- True N-region engine wrapper
- Full migration absorption into HumanCapital (D4/D5 provides scalar only)
- Dynamic phosphorus recycling control beyond static PRR floor
- Full C_scale connectivity severance for lifeboating
- Replacing Phase 1 `pollution.py` proxy with `pollution_ghg.py` as primary
- SEIR cohort aging (fraction-based stocks)
- Growth-financing debt model (Minsky scenario prerequisite)
- CentralRegistrar macro Ability-to-Pay redesign
- Energy ceiling capital-investment semantics (Registrar redesign)

## Self-Review (post-revision)

- [x] Every task uses real class names (`SEIRModule`, `BaseSector`, `init_stocks`)
- [x] Every test imports from real helper module `tests._phase2_helpers`
- [x] `_EJ_SCALE` usage annotated; plan calls out exposure
- [x] `PolicyEvent.apply()` and `Scenario.apply_policies()` used (no fabricated methods)
- [x] Coverage threshold is 100% per `.coverage-thresholds.json`
- [x] `/self-reflect` in Phase F
- [x] `_GTC_PER_PPM = 2.13` constant name and formula direction clarified
- [x] Calibration numbers cited (OECD retention rate, UNESCO education spend, Zhao 2017, IPCC AR6)
- [x] All 23 verified defects covered; 5 missing test files added; capital conservation added
- [x] B10, D3 (capital half), B4 (TNDS audit), E4 (9 files) resolve all completeness blockers
