# 5-Stock Global Carbon Model Implementation Plan

**Date:** 2026-04-15
**Goal:** Rewrite `PollutionGHGModule` from a single-stock 100-year delay approximation into a rigorous 5-stock global carbon model, calibrated against NOAA/GCB 2024 data with Gaian feedback loops (Q84, Q75).

## 1. Architectural Overview

The current `PollutionGHGModule` uses a single state variable (`ghg_stock`) representing an abstract pollution index. The rewrite will introduce **5 distinct state variables** representing carbon mass in Gigatonnes (GtC):
1.  **$C_{atm}$**: Atmospheric Carbon
2.  **$C_{land}$**: Land Biomass (Vegetation)
3.  **$C_{soc}$**: Soil Organic Carbon
4.  **$C_{ocean\_surf}$**: Ocean Surface (Dissolved Carbon)
5.  **$C_{ocean\_deep}$**: Deep Ocean & Sediments

### 1.1 Pre-Industrial Initial Conditions (t=1900)
*   `C_atm_0`: ~600 GtC (equivalent to ~280 ppm CO₂)
*   `C_land_0`: ~600 GtC
*   `C_soc_0`: ~1500 GtC
*   `C_ocean_surf_0`: ~1000 GtC
*   `C_ocean_deep_0`: ~38000 GtC

## 2. ODE Flux Definitions

The `compute()` function will calculate the rate of change for each stock ($dC/dt$) based on the following fluxes:

### A. Anthropogenic Emissions
Flows directly into $C_{atm}$ from the economy:
*   $F_{combustion}$ = `fossil_output * intensity`
*   $F_{calcination}$ = `industrial_output * intensity`
*   $F_{leakage}$ = `fossil_output * intensity`
*   **Total:** $F_{emissions} = F_{combustion} + F_{calcination} + F_{leakage}$

### B. Ocean Carbon Sink
Exchange between Atmosphere and Ocean Surface:
*   $F_{atm \to ocean\_surf} = k_{oa} \cdot (pCO_{2,atm} - pCO_{2,ocean})$
*   **Gaian Feedback:** Warmer oceans hold less dissolved CO₂. $k_{oa}$ or the equilibrium partition coefficient must decrease as `temperature_anomaly` ($T$) increases.
*   **Deep Mixing:** $F_{ocean\_surf \to ocean\_deep} = k_{od} \cdot (C_{ocean\_surf} - C_{eq\_surf})$

### C. Land Carbon Sink (Biosphere)
Exchange between Atmosphere, Vegetation, and Soil:
*   **NPP (Photosynthesis):** $F_{atm \to land} = NPP_0 \cdot \left(1 + \beta \ln\frac{C_{atm}}{C_{atm\_0}}\right)$ (CO₂ fertilization effect)
*   **Litter Fall:** $F_{land \to soc} = k_{litter} \cdot C_{land}$
*   **Plant Respiration / Biomass Loss:** $F_{land \to atm} = k_{resp\_plant} \cdot C_{land}$
*   **Soil Respiration (Microbial):** $F_{soc \to atm} = k_{resp\_soil} \cdot C_{soc}$

### D. Gaian Feedback Loop (Permafrost / Soil Carbon)
The soil respiration rate is highly sensitive to temperature.
*   $k_{resp\_soil}(T) = k_{resp\_soil\_0} \cdot Q_{10}^{(T / 10)}$
*   As $T$ rises, microbial decomposition accelerates, causing the soil matrix to outgas carbon back into the atmosphere. This effectively turns the land sink into a net emitter under high warming scenarios, fulfilling the "Gaian feedback" requirement (Q84).

## 3. Code Modifications

### 3.1 `pyworldx/sectors/pollution_ghg.py`
1.  **Remove:** Single `ghg_stock` logic and `_TAU_GHG` delay constant.
2.  **Add:** 5 state variables (`C_atm`, `C_land`, `C_soc`, `C_ocean_surf`, `C_ocean_deep`) to `init_stocks()` and `declares_writes()`.
3.  **Read Port:** Add `"temperature_anomaly"` to `declares_reads()` so the Gaian feedbacks can read $T$ from the Climate sector.
4.  **Compute Block:** Implement the ODE flux matrix.
5.  **Output Radiative Forcing:** $RF = 5.35 \cdot \ln(C_{atm} / C_{atm\_0})$. Provide this variable for backward compatibility with `ClimateSector`.

### 3.2 `pyworldx/sectors/climate.py`
*   Ensure the `ClimateSector` continues to correctly map `"ghg_radiative_forcing"` written by the `PollutionGHGModule`. (No structural changes required if the variable name remains consistent).

### 3.3 `pyworldx/sectors/phosphorus.py` & `agriculture.py`
*   Later integration: The $C_{soc}$ stock calculated here will eventually serve as the "living matrix" input for determining the "rooting depth resilience threshold" in the Agricultural and Phosphorus arrays (Task 4 of the overall Phase 2 refinement plan).

## 4. Testing & Validation
*   **Mass Conservation Test:** Verify that at any timestep $t$:
    $\sum C(t) = \sum C(0) + \int_0^t F_{emissions} dt$
    Total system carbon must be perfectly conserved.
*   **Analytical Test:** Verify the CO₂ fertilization and temperature-dependent outgassing isolate accurately against step-function inputs.
*   **Integration Test Update:** Ensure `test_phase1_integration.py` expects the 5 new state variables and doesn't look for the deprecated `ghg_stock`.

---
**Next Actions:** Begin modifying `pyworldx/sectors/pollution_ghg.py` and `tests/unit/test_pollution_ghg.py` according to this spec.