# Phase 2 Final Patches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 4 targeted code patches that close the remaining Phase 2 physics and macroeconomic holes: charge the economy for tech R&D, enable debt accumulation in the Minsky scenario, make CentralRegistrar energy allocation demand-proportional, and couple SEIR cohort aging to population maturation flows.

**Architecture:** Each patch is a self-contained change with its own test file. Tasks are ordered by risk (lowest first): capital I/O accounting → finance leverage → registrar weighting → SEIR maturation. All changes must leave `test_phase1_integration.py` physics bounds passing — run it after every task as a regression guard.

**Tech Stack:** Python 3.11+, pytest, mypy strict, ruff. Branch: `phase-2-remediation`. Run tests via `python3 -m pytest` (not `poetry run`).

---

## File Map

| File | Change |
|---|---|
| `pyworldx/sectors/capital.py` | Read `tech_cost_fraction`; subtract `tech_rd_cost` from `io_for_capital` |
| `pyworldx/sectors/finance.py` | Add `leverage_fraction=0.0`; add growth-driven debt term to `loan_taking_rate` |
| `pyworldx/scenarios/v2_scenarios.py` | Add `"finance.leverage_fraction": 0.2` to `minsky_moment()` overrides |
| `pyworldx/core/central_registrar.py` | Delete `all_default` bypass; use demand-scaled weights |
| `pyworldx/sectors/population.py` | Export `mat1`, `mat2`, `mat3` in return dict and `declares_writes()` |
| `pyworldx/sectors/seir.py` | Read `mat1/2/3`; add proportional aging in/out to SEIR ODEs |
| `tests/unit/test_capital_tech_cost.py` | New — tech_rd_cost tests |
| `tests/unit/test_finance_leverage.py` | New — leverage_fraction tests |
| `tests/unit/test_central_registrar_a3.py` | Extend — demand-weighted allocation tests |
| `tests/unit/test_seir_maturation.py` | New — SEIR cohort aging tests |

---

## Task 1: capital.py — Charge Economy for Tech R&D

`adaptive_technology.py` already emits `tech_cost_fraction` (fraction of IO spent on R&D). Capital currently ignores it, making tech R&D free. This task deducts it from `io_for_capital`.

**Files:**
- Create: `tests/unit/test_capital_tech_cost.py`
- Modify: `pyworldx/sectors/capital.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_capital_tech_cost.py
from __future__ import annotations
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.capital import CapitalSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _base_inputs() -> dict[str, Quantity]:
    return {
        "fcaor": Quantity(0.05, "dimensionless"),
        "POP": Quantity(1.65e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "AL": Quantity(1.4e9, "hectares"),
        "aiph": Quantity(5.0, "capital_units"),
        "food_per_capita": Quantity(400.0, "food_units_per_person"),
        "frac_io_to_agriculture": Quantity(0.15, "dimensionless"),
        "industrial_output_per_capita": Quantity(40.0, "industrial_output_units"),
        "service_output_per_capita": Quantity(87.0, "service_units_per_capita"),
        "maintenance_ratio": Quantity(1.0, "dimensionless"),
        "human_capital_multiplier": Quantity(1.0, "dimensionless"),
        "labor_force_multiplier": Quantity(1.0, "dimensionless"),
        "energy_supply_factor": Quantity(1.0, "dimensionless"),
        "financial_resilience": Quantity(1.0, "dimensionless"),
        "resource_share_bot90": Quantity(0.5, "dimensionless"),
    }


def test_tech_cost_fraction_declared_as_read() -> None:
    """Capital sector must declare tech_cost_fraction as a read."""
    assert "tech_cost_fraction" in CapitalSector().declares_reads()


def test_zero_tech_cost_fraction_unchanged() -> None:
    """tech_cost_fraction=0 must produce same IO as when key is absent."""
    s = CapitalSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    inputs_no_key = _base_inputs()
    inputs_zero = {**_base_inputs(), "tech_cost_fraction": Quantity(0.0, "dimensionless")}
    out_no = s.compute(0.0, stocks, inputs_no_key, ctx)
    out_zero = s.compute(0.0, stocks, inputs_zero, ctx)
    assert abs(out_no["industrial_output"].magnitude - out_zero["industrial_output"].magnitude) < 1.0


def test_nonzero_tech_cost_reduces_io_for_capital() -> None:
    """A 10% tech_cost_fraction must reduce IC investment vs the zero case."""
    s = CapitalSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    out_zero = s.compute(0.0, stocks, {**_base_inputs(), "tech_cost_fraction": Quantity(0.0, "dimensionless")}, ctx)
    out_ten = s.compute(0.0, stocks, {**_base_inputs(), "tech_cost_fraction": Quantity(0.10, "dimensionless")}, ctx)
    # Higher tech R&D cost → less IO available for capital investment → IC grows slower
    assert out_ten["d_IC"].magnitude < out_zero["d_IC"].magnitude


def test_tech_cost_fraction_monotone() -> None:
    """d_IC must decrease monotonically as tech_cost_fraction increases."""
    s = CapitalSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    fracs = [0.0, 0.05, 0.10, 0.20]
    dic_values = []
    for f in fracs:
        out = s.compute(0.0, stocks, {**_base_inputs(), "tech_cost_fraction": Quantity(f, "dimensionless")}, ctx)
        dic_values.append(out["d_IC"].magnitude)
    assert dic_values == sorted(dic_values, reverse=True), "d_IC must decrease as tech_cost_fraction increases"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_capital_tech_cost.py -v
```

