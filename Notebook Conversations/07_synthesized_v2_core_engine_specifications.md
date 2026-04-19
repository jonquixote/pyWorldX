# Synthesized v2 Core Engine Specifications

Following the completion of the full 57-query NotebookLM research corpus, this document synthesizes the explicit Python engine architecture patterns required for PyWorldX v2. These specifications define how the RK4 solver, CentralRegistrar, and sector modules must be structurally organized to enforce thermodynamic mass-balance while avoiding algebraic deadlocks.

## I. The CentralRegistrar Pipeline

The CentralRegistrar is not a sector — it is an **orchestration pass** within the engine core that sits between the scheduler and the sector derivative computation. It transforms the engine flow from a simple sequential loop into a constrained demand-resolution cycle.

### Current v1 Engine Flow
```
t → topological sort → sector.compute() for each → RK4 step → advance
```

### Required v2 Engine Flow
```
t → sector.broadcast_demand()
  → CentralRegistrar collects all demands
  → evaluate 65% Energy Ceiling
  → compute SupplyMultipliers (< 1.0 if ceiling hit)
  → broadcast SupplyMultipliers back to sectors
  → topological sort → sector.compute() (constrained) → RK4 step → advance
```

### Step-by-Step Resolution Logic

**Step A — Demand Linkages:** Each sector posts its resource/energy demands to a centralized demand registry. Technology Energies (solar, wind) broadcast strict material demands for elements like Silver, Gallium, Indium, Neodymium, and Lithium. Agriculture broadcasts water and phosphorus demands. The demands are aggregated into vectorized arrays.

**Step B — 65% Energy Ceiling Evaluation:** The CentralRegistrar sums total energy demanded by *all* resource extraction globally. If the aggregate exceeds **65% of total available energy**, the unconstrained execution is halted.

**Step C — SupplyMultiplier Broadcast:** If the ceiling is breached, the CentralRegistrar computes SupplyMultipliers (< 1.0) and broadcasts them back to the requesting sectors. The strict rule: **"When actual supply to a module is less than demand, then production is reduced."**

**Step D — Market-Driven Allocation (Not Equal Scaling):** The SupplyMultiplier is **not** a uniform linear scaler. Allocation is prioritized through endogenous market price mechanisms based on **"Ability to Pay"** (Liquid Funds available to each sector/cohort) and **"Security Value"** (strategic importance). During scarcity, price spikes mean only the wealthy core can afford resources; the bottom 90%'s effective demand approaches zero. **Basic survival sectors are NOT universally protected** — the market mechanism starves vulnerable populations.

## II. The Energy Sector — Disaggregated Sub-Sector Architecture

The Energy Sector must **not** be a single aggregated module. Following the WORLD6/7 architecture, it is split into three categories, each with independent EROI curves:

| Sub-Sector | Components | EROI Driver | Material Bottleneck |
|------------|-----------|-------------|---------------------|
| **Fossil Fuels** | Oil, Gas, Coal, Conventional Nuclear (U, Th) | Ore grade decline → EROI drops non-linearly | Abundant — no technology metal constraint |
| **Sustainable/Renewable** | Hydropower, Biofuels | Renewable flows — EROI relatively stable | Land use, water availability |
| **Technology Energies** | Solar PV, Wind, Geothermal | Technology metal extraction cost → EROI is function of rare earth availability | **Silver, Gallium, Indium, Neodymium, Lithium** — hard scarcity ~2100 |

### Capital Competition via Endogenous Profitability
*   Each sub-sector generates income = Energy Supplied × Market Price.
*   Cost of Production = $f(\text{EROI}, \text{material requirements})$.
*   Profit = Income − Cost → higher profit attracts more Investment from Liquid Funds.
*   **Key constraint:** Even if Technology Energies has massive financial capital, the RK4 engine **prohibits** instantiation of solar/wind arrays if physical materials cannot be supplied due to the 65% ceiling. Trapped financial capital either remains unspent (lowering COR) or is out-competed by lower-complexity systems (coal, hydro) that don't trigger rare-metal bottlenecks.

## III. State-Gating — Algebraic Loop Prevention

Every cross-sector feedback loop in the v2 architecture **must** contain at least one Integrator (Stock/Level) or Significant Delay. This is the fundamental mechanism that prevents algebraic deadlocks in the RK4 solver.

