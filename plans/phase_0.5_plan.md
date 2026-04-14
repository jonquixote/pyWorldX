# Phase 0.5 — v1 Correctness Fixes

**Date:** 2026-04-14  
**Goal:** Fix structural correctness gaps in v1 before building v2 architecture  
**Duration:** 1-2 weeks  
**Scope:** 3 tasks that make World3-03 structurally correct without adding v2 architecture  

---

## Rationale

Phase 0 gets the release gate checklist done and runs validation for the first time. But validation will show NRMSD errors partly caused by structural simplifications: linear depreciation instead of nonlinear, wrong pollution delay. Phase 0.5 fixes these structural gaps so that when we build v2 on top, the v1 baseline is accurate.

---

## Task 1: Nonlinear Depreciation (φ Maintenance Gap)

**Status:** ❌ Linear ALIC (`depreciation = IC / 14`) instead of φ(MaintenanceRatio)  
**Source:** Notebook q11, q54  
**Effort:** 2-3 days

### The Problem

Current: `depreciation = IC / ALIC` (constant 14-year lifetime)  
Correct: `depreciation = (IC / ALIC) × φ(MaintenanceRatio)`

Where:
- `MaintenanceRatio = Actual_Maintenance_Investment / Required_Maintenance`
- `φ(ratio)` = 1.0 when ratio ≥ 1.0, exponential spike when ratio < 1.0, bounded at 2.0-4.0×
- When Liquid Funds are exhausted and 150% Debt ceiling blocks borrowing → Maintenance Investment drops → MaintenanceRatio < 1.0 → φ spikes → capital physically unravels faster than design lifetime

### Critical Design Fix (from audit)

**The φ formula is NOT specified by the notebooks.** q11 says "a lookup table or exponential function where φ = 1.0 if the ratio is ≥ 1.0, but spikes exponentially (e.g., to 2.0 or 4.0x) as the ratio drops toward zero." q54 explicitly states: "The provided literature and project documentation do not specify a precise mathematical equation or exact lookup-table coordinates for the phi multiplier."

The formula `φ = 1 + 3 × (1 - ratio)²` is a **design choice** that satisfies the boundary conditions:
- φ(1.0) = 1.0 (flat at baseline)
- φ(0.0) = 4.0 (capped at 4×)
- φ(0.5) = 1.75 (moderate acceleration)
- Monotonically decreasing

It is **quadratic**, not exponential. Code comments must be accurate.

### Implementation

**File:** `pyworldx/sectors/capital.py`

Add φ function as a module-level utility:
```python
def depreciation_multiplier(maintenance_ratio: float) -> float:
    """φ(MaintenanceRatio) — nonlinear depreciation acceleration.
    
    DESIGN NOTE: The notebooks (q11, q54) specify the behavioral shape
    (flat at 1.0 when ratio >= 1.0, spikes to 2.0-4.0x below 1.0) but do
    NOT specify a precise formula. This quadratic function satisfies the
    boundary conditions: φ(1.0)=1.0, φ(0.0)=4.0, monotonic.
    """
    if maintenance_ratio >= 1.0:
        return 1.0
    if maintenance_ratio <= 0.0:
        return 4.0
    # Quadratic: φ = 1 + 3 × (1 - ratio)²
    return min(1.0 + 3.0 * (1.0 - maintenance_ratio) ** 2, 4.0)
```

Modify capital sector's `compute()`:
```python
# Get maintenance ratio (defaults to 1.0 for Phase 0.5 compatibility)
maintenance_ratio = inputs.get("maintenance_ratio", Quantity(1.0, "dimensionless")).magnitude

# Current (linear):
# ic_depreciation = ic / self.alic

# New (nonlinear):
base_depreciation = ic / self.alic
phi = depreciation_multiplier(maintenance_ratio)
ic_depreciation = base_depreciation * phi
```

**Update `declares_reads()`:** Add `"maintenance_ratio"` so the dependency graph knows capital depends on the finance sector (when it arrives in Phase 1).