Expected: `FAILED test_tech_cost_fraction_declared_as_read` — `"tech_cost_fraction"` not in `declares_reads()`.

- [ ] **Step 3: Implement — capital.py**

In `pyworldx/sectors/capital.py`, make three edits:

**Edit A** — Read `tech_cost_fraction` after the existing `trapped_capital_refund` read (around line 318):

```python
        trapped_capital_refund = inputs.get(
            "trapped_capital", Quantity(0.0, "capital_units")
        ).magnitude

        # Tech R&D cost: IO allocated to adaptive technology R&D is not
        # available for productive capital investment.
        tech_cost_fraction = inputs.get(
            "tech_cost_fraction", Quantity(0.0, "dimensionless")
        ).magnitude
        tech_rd_cost = io * tech_cost_fraction
```

**Edit B** — Subtract `tech_rd_cost` from `io_for_capital` (the existing line around line 307):

```python
        # Before:
        io_for_capital = max(io - energy_sector_draw, 0.0)

        # After:
        io_for_capital = max(io - energy_sector_draw - tech_rd_cost, 0.0)
```

**Edit C** — Add `"tech_cost_fraction"` to `declares_reads()`:

```python
    def declares_reads(self) -> list[str]:
        return [
            "fcaor",
            "POP",
            "P2",
            "P3",
            "AL",
            "aiph",
            "food_per_capita",
            "frac_io_to_agriculture",
            "industrial_output_per_capita",
            "service_output_per_capita",
            "maintenance_ratio",
            "human_capital_multiplier",
            "labor_force_multiplier",
            "energy_supply_factor",
            "financial_resilience",
            "fossil_sector_investment",
            "tech_sector_investment",
            "sust_sector_investment",
            "trapped_capital",
            "tech_cost_fraction",        # ← add this
            "resource_share_bot90",
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_capital_tech_cost.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Regression check**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/integration/test_phase1_integration.py -v
```

Expected: all pass. If any physics bound fails, the `tech_cost_fraction` default in the real run is 0 (adaptive_technology initialises slowly), so there should be no change.

- [ ] **Step 6: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/sectors/capital.py tests/unit/test_capital_tech_cost.py
git commit -m "feat(capital): deduct tech_rd_cost from io_for_capital (closes free-tech bug)"
```

---

## Task 2: Finance — Leverage Fraction + Minsky Scenario Wire

`FinanceSector` currently only borrows when liquid funds go negative. Adding `leverage_fraction` allows debt-financed growth investment, enabling the Minsky scenario. Defaults to 0.0 so the baseline is unchanged.

**Files:**
- Create: `tests/unit/test_finance_leverage.py`
- Modify: `pyworldx/sectors/finance.py`
- Modify: `pyworldx/scenarios/v2_scenarios.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_finance_leverage.py
from __future__ import annotations
import pytest
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.finance import FinanceSector


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _base_stocks(sector: FinanceSector, ctx: RunContext) -> dict[str, Quantity]:
    return sector.init_stocks(ctx)