### The Rule
No auxiliary variable may simultaneously read from and write to another auxiliary variable across sector boundaries within the same RK4 k-stage. All inter-sector communication passes through **Stocks** whose values are fixed at the beginning of each step and updated only at the end.

### Critical State-Gated Variables

| Variable | Type | Why It Must Be a Stock |
|----------|------|----------------------|
| **Industrial Capital (IC)** | Integrator | Bridges depreciation ↔ investment loop |
| **Liquid Funds (L)** | Integrator | Bridges revenue ↔ spending ↔ debt issuance |
| **Total Debt (D)** | Integrator | Bridges loan-taking ↔ repayment ↔ interest drain |
| **ESP** | Integrator | Bridges degradation ↔ regeneration ↔ AES cost |
| **GHG Atmospheric** | Integrator | Bridges emission ↔ absorption ↔ temperature |
| **Persistent Pollution (PPOL)** | Integrator | Bridges generation ↔ assimilation |

### How State-Gating Works at Runtime
At each RK4 k-stage evaluation:
1. Stock values are **frozen** at their current level (from previous step or intermediate RK4 stage).
2. Sectors compute derivatives using these frozen values as inputs.
3. The CentralRegistrar resolves constraints using frozen stock values + current demands.
4. Derivatives are finalized and returned to the RK4 integrator.
5. Stocks are updated **only** at the completion of the full RK4 step ($y_{n+1} = y_n + \frac{h}{6}(k_1 + 2k_2 + 2k_3 + k_4)$).

This guarantees that no circular algebraic dependency can form — every feedback loop is buffered by at least one time step of integration.

## IV. The $dt$ Resolution — Multi-Rate Integration

### The Constraint
The 1/512 year timestep (~0.00195 year, ~17 hours) is required when Finance, Hydrology, and Climate modules are all active and creating stiff interlinked equations.

### The Architecture
PyWorldX uses the existing **multi-rate scheduler** with configurable `master_dt`:
*   `master_dt` is set via `ModelConfig` (already exists).
*   For v2.0 with Finance active: `master_dt = 1/64` or `1/256`.
*   For v2.2 with Finance + Climate + Hydrology: `master_dt = 1/512`.
*   Individual sectors can request **integer sub-stepping ratios** (e.g., 4:1) for sectors that need finer resolution than `master_dt`.

### Stiffness Handling
The bounded $\phi(\text{MaintenanceRatio})$ function (capped at 2.0–4.0× baseline) combined with the 1/512 $dt$ handles numerical stiffness natively. The RK4 solver digests exponential depreciation shocks step-by-step without numerical explosion. **No implicit solver or adaptive stepping is required** at this resolution.

## V. The WILIAM-Finance Merge — Physical-to-Financial Bridge

The WILIAM economy adapter (Cobb-Douglas with military drag) merges with the new FinanceSector to create a unified economic layer.

### Physical → Financial Linkage
```
Revenue (TV) = Q × p          (endogenous market price)
Total Cost (TC) = μ×K + σ×R + ω×L   (maintenance + resource + labor)
Profit = TV - TC              → flows into Liquid Funds as inflow
```

### Financial → Physical Linkage (The Depreciation-Debt Spiral)
```
150% ceiling breached
  → Loan Availability = 0
  → Liquid Funds frozen
  → Actual Maintenance < Required Maintenance
  → MaintenanceRatio < 1.0
  → φ(MaintenanceRatio) exponential spike (bounded 2.0-4.0×)
  → Physical depreciation accelerates
  → Collateral value drops
  → Financial Resilience worsens
  → (positive feedback loop, buffered by State-Gating)
```

### Loop Safety
All three critical financial variables (IC, $L$, $D$) are **Stocks/Integrators**, not auxiliary variables. Their values update based on rates of change from the previous step. The 1/512 $dt$ CentralRegistrar resolves financial constraints before sectors finalize derivatives.

---
*Sources: q47 (Energy Sector Architecture), q49 (Multi-Node Regional Scaling), q52 (CentralRegistrar Mediator), q53 (WILIAM Finance Merge), q54 (Non-Linear Depreciation Stiffness)*