**Update parameter registry:** Add `capital.maintenance_ratio` to `parameters.py` with default=1.0, bounds=(0.0, 2.0), scenario_mutable=False.

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_phi_at_1.0_is_1.0` | φ(1.0) = 1.0 |
| 2 | `test_phi_at_0.5_is_quadratic` | φ(0.5) = 1.75 |
| 3 | `test_phi_at_0.0_is_bounded` | φ(0.0) = 4.0 (capped) |
| 4 | `test_phi_at_negative_is_bounded` | φ(-1.0) = 4.0 (capped) |
| 5 | `test_phi_monotonic` | φ is monotonically decreasing |
| 6 | `test_capital_depreciation_accelerates` | Capital sector depreciation increases when maintenance_ratio < 1.0 |
| 7 | `test_default_maintenance_ratio_is_1.0` | Without explicit input, φ=1.0 (no change from v1 behavior) |
| 8 | `test_full_engine_no_regression` | World3-03 run with default maintenance_ratio=1.0 produces byte-identical output to Phase 0 |

### Acceptance Criteria

- [ ] φ function implemented with correct shape (flat at 1.0, quadratic below, bounded at 4.0)
- [ ] Capital sector uses φ when maintenance_ratio input is provided
- [ ] `maintenance_ratio` added to capital sector's `declares_reads()`
- [ ] `capital.maintenance_ratio` registered in parameter registry (default=1.0)
- [ ] Default maintenance_ratio=1.0 produces identical output to Phase 0 (no regression)
- [ ] All 8 tests pass
- [ ] All Phase 0 tests still pass
- [ ] mypy strict passes

---

## Task 2: Pollution Delay Recalibration (pptd: 20 → 111.8)

**Status:** ⚠️ NEBEL_2024 preset sets pptd=111.8 but sector default is 20  
**Source:** Notebook q11, Nebel 2024 paper  
**Effort:** 1 day

### The Problem

The Nebel 2024 recalibration found that the pollution transmission delay (pptd) should be 111.8 years, not the original 20 years. The `NEBEL_2024` preset overrides this, but the PollutionSector's hardcoded default is still 20.

**Confirmed by audit:** PPTD is already used as a 3rd-order delay (3-stage cascade with `stage_delay = pptd / 3.0`). So the structural implementation is correct — only the default value needs changing.

### Implementation

**File:** `pyworldx/sectors/pollution.py`

```python
# Current:
_PPTD = 20.0

# New:
_PPTD = 111.8  # Nebel et al. 2024 recalibration (DOI: 10.1111/jiec.13442)
```

**File:** `pyworldx/calibration/parameters.py`

```python
# Current:
reg.register(ParameterEntry(
    name="pollution.pptd",
    default=20.0,
    ...
    rationale="W3-03 PPTD = 20 years; Nebel 2024 recalibrated to 111.8",
))

# New:
reg.register(ParameterEntry(
    name="pollution.pptd",
    default=111.8,
    bounds=(50.0, 200.0),  # Widen bounds: 111.8 is close to old upper bound of 150
    ...
    rationale="Nebel et al. 2024 recalibration (DOI: 10.1111/jiec.13442)",
))
```

**Note:** The bounds need widening. With default=111.8 and old bounds=(10.0, 150.0), the default is very close to the upper bound. Expand to (50.0, 200.0).

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_pptd_default_is_111.8` | Pollution sector default matches Nebel 2024 |
| 2 | `test_pollution_slower_response` | Pollution trajectory responds more slowly with pptd=111.8 vs 20.0 |
| 3 | `test_3rd_order_delay_correct` | 3-stage cascade with stage_delay = pptd / 3.0 |
| 4 | `test_bounds_accommodate_default` | Parameter bounds contain the new default comfortably |

### Acceptance Criteria

- [ ] Pollution sector PPTD default = 111.8
- [ ] Parameter registry default = 111.8
- [ ] Parameter bounds widened to (50.0, 200.0)
- [ ] All 4 tests pass
- [ ] All Phase 0 tests still pass

---

## Task 3: FIOAA Deduplication

**Status:** ⚠️ Both capital.py and agriculture.py compute FIOAA independently  
**Source:** Code audit  
**Effort:** 1-2 days

### The Problem

Both sectors compute FIOAA using the same lookup table but different inputs:
- **capital.py:** `fpc_ratio = fpc / _SFPC` → `fioaa = table_lookup(fpc_ratio, _FIOAA_X, _FIOAA_Y)`
- **agriculture.py:** `fpc_ratio_alloc = prev_fpc / max(ifpc, 1.0)` → `fioaa = table_lookup(fpc_ratio_alloc, _FIOAA_X, _FIOAA_Y)`