def _base_inputs() -> dict[str, Quantity]:
    return {
        "industrial_output": Quantity(7.9e10, "industrial_output_units"),
        "IC": Quantity(1.3e12, "capital_units"),
        "SC": Quantity(1.4e11, "capital_units"),
        "AL": Quantity(1.4e9, "hectares"),
        "POP": Quantity(1.65e9, "persons"),
        "governance_index": Quantity(0.6, "dimensionless"),
    }


def test_leverage_fraction_default_zero() -> None:
    """FinanceSector must default leverage_fraction to 0.0."""
    s = FinanceSector()
    assert s.leverage_fraction == 0.0


def test_leverage_zero_preserves_baseline() -> None:
    """leverage_fraction=0 must produce same dD_g as a sector without the attribute."""
    s_default = FinanceSector()
    s_explicit = FinanceSector(leverage_fraction=0.0)
    ctx = _ctx()
    out_d = s_default.compute(0.0, s_default.init_stocks(ctx), _base_inputs(), ctx)
    out_e = s_explicit.compute(0.0, s_explicit.init_stocks(ctx), _base_inputs(), ctx)
    assert abs(out_d["d_D_g"].magnitude - out_e["d_D_g"].magnitude) < 1.0


def test_nonzero_leverage_increases_debt_growth() -> None:
    """leverage_fraction=0.2 must produce higher dD_g than leverage_fraction=0.0."""
    ctx = _ctx()
    s_no_lev = FinanceSector(leverage_fraction=0.0)
    s_lev = FinanceSector(leverage_fraction=0.2)
    out_no = s_no_lev.compute(0.0, s_no_lev.init_stocks(ctx), _base_inputs(), ctx)
    out_lev = s_lev.compute(0.0, s_lev.init_stocks(ctx), _base_inputs(), ctx)
    assert out_lev["d_D_g"].magnitude > out_no["d_D_g"].magnitude


def test_leverage_fraction_is_scenario_settable() -> None:
    """finance.leverage_fraction must be overridable via apply_parameter_overrides."""
    from pyworldx.scenarios.scenario import apply_parameter_overrides, Scenario
    scenario = Scenario(
        name="test", description="test", start_year=1900, end_year=2100,
        parameter_overrides={"finance.leverage_fraction": 0.3},
    )
    s = FinanceSector()
    apply_parameter_overrides(scenario, [s])
    assert s.leverage_fraction == pytest.approx(0.3)


def test_minsky_moment_scenario_has_leverage_override() -> None:
    """minsky_moment() must include finance.leverage_fraction in parameter_overrides."""
    from pyworldx.scenarios.v2_scenarios import minsky_moment
    s = minsky_moment()
    assert "finance.leverage_fraction" in s.parameter_overrides
    assert s.parameter_overrides["finance.leverage_fraction"] > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_finance_leverage.py -v
```

Expected: fails on `test_leverage_fraction_default_zero` — `FinanceSector` has no `leverage_fraction`.

- [ ] **Step 3: Implement — finance.py**

**Edit A** — Add `leverage_fraction` to `__init__` (after `investment_fraction`):

```python
    def __init__(
        self,
        initial_liquid_funds: float = _L0,
        interest_rate: float = _INTEREST_RATE,
        debt_repayment_time: float = _DEBT_REPAYMENT,
        military_fraction: float = _MILITARY_FRACTION,
        investment_fraction: float = _INVESTMENT_FRACTION,
        leverage_fraction: float = 0.0,
    ) -> None:
        self.initial_liquid_funds = initial_liquid_funds
        self.interest_rate = interest_rate
        self.debt_repayment_time = debt_repayment_time
        self.military_fraction = military_fraction
        self.investment_fraction = investment_fraction
        self.leverage_fraction = leverage_fraction
