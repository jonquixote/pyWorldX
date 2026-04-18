# Phase 2 Implementation Refinements (q79–q84)

This synthesis integrates the latest architectural guidance and calibration targets for the pyWorldX v2.1 biophysical layer, following queries q79 through q84.

## 1. Human Capital ($H$) Calibration & Logic
- **Education Rate Correction (q79):** $H$ is a **dimensionless index (0–1.0)**. The `EducationRate` must be calibrated such that at pre-industrial equilibrium, it exactly balances the base `SkillDegradationRate`. Do **not** use statistical hacks (like arbitrary $1e^{-10}$ multipliers).
- **Analytical Test Stability (q80):** High-frequency dynamics in $H$ and SEIR require a high-frequency **substep ratio (e.g., 64:1 or 512:1)** to pass analytical tests with $1e^{-4}$ tolerance. $dt=1.0$ is insufficient.
- **Production Function Refactoring (q81):** A simple multiplier at the end of the production chain is **unacceptable**. You must refactor the core `CapitalSector` to use a true **Cobb-Douglas production function**:  
  $Q = A \cdot K^\alpha \cdot R^\beta \cdot H^{(1-\alpha-\beta)}$  
  This ensures $H$ correctly models the "intelligence bottleneck" during collapse via 50–60% output elasticity.
- **Implicit Energy Footprint (q82):** $H$ has no explicit energy demand. Its physical requirements are implicitly covered by the **Service Sector** energy mandate.

## 2. Infrastructure & Testing
- **Supply Multiplier Propagation (q78):** Reduced energy supply does not reduce production linearly. It triggers **"Ability to Pay"** priority chains and price spikes that zero out peripheral demand, creating a **"Maintenance Gap"** ($\phi$) that accelerates physical capital collapse.
- **Test Fixtures (q83):** Use **Sector-Port Encapsulation** for unit testing. Pass mock `RunContext` dicts of Quantities to verify boundary conditions in isolation.

## 3. Data Mapping (q84)
- **NOAA/GCB (Carbon):** Calibrates the 5-stock global carbon model and long-term exchange delays. Tracks the **Heat Shock Multiplier** in agriculture.
- **EIA (Energy):** Calibrates the baseline for the **65% Thermodynamic Energy Ceiling** and sectoral energy intensity.
- **USDA SSURGO (Phosphorus):** Initializes $P_{soc}$ and parameterizes geological weathering to calibrate the **rooting depth resilience threshold**.
