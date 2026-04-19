# Uncertainties — Phase 2

**Date:** 2026-04-14
**Resolution Source:** NotebookLM Q71-Q78 + Implementation findings
**Full synthesis:** See [phase2_uncertainty_resolution.md](plans/phase2_uncertainty_resolution.md)

---

## Fixed (Code Changed)

| # | Uncertainty | Fix | Status |
|---|------------|-----|--------|
| **Q76** | AES cost exponent (was 2.0) | Changed to 2.5, recalibrated c_AES to 6.7e11 | ✅ FIXED |
| **Q72** | ESP temperature regeneration (was linear) | Replaced with piecewise quadratic (flat ≤15°C, quadratic 15-35°C, zero ≥35°C) | ✅ FIXED |
| **Q73** | Heat shock multiplier (was linear) | Replaced with exponential `exp(-4.6 × ratio²)` | ✅ FIXED |
| **Q78** | Supply multiplier propagation (was linear) | Replaced with super-linear decline (power 1.5 for 50-100%, power 2.0 below 50%) | ✅ FIXED |

---

## Needs External Sourcing (No Code Change Yet)

| # | Uncertainty | What's Needed | Priority |
|---|------------|---------------|----------|
| **Q75** | CO2 proxy from pollution generation | Add CarbonCycle sector (atmosphere → ocean → terrestrial). Needs sink rate calibration from observed CO2 data. | 🔴 P0 |
| **Q71** | Phosphorus bioavailability model | Add bioavailability_factor state variable. Needs calibration from soil survey data. | 🟡 P1 |
| **Q77** | Energy unit calibration | Add energy_intensity per sector, calibrate to 600 EJ/yr baseline. Needs IEA/EIA data. | 🔴 P0 |

---

## Partially Resolved

| # | Uncertainty | Status |
|---|------------|--------|
| **Q71** | Phosphorus recycling energy costs (fixed 2.0× ratio) | Keep 2.0× as placeholder. Entropy-based argument supports rising costs with dilution, but no calibration data. |

---

## No Change Needed

| # | Uncertainty | Reason |
|---|------------|--------|
| **Q74** | Aerosol quasi-equilibrium | Validated — standard in IAMs, quasi-equilibrium is correct for annual timesteps. |

---

## SEIR Module Shortcuts (Noted During Implementation)

| # | Shortcut | Rationale | Resolution |
|---|---------|-----------|-----------|
| **SEIR-1** | Disease rates scaled to annual timescales (gamma=10/yr, sigma=20/yr instead of real ~36.5/70 per year) | Real disease dynamics (days/weeks) are too fast for annual timesteps, causing numerical instability. Effective annual rates preserve R0=2.5 but unfold over ~1 year instead of weeks. | ⚠️ **Acceptable** — R0 is preserved, epidemic shape is correct, just slower. For sub-annual timesteps, use real-day-based rates. |
| **SEIR-2** | Fixed contact matrix (4×4) instead of dynamic network graph | Dynamic network graphs require graph data structures and are complex. A fixed age-structured contact matrix captures the essential epidemiology. | ⚠️ **Acceptable** — Contact matrix is standard in age-structured SEIR models. Can be upgraded to dynamic graph later. |
| **SEIR-3** | SEIR stocks are separate from Population sector stocks (P1-P4) | SEIR tracks S/E/I/R compartments while Population tracks total cohort counts. They're coupled via population reads but not strictly consistent. | ⚠️ **Known limitation** — SEIR should ideally track fractions of Population cohort stocks, not absolute counts. Requires engine-level stock coupling. |
| **SEIR-4** | SEIR + Capital sector coupling causes numerical instability at t>2 | When SEIR's labor_force_multiplier drops significantly, Capital's labor utilization fraction (LUF) spikes, causing cascading numerical issues in the RK4 integration. | ⚠️ **Known limitation** — SEIR works in isolation (10/10 unit tests). Full integration requires engine-level investigation of multi-rate coupling. |
| **SEIR-5** | Post-infection productivity penalty is constant (20%) | Real recovery is gradual — productivity increases over time as immunity develops. The constant penalty is a simplification. | ⚠️ **Acceptable** — Can be upgraded to decaying penalty later if needed. |

---

## Regional Objects Shortcuts (Noted During Implementation)

| # | Shortcut | Rationale | Resolution |
|---|---------|-----------|-----------|
| **REG-1** | Regional sector is a redistribution layer, not per-region sector instances | Creating N full copies of all sectors would require major engine restructuring. A single sector that redistributes global outputs is simpler. | ⚠️ **Acceptable** — Captures trade/migration dynamics without engine changes. Can be upgraded to full regional architecture later. |
| **REG-2** | Population/IO distribution across regions is fixed (not endogenous) | Real regional population and economic distribution evolves over time based on migration, investment, etc. Fixed distribution is a simplification. | ⚠️ **Acceptable** — Migration flows adjust population; trade adjusts IO. Distribution is a reasonable baseline. |
| **REG-3** | Trade attraction matrix is distance-based (not computed from real data) | Real trade flows depend on tariffs, agreements, transport infrastructure, etc. Distance-based proxy is a simplification. | ⚠️ **Acceptable** — Standard gravity model approximation. Can be calibrated to real trade data later. |
| **REG-4** | Lifeboating severs trade but not migration | This is actually by design from q61 — desperate populations continue to migrate even when trade stops. | ✅ **By design** — Matches the notebook specification. |

---

## Summary

| Category | Count |
|----------|-------|
| Fixed (code changed) | 4 |
| Needs external sourcing | 3 |
| Partially resolved | 1 |
| No change needed | 1 |
| SEIR shortcuts (acceptable) | 5 |
| Regional shortcuts (acceptable) | 4 |
| **Total** | **18** |