```

**Edit B** — Update `loan_taking_rate` in `compute()` (replace the existing line):

```python
        # Before:
        loan_taking_rate = loan_deficit * gov_mult

        # After — adds growth-driven debt: even with positive L, sectors
        # borrow leverage_fraction of new investments during boom cycles.
        loan_taking_rate = (loan_deficit + investments * self.leverage_fraction) * gov_mult
```

Note: `investments` is already computed one line earlier as `profit * self.investment_fraction`.

- [ ] **Step 4: Implement — v2_scenarios.py**

Add `"finance.leverage_fraction": 0.2` to `minsky_moment()`:

```python
def minsky_moment() -> Scenario:
    """Total Debt > ΣV_c → Investment Rate → 0, broad-front collapse."""
    return Scenario(
        name="minsky_moment",
        description=(
            "Orchestrated Minsky Moment: debt accumulation exceeds collateral "
            "value, triggering Investment Rate → 0 and broad-front collapse."
        ),
        start_year=1900,
        end_year=2200,
        parameter_overrides={
            "finance.interest_rate": 0.06,
            "finance.leverage_fraction": 0.2,
        },
        tags=["v2", "minsky", "stress_test"],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_finance_leverage.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Regression check**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/integration/test_phase1_integration.py tests/integration/test_v2_scenarios.py -v
```

Expected: all pass. `leverage_fraction=0.0` default leaves baseline untouched; `minsky_moment` test only checks trajectory is finite (not specific values).

- [ ] **Step 7: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/sectors/finance.py pyworldx/scenarios/v2_scenarios.py tests/unit/test_finance_leverage.py
git commit -m "feat(finance): add leverage_fraction for debt-financed growth; wire minsky_moment"
```

---

## Task 3: CentralRegistrar — Demand-Weighted Allocation

Delete the `all_default` bypass and replace the weight formula with `demand × (0.5·lf_norm + 0.5·sv_norm)`. When all LF=SV=1 this reduces to pure demand-proportional allocation (better physics than equal shares). When LF/SV differ, larger and richer sectors get more energy.

**Files:**
- Modify: `pyworldx/core/central_registrar.py`
- Modify: `tests/unit/test_central_registrar_a3.py` (extend with new tests)

- [ ] **Step 1: Write the new tests**

Add these tests to the bottom of `tests/unit/test_central_registrar_a3.py`:

```python
def test_demand_proportional_when_all_weights_equal() -> None:
    """When all LF=SV=1, allocation must be demand-proportional, not equal-share."""
    from pyworldx.core.central_registrar import CentralRegistrar, EnergyDemand
    cr = CentralRegistrar(enabled=True)
    demands = [
        EnergyDemand(sector_name="big", demand=90.0, liquid_funds=1.0, security_value=1.0),
        EnergyDemand(sector_name="small", demand=10.0, liquid_funds=1.0, security_value=1.0),
    ]
    mults = cr._allocate(total_supply=50.0, demands=demands)
    # big sector demanded 90, small demanded 10.
    # demand-proportional: big gets 45, small gets 5 → ratios 0.5 and 0.5.
    # Equal-share (old behaviour): each gets 25 → big: 25/90 < small: 25/10.
    # With demand-proportional the multipliers must be EQUAL (both at 50% of demand).
    assert abs(mults["big"] - mults["small"]) < 0.01, (
        f"Multipliers must be equal under demand-proportional: big={mults['big']:.3f} small={mults['small']:.3f}"
    )


def test_high_liquid_funds_gets_more_allocation() -> None:
    """A sector with 2× liquid_funds must receive a larger multiplier."""
    from pyworldx.core.central_registrar import CentralRegistrar, EnergyDemand
    cr = CentralRegistrar(enabled=True)
    demands = [
        EnergyDemand(sector_name="rich", demand=50.0, liquid_funds=2.0, security_value=1.0),
        EnergyDemand(sector_name="poor", demand=50.0, liquid_funds=1.0, security_value=1.0),
    ]
    mults = cr._allocate(total_supply=60.0, demands=demands)
    assert mults["rich"] > mults["poor"], "Higher liquid_funds must yield higher multiplier"


def test_allocate_handles_no_demands() -> None:
    """Empty demands list must return empty dict (no crash)."""
    from pyworldx.core.central_registrar import CentralRegistrar
    cr = CentralRegistrar(enabled=True)
    assert cr._allocate(total_supply=100.0, demands=[]) == {}
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_central_registrar_a3.py::test_demand_proportional_when_all_weights_equal tests/unit/test_central_registrar_a3.py::test_high_liquid_funds_gets_more_allocation -v
```

Expected: `test_demand_proportional_when_all_weights_equal` fails — old code gives equal shares not demand-proportional.

- [ ] **Step 3: Implement — central_registrar.py**

Replace lines 236–266 (the `all_default` block and old weight formula) with the unified demand-weighted formula. The block to replace starts at `all_default = all(` and ends before `multipliers = {}` in the weighted path:

```python
        # Demand-weighted ability-to-pay allocation.
        # When all LF=SV=1 (default), weight ∝ demand → demand-proportional.
        # When LF/SV differ, larger/richer sectors get proportionally more.
        total_lf = sum(d.liquid_funds for d in demands)
        total_sv = sum(d.security_value for d in demands)

        weights: dict[str, float] = {}
        for d in demands:
            lf_norm = d.liquid_funds / max(total_lf, 1e-15)
            sv_norm = d.security_value / max(total_sv, 1e-15)
            weights[d.sector_name] = d.demand * (0.5 * lf_norm + 0.5 * sv_norm)

        total_weight = sum(weights.values())

        multipliers: dict[str, float] = {}
        for d in demands:
            w = weights[d.sector_name] / max(total_weight, 1e-15)
            allocation = w * total_supply
            raw_ratio = allocation / max(d.demand, 1e-15)
            if raw_ratio >= 1.0:
                mult = 1.0
            elif raw_ratio < 0.5:
                mult = max(0.0, raw_ratio ** 2.0)
            else:
                mult = raw_ratio ** 1.5
            multipliers[d.sector_name] = max(mult, 0.0)

        return multipliers
```

The closing `return multipliers` from the old weighted path is already there — make sure the old `all_default` early-return block (lines 239–254) and the old `total_lf`/`total_sv`/`weights` block (lines 257–266) are both removed.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_central_registrar_a3.py -v
```

Expected: all pass (old tests still pass because the multiplier math for the weighted path is unchanged; new tests pass with demand-proportional behaviour).

- [ ] **Step 5: Regression check — physics bounds**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/integration/test_phase1_integration.py -v
```

This is the critical gate. The allocation change affects every sector's energy multiplier. If bounds fail, the allocation change shifted the energy balance; diagnose which trajectory broke before adjusting anything.

- [ ] **Step 6: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/core/central_registrar.py tests/unit/test_central_registrar_a3.py
git commit -m "feat(registrar): demand-weighted allocation — proportional by default, ability-to-pay as scale"
```

---

## Task 4: SEIR + Population — Cohort Maturation Coupling

`population.py` computes `mat1/mat2/mat3` (persons/year flowing from cohort i to i+1) but never exports them. `seir.py` therefore has no aging — infected people in the 0–14 cohort stay there forever. This task exports the flows from population and applies them proportionally to SEIR compartments.

**Background on the math:**
- `mat1` = persons/year aging from C1 (0–14) → C2 (15–44)
- `mat2` = persons/year aging from C2 (15–44) → C3 (45–64)
- `mat3` = persons/year aging from C3 (45–64) → C4 (65+)
- For SEIR cohort `i`, the out-fraction per year = `mat_i / max(P_i, 1.0)` where P_i is the total population in that cohort.
- The SEIR aging terms added to each compartment (e.g. S) for cohort `i`: `aging_out = S_i * out_frac_i` and `aging_in = S_{i-1} * out_frac_{i-1}` (if i > 0).

**Files:**
- Create: `tests/unit/test_seir_maturation.py`
- Modify: `pyworldx/sectors/population.py`
- Modify: `pyworldx/sectors/seir.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_seir_maturation.py
from __future__ import annotations
import numpy as np
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.seir import SEIRModule


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _pop_inputs() -> dict[str, Quantity]:
    return {
        "food_per_capita": Quantity(400.0, "food_units_per_person"),
        "industrial_output": Quantity(7.9e10, "industrial_output_units"),
        "pollution_index": Quantity(1.0, "dimensionless"),
        "service_output_per_capita": Quantity(87.0, "service_units_per_capita"),
        "supply_multiplier_population": Quantity(1.0, "dimensionless"),
        "labor_force_multiplier": Quantity(1.0, "dimensionless"),
        "toxin_health_multiplier": Quantity(1.0, "dimensionless"),
        "toxin_fertility_multiplier": Quantity(1.0, "dimensionless"),
        "disease_death_rate": Quantity(0.0, "per_year"),
        "gini_mortality_mult": Quantity(1.0, "dimensionless"),
        "total_migration_flow": Quantity(0.0, "persons"),
        "energy_supply_factor": Quantity(1.0, "dimensionless"),
    }


def test_population_exports_mat1_mat2_mat3() -> None:
    """PopulationSector.compute() must include mat1, mat2, mat3 in its output."""
    s = PopulationSector()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    out = s.compute(0.0, stocks, _pop_inputs(), ctx)
    for key in ("mat1", "mat2", "mat3"):
        assert key in out, f"PopulationSector must export {key}"
        assert out[key].magnitude > 0.0, f"{key} must be positive at t=0 (population is aging)"


def test_population_declares_writes_mat_flows() -> None:
    """PopulationSector.declares_writes() must include mat1, mat2, mat3."""
    s = PopulationSector()
    for key in ("mat1", "mat2", "mat3"):
        assert key in s.declares_writes(), f"declares_writes() must include {key}"


def test_seir_declares_reads_mat_flows() -> None:
    """SEIRModule.declares_reads() must include mat1, mat2, mat3."""
    s = SEIRModule()
    for key in ("mat1", "mat2", "mat3"):
        assert key in s.declares_reads(), f"declares_reads() must include {key}"


def test_seir_aging_reduces_young_cohort_susceptibles() -> None:
    """With positive mat flows, dS for C1 (0-14) must be lower than without maturation."""
    s = SEIRModule()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    # Common base inputs
    base = {
        "POP": Quantity(1.65e9, "persons"),
        "P1": Quantity(0.4e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "P4": Quantity(0.25e9, "persons"),
        "birth_rate": Quantity(5.0e7, "persons_per_year"),
        "death_rate": Quantity(0.01, "per_year"),
    }
    inputs_no_aging = {**base}
    inputs_with_aging = {
        **base,
        "mat1": Quantity(2.0e7, "persons_per_year"),  # realistic: 20M age out of C1/yr
        "mat2": Quantity(1.5e7, "persons_per_year"),
        "mat3": Quantity(1.0e7, "persons_per_year"),
    }
    out_no = s.compute(0.0, stocks, inputs_no_aging, ctx)
    out_with = s.compute(0.0, stocks, inputs_with_aging, ctx)
    # C1 loses susceptibles to aging → dS_C1 must be lower (more negative) with aging
    assert out_with["d_S_C1"].magnitude < out_no["d_S_C1"].magnitude, (
        "Aging must remove susceptibles from C1: dS_C1 with aging must be < without"
    )


def test_seir_aging_increases_adult_cohort_susceptibles() -> None:
    """Aging must add susceptibles to C2 (15-44) from C1 outflow."""
    s = SEIRModule()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    base = {
        "POP": Quantity(1.65e9, "persons"),
        "P1": Quantity(0.4e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "P4": Quantity(0.25e9, "persons"),
        "birth_rate": Quantity(5.0e7, "persons_per_year"),
        "death_rate": Quantity(0.01, "per_year"),
    }
    inputs_no_aging = {**base}
    inputs_with_aging = {
        **base,
        "mat1": Quantity(2.0e7, "persons_per_year"),
        "mat2": Quantity(1.5e7, "persons_per_year"),
        "mat3": Quantity(1.0e7, "persons_per_year"),
    }
    out_no = s.compute(0.0, stocks, inputs_no_aging, ctx)
    out_with = s.compute(0.0, stocks, inputs_with_aging, ctx)
    # C2 gains susceptibles from C1 aging → dS_C2 must be higher with aging
    assert out_with["d_S_C2"].magnitude > out_no["d_S_C2"].magnitude, (
        "Aging must add susceptibles to C2: dS_C2 with aging must be > without"
    )


def test_seir_no_crash_with_zero_mat_flows() -> None:
    """SEIR must not crash when mat1/mat2/mat3 are absent (defaults to 0)."""
    s = SEIRModule()
    ctx = _ctx()
    stocks = s.init_stocks(ctx)
    inputs = {
        "POP": Quantity(1.65e9, "persons"),
        "P1": Quantity(0.4e9, "persons"),
        "P2": Quantity(0.7e9, "persons"),
        "P3": Quantity(0.3e9, "persons"),
        "P4": Quantity(0.25e9, "persons"),
        "birth_rate": Quantity(5.0e7, "persons_per_year"),
        "death_rate": Quantity(0.01, "per_year"),
    }
    out = s.compute(0.0, stocks, inputs, ctx)
    for k, v in out.items():
        assert v.magnitude == v.magnitude, f"NaN in {k}"  # NaN check
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_seir_maturation.py -v
```

Expected: fails on `test_population_exports_mat1_mat2_mat3` — `mat1` not in output dict.

- [ ] **Step 3: Implement — population.py**

**Edit A** — Add `mat1`, `mat2`, `mat3` to the return dict (after the existing `"death_rate"` entry, around line 380):

```python
        return {
            "d_P1": Quantity(d_p1, "persons"),
            "d_P2": Quantity(d_p2, "persons"),
            "d_P3": Quantity(d_p3, "persons"),
            "d_P4": Quantity(d_p4, "persons"),
            "d_POP": Quantity(d_pop, "persons"),
            "d_PLE": Quantity(d_ple, "years"),
            "d_EHSPC": Quantity(d_ehspc, "dollars_per_person"),
            "d_AIOPC": Quantity(d_aiopc, "industrial_output_units"),
            "d_DIOPC": Quantity(d_diopc, "industrial_output_units"),
            "d_FCFPC": Quantity(d_fcfpc, "dollars_per_person"),
            # Aggregate for downstream sectors
            "POP": Quantity(pop, "persons"),
            "P1": Quantity(p1, "persons"),
            "P2": Quantity(p2, "persons"),
            "P3": Quantity(p3, "persons"),
            "P4": Quantity(p4, "persons"),
            "birth_rate": Quantity(births, "persons_per_year"),
            "death_rate": Quantity(total_deaths, "persons_per_year"),
            "life_expectancy": Quantity(life_expectancy, "years"),
            # Maturation flows for SEIR cohort aging
            "mat1": Quantity(mat1, "persons_per_year"),
            "mat2": Quantity(mat2, "persons_per_year"),
            "mat3": Quantity(mat3, "persons_per_year"),
        }
```

**Edit B** — Add `"mat1"`, `"mat2"`, `"mat3"` to `declares_writes()`:

```python
    def declares_writes(self) -> list[str]:
        return [
            "P1",
            "P2",
            "P3",
            "P4",
            "POP",
            "birth_rate",
            "death_rate",
            "life_expectancy",
            "mat1",
            "mat2",
            "mat3",
        ]
```

- [ ] **Step 4: Implement — seir.py**

**Edit A** — Add `"mat1"`, `"mat2"`, `"mat3"` to `declares_reads()`:

```python
    def declares_reads(self) -> list[str]:
        return [
            "temperature_anomaly",
            "P1", "P2", "P3", "P4",
            "birth_rate",
            "death_rate",
            "mat1",
            "mat2",
            "mat3",
        ]
```

**Edit B** — Read the maturation flows near the top of `compute()`, after the existing `birth_rate`/`death_rate` reads. Find where `pop_by_cohort` is populated (around line 156) and add after it:

```python
        # Maturation flows from PopulationSector (persons/year aging between cohorts).
        # Default 0.0 preserves pre-coupling behaviour when population sector is absent.
        mat_vals = [
            inputs.get("mat1", Quantity(0.0, "persons_per_year")).magnitude,  # C1→C2
            inputs.get("mat2", Quantity(0.0, "persons_per_year")).magnitude,  # C2→C3
            inputs.get("mat3", Quantity(0.0, "persons_per_year")).magnitude,  # C3→C4
            0.0,  # C4 (65+): no out-flow to next cohort
        ]
```

**Edit C** — Add aging in/out terms to the SEIR ODEs inside the cohort loop. Replace the existing `dS`, `dE`, `dI`, `dR` assignments (lines 239–242) with:

```python
            # Proportional aging: fraction of this cohort that ages into next
            out_frac = mat_vals[i] / max(pop, 1.0)
            # In-flow: previous cohort's aging fraction applied to their SEIR stocks
            if i > 0:
                prev_pop = pop_by_cohort[i - 1]
                in_frac = mat_vals[i - 1] / max(prev_pop, 1.0)
                aging_in_s = S_vals[i - 1] * in_frac
                aging_in_e = E_vals[i - 1] * in_frac
                aging_in_i = I_vals[i - 1] * in_frac
                aging_in_r = R_vals[i - 1] * in_frac
            else:
                aging_in_s = aging_in_e = aging_in_i = aging_in_r = 0.0

            # SEIR dynamics with cohort aging
            dS = births - foi_c * s - deaths_s - s * out_frac + aging_in_s
            dE = foi_c * s - self.sigma * e - deaths_e - e * out_frac + aging_in_e
            dI = self.sigma * e - self.gamma * iv - deaths_i - iv * out_frac + aging_in_i
            dR = self.gamma * iv - deaths_r - r * out_frac + aging_in_r
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/unit/test_seir_maturation.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Run ruff and mypy**

```bash
cd /Users/johnny/pyWorldX && python3 -m ruff check pyworldx/ tests/ && python3 -m mypy pyworldx
```

Expected: no errors.

- [ ] **Step 7: Full regression check**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/ -q
```

Expected: 842+ passed. If `test_phase1_integration.py` fails on a physics bound, the aging flows are redistributing population in a way that changes the labor force; check `labor_force_multiplier` trajectory.

- [ ] **Step 8: Commit**

```bash
cd /Users/johnny/pyWorldX && git add pyworldx/sectors/population.py pyworldx/sectors/seir.py tests/unit/test_seir_maturation.py
git commit -m "feat(seir+population): export mat1/2/3 from population; proportional SEIR cohort aging"
```

---

## Task 5: Final Integration Verification

- [ ] **Step 1: Run the full suite**

```bash
cd /Users/johnny/pyWorldX && python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: all tests pass, count ≥ 860.

- [ ] **Step 2: Run ruff + mypy**

```bash
cd /Users/johnny/pyWorldX && python3 -m ruff check pyworldx/ tests/ && python3 -m mypy pyworldx
```

Expected: `All checks passed!` and `Success: no issues found in 96 source files`.

- [ ] **Step 3: Push**

```bash
cd /Users/johnny/pyWorldX && git push origin phase-2-remediation
```

---

## Self-Review

**Spec coverage:**
1. ✅ capital.py tech_rd_cost — Task 1
2. ✅ finance.leverage_fraction=0.0 default + minsky_moment=0.2 — Task 2
3. ✅ CentralRegistrar demand-weighted (delete all_default, use demand×weight) — Task 3
4. ✅ SEIR maturation flows — Task 4
5. ✅ Preserve test_phase1_integration.py physics bounds — regression check after every task

**Placeholder scan:** No TBDs. Every edit block contains the exact replacement code.

**Type consistency:**
- `mat_vals: list[float]` — consistent across Task 4 edits
- `out_frac`, `in_frac` — local floats, no type annotation needed (mypy infers)
- `weights: dict[str, float]` — consistent with existing `multipliers: dict[str, float]` in registrar
- `leverage_fraction: float = 0.0` — matches `interest_rate: float` pattern in `FinanceSector.__init__`
- `Quantity(mat1, "persons_per_year")` — unit string is consistent with `birth_rate` unit in population.py