The agriculture sector's version is correct (uses dynamic IFPC). Capital sector should read FIOAA from shared state, not compute it independently.

### Critical Design Fixes (from audit)

**Must update BOTH `declares_reads()` and `declares_writes()` in capital sector:**
1. Add `frac_io_to_agriculture` to `declares_reads()` — so the dependency graph orders agriculture before capital
2. Remove `frac_io_to_agriculture` from `declares_writes()` — capital is no longer the source of truth

Without the `declares_reads()` update, the engine's topological sort will NOT automatically order agriculture before capital. The plan originally claimed this would happen automatically — **this is incorrect**.

**Fallback default:** Capital should have a reasonable default for FIOAA if agriculture hasn't written it yet (for standalone testing):
```python
fioaa = inputs.get("frac_io_to_agriculture", Quantity(0.1, "dimensionless")).magnitude
```

### Implementation

**File:** `pyworldx/sectors/capital.py`

```python
# Remove FIOAA computation:
# fioaa = table_lookup(fpc_ratio, _FIOAA_X, _FIOAA_Y)

# Replace with read from shared state:
fioaa = inputs.get("frac_io_to_agriculture", Quantity(0.1, "dimensionless")).magnitude
```

Update `declares_reads()`:
```python
def declares_reads(self) -> list[str]:
    return [
        ...,
        "frac_io_to_agriculture",  # NEW — read from agriculture sector
        ...,
    ]
```

Update `declares_writes()`:
```python
def declares_writes(self) -> list[str]:
    return [
        "IC",
        "SC",
        ...,
        # REMOVE: "frac_io_to_agriculture" — agriculture is now the source of truth
        ...,
    ]
```

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_capital_reads_fioaa_from_shared` | Capital sector doesn't compute FIOAA, reads from inputs |
| 2 | `test_agriculture_writes_fioaa` | Agriculture sector writes frac_io_to_agriculture |
| 3 | `test_execution_order_agriculture_before_capital` | Topological sort puts agriculture before capital (via declares_reads) |
| 4 | `test_full_engine_fioaa_consistent` | Single source of truth for FIOAA in full World3-03 run |
| 5 | `test_capital_standalone_uses_default_fioaa` | Capital sector works in isolation with default FIOAA fallback |

### Acceptance Criteria

- [ ] Capital sector no longer computes FIOAA independently
- [ ] Capital sector reads FIOAA from shared state (written by agriculture)
- [ ] `frac_io_to_agriculture` added to capital's `declares_reads()`
- [ ] `frac_io_to_agriculture` removed from capital's `declares_writes()`
- [ ] Topological sort correctly orders agriculture before capital
- [ ] All 5 tests pass
- [ ] All previous tests still pass

---

## Task Dependencies

```
Task 2 (PPTD recalibration) ── 1 day ── independent
Task 3 (FIOAA dedup) ────────── 1-2 days ── independent
Task 1 (Nonlinear depreciation) ── 2-3 days ── independent

Can all run in parallel. No dependencies between them.
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Nonlinear depreciation changes baseline trajectories | Certain (by design) | Medium — will change IC/SC trajectories | Document the change; re-run validation to see if NRMSD improves or worsens |
| PPTD=111.8 makes pollution respond much slower | Certain (by design) | Medium — pollution trajectory will shift significantly | Re-run validation; this should actually improve NRMSD for pollution since Nebel calibrated with this value |
| FIOAA dedup changes capital allocation slightly | Low | Low — agriculture's IFPC-based FIOAA is more accurate | Document any trajectory changes |
| φ formula is a design choice, not from notebooks | Certain | Low — formula satisfies all stated boundary conditions | Document as design choice; make it configurable via lookup table in Phase 1 |

---

## Definition of Done

- [ ] All 3 tasks completed
- [ ] All new tests pass (8 + 4 + 5 = 17 tests)
- [ ] All Phase 0 tests still pass (470 + 9 + 7 + 11 + 2 = 499 tests)
- [ ] World3-03 validation re-run with corrected structure — new NRMSD documented
- [ ] mypy strict passes on all modified files
- [ ] ruff check passes on all modified files
