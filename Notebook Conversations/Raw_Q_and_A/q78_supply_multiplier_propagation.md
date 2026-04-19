**Question:** In our pyWorldX model, when the CentralRegistrar enforces the 65% Energy Ceiling, it computes SupplyMultipliers as allocation divided by demand for each sector. How should these constrained energy supplies propagate through the economic system? Does reduced energy supply reduce production linearly, or are there threshold effects, priority chains, and cascading failures? How should the supply multiplier affect sector outputs?

---

Answer:
Answer:
In the pyWorldX architecture, constrained energy supplies do not propagate as a simple linear or
equal reduction across all sectors. Instead, when the CentralRegistrar enforces the **65% 
Thermodynamic Energy Ceiling**, it triggers a cascade of non-linear threshold effects, 
market-driven priority chains, and physical depreciation.

**1. Priority Chains and "Ability to Pay" Allocation**
The CentralRegistrar **does not enforce equal scaling** [1, 2]. Because pyWorldX models a 
monetized economy, the energy deficit generates an immediate endogenous price spike [3, 4]. The 
constrained energy is allocated based on **"Ability to Pay" (Liquid Funds) and "Security 
Value"** [1, 2].
*   Wealthy "core" regions and vital industrial/military capital can absorb these higher prices 
to secure their energy allocation [4]. 
*   Conversely, the demand from the "periphery" (e.g., the bottom 50% or 90%) is 
**mathematically modified to zero** because their disposable income falls below the new 
subsistence price [1, 4]. **Basic survival is not universally protected** [1].

**2. Impact on Sector Outputs via Production Functions**
The computed `SupplyMultipliers` (< 1.0) are broadcast back down to the sectors as a 
**"Production Scaler"** before they execute their derivative calculations [5, 6]. 
*   When supply is strictly less than demand, production is reduced [7].
*   Because sector outputs ($Q$) are calculated using a **Cobb-Douglas production function** ($Q
= q_k \cdot K^\alpha \cdot q_r \cdot R^\beta \cdot q_l \cdot L^{(1-\alpha-\beta)}$), the sudden 
restriction of physical resources and energy ($R$) drives an exponential, non-linear contraction
in industrial and agricultural output rather than a 1:1 linear decline [8].

**3. Cascading Failures and the Maintenance Gap**
The propagation of these multipliers creates severe systemic feedback loops:
*   **Agricultural Collapse:** Throttling energy to sectors like the HydrologicalSector 
restricts desalination and deep water pumping [9]. This immediately throttles water production, 
leading to food shortages and triggering the Death-Rate-from-Food Multiplier [9].
*   **Non-Linear Depreciation:** As energy costs spike and output contracts, the system's Liquid
Funds are exhausted [4, 10]. When loan availability hits the 150% Debt-to-GDP ceiling, the 
system can no longer fund required maintenance [10, 11]. This "Maintenance Gap" triggers a 
non-linear decay multiplier ($\phi$, bounded up to 4.0x) that causes the physical integrity of 
the capital base to exponentially collapse [12, 13].

**4. Engine Orchestration and Stability**
To avoid algebraic loops (where demand depends on supply which depends on demand), the 
CentralRegistrar operates as a **pre-derivative resolution pass** [14, 15]. At each RK4 sub-step
(specifically step 1b), the engine collects demands from a shared state, enforces the 65% 
ceiling, and resolves the multipliers [2]. The model allows for a **brief overshoot** of the 
energy ceiling due to system delays, which is smoothly corrected within a few RK4 sub-steps by 
utilizing a high-frequency **1/512 year timestep** ($dt$) to maintain numerical stability 
without crashing the solver [1, 16, 17].
