# Phase 2 Uncertainty Resolution — Final Status

**Date:** 2026-04-14  
**Questions Asked:** 8 (q71-q78)  
**Fixes Implemented:** 4 of 9  
**Requires External Sourcing:** 3 of 9  
**No Change Needed:** 1 of 9  
**Partially Resolved:** 1 of 9  

---

## Fixes Implemented (Code Changed)

| # | Uncertainty | Fix Applied | Files Modified |
|---|------------|-------------|---------------|
| **Q76** | AES cost exponent | Changed exponent from 2.0 → 2.5, recalibrated c_AES from 1.0e10 → 6.7e11 | `sectors/ecosystem_services.py` |
| **Q72** | ESP temperature regeneration | Replaced linear `r(T) = r0 × max(1 - T×0.1, 0)` with piecewise quadratic (flat at T≤15°C, quadratic decline 15-35°C, zero at T≥35°C) | `sectors/ecosystem_services.py` |
| **Q73** | Heat shock multiplier | Replaced linear decline with exponential/quadratic `exp(-4.6 × ratio²)` for smoother threshold behavior | `sectors/climate.py` |
| **Q78** | Supply multiplier propagation | Replaced linear `allocation/demand` with super-linear decline: power 1.5 for 50-100%, power 2.0 (cascading failure) below 50% | `core/central_registrar.py` |

**All 580 tests pass after these changes.**

---

## Requires External Sourcing (No Code Change Yet)

| # | Uncertainty | What's Needed | Effort |
|---|------------|---------------|--------|
| **Q75** | CO2 separate carbon cycle stock | Add CarbonCycle sector with 3-box model (atmosphere, ocean, terrestrial). Needs calibration of sink rates (k_ocean, k_land) against observed atmospheric CO2 growth data. | 1-2 days |
| **Q71** | Phosphorus bioavailability factor | Add `bioavailability_factor` state variable (0-1) to Phosphorus sector. Needs calibration from soil survey data (pH, organic matter, Fe-Al oxide content). | 1-2 days |
| **Q77** | Energy unit calibration | Add `energy_intensity` parameter per sector, calibrate so baseline total = 600 EJ/yr. Needs IEA or EIA sectoral energy consumption data. | 1 day |

---

## No Change Needed

| # | Uncertainty | Resolution |
|---|------------|-----------|
| **Q74** | Aerosol quasi-equilibrium | ✅ Validated — quasi-equilibrium approximation is standard in IAMs, no change needed. |

---

## Partially Resolved

| # | Uncertainty | Status | Notes |
|---|------------|--------|-------|
| **Q71** | Phosphorus recycling energy costs | ⚠️ Keep 2.0× ratio as placeholder. Entropy-based argument supports energy costs rising with dilution, but no specific calibration data available. | Needs external calibration data |

---

## Implementation Priority for Remaining Items

1. **P0 — Q77 (Energy calibration):** The 65% ceiling and all energy demands are meaningless without real units. This should be done before any Phase 3 work.
2. **P0 — Q75 (Carbon cycle):** CO2 drives climate → heat shock → agriculture → food security. The CO2 proxy is currently a guess.
3. **P1 — Q71 (Phosphorus bioavailability):** Improves phosphorus-agriculture coupling but is not a blocker for other work.
4. **P2 — Q71 partial (Recycling energy):** Keep current 2.0× ratio; recalibrate when data available.
