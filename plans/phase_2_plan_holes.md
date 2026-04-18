# Phase 2 Remediation Plan: Structural Holes Analysis

This document details critical structural holes found in the `phase_2_remediation_plan.md` (v2), providing a deep explanation of each oversight and specific instructions on how to patch both the plan and the underlying codebase.

*(Note: Holes 2, 3, 10, and 11 from the previous analysis were formally retracted after deeper thermodynamic and macroeconomic review. They have been excised from this document to maintain absolute fidelity to the World3 structural spec).*

---

## 1. The Missing Fossil Energy Capital Drain

### Deep Explanation
Task B10 of the remediation plan correctly addresses "Capital Stealing" by observing that the new Phase 2 energy sectors require capital investment, which must be subtracted from the main economy's Industrial Capital (`IC`) accumulation to maintain mass/value conservation. The plan instructs `capital.py` to subtract `tech_sector_investment` and `sustainable_sector_investment`. 

However, the plan **completely misses `energy_fossil.py`**. The fossil sector *also* internally calculates an endogenous investment drain:
```python
# pyworldx/sectors/energy_fossil.py:79
investment = io * 0.05 * profitability  # 5% of IO * profitability
```
Because the plan omits exposing this fossil investment and subtracting it in `capital.py`, the simulation will continue to violate capital conservation. The engine will literally build fossil fuel infrastructure for free out of thin air.

### How to fix the Plan
Update **Task B10** to include `energy_fossil.py`. The task should explicitly mention exposing `fossil_sector_investment` and updating `capital.py` to read and subtract all three energy sector investments.

### How to fix the Code
1. **In `energy_fossil.py`**: Add `"fossil_sector_investment"` to the `declares_writes()` list. In the `compute()` function, add `"fossil_sector_investment": Quantity(investment, "capital_units")` to the returned dictionary.
2. **In `capital.py`**: Add `"fossil_sector_investment"` to `declares_reads()`.
3. **In `capital.py` `compute()`**: 
```python
tech_inv = inputs.get("tech_sector_investment", Quantity(0, "capital_units")).magnitude
sust_inv = inputs.get("sustainable_sector_investment", Quantity(0, "capital_units")).magnitude
fossil_inv = inputs.get("fossil_sector_investment", Quantity(0, "capital_units")).magnitude

# Subtract all energy investments from the available industrial capital pool
ic_investment = max((io * fioai) - tech_inv - sust_inv - fossil_inv, 0.0)
```

---

## 2. The Absolute vs. Relative Time Scale Schizophrenia

### Deep Explanation
There is a fatal contradiction in how the simulation handles time `t`. In `v2_scenarios.py`, policies use absolute calendar years (e.g., `t_start=2020.0` or `2030.0`). However, in `runner.py`, the engine is instantiated using relative time: `t_start=float(scenario.start_year - 1900)` (which equals `0.0`). This means the internal `t` runs from 0 to 200. Because the policy applier compares this relative `t` against an absolute `t_start` of 2020, the event will **NEVER** trigger because `t` maxes out at 200.

Conversely, your remediation plan's test fixtures (like Task 0.2, Task A2, Task A5) instantiate the engine with absolute time `t_start=1900.0`. But the core integration tests like `test_phase1_integration.py` use `t_start=0.0`. The entire architecture is schizophrenic about time scales.

### How to fix the Plan
Add a new task (e.g., **Task A0**) to standardize the time scale across the entire engine, scenarios, and test suite.

### How to fix the Code
Pick one time scale globally. Absolute calendar years (1900 to 2100) are recommended for clarity:
1. **In `runner.py`**: Remove the `- 1900` subtraction when instantiating the Engine.
2. **In `test_phase1_integration.py`**: Update to use `t_start=1900.0, t_end=2100.0`.
3. **In `scenario.py`**: Ensure all built-in scenarios (like `pollution_control_push`) use absolute calendar years (e.g., `t_start=1950.0` instead of `50.0`).

---

## 3. The Scenario RAMP Math Bug (Task E7)

### Deep Explanation
In Task E7, the plan dictates adding policy events using `PolicyShape.RAMP` and specifies: 
`rate=-0.9 / 40.0, # relative rate; applier multiplies by baseline`

This fundamentally misunderstands how `PolicyEvent.apply()` works in `scenario.py`. The actual source code calculates the RAMP as:
`return baseline_value + r * elapsed`
It does **not** multiply by the baseline. If you use a rate of `-0.0225` (-0.9/40) on `fossil_output` (which operates on a scale of ~1e11), the RAMP will subtract exactly 0.0225 units per year from 100,000,000,000. It will do absolutely nothing.

### How to fix the Plan
Update **Task E7** to either specify absolute magnitude rates, or require modifying the `PolicyEvent` engine to support multiplicative rates.

### How to fix the Code
If you want to support multiplicative/relative RAMP rates (which is much safer for dynamic variables), modify `pyworldx/scenarios/scenario.py`'s `PolicyEvent.apply()` method. Add a new `is_relative: bool = False` flag to the `PolicyEvent` dataclass.
```python
if self.shape == PolicyShape.RAMP:
    r = self.rate if self.rate is not None else 0.0
    t_end = self.t_end if self.t_end is not None else t
    elapsed = min(t - self.t_start, t_end - self.t_start)
    if getattr(self, "is_relative", False):
        return baseline_value * (1.0 + r * elapsed)
    return baseline_value + r * elapsed
```

---

## 4. The SEIR Aging Disconnect (Task D2)

### Deep Explanation
In Task D2, you instruct `seir.py` to stop adding deaths to its own internal cohorts, and instead export a scalar death rate to `population.py` to prevent double-counting deaths. 

However, you missed a much larger structural disconnect: **`seir.py` has no demographic aging mechanism!** 
In `population.py`, people age up from `P1` (0-14) to `P2` (15-44) to `P3` and `P4` over time. In `seir.py`, the disease matrix operates its own independent `S/E/I/R` stock ODEs for these four cohorts. But nobody ever ages between them. Furthermore, all births are dumped exclusively into the `C1` cohort (`births = birth_rate * pop if i == 0 else 0.0`). 

Over a 200-year simulation, the working-age cohorts (`C2` and `C3`) in the SEIR module will only experience death, with nobody aging into them. They will hit exactly zero. Since these are the exact cohorts used to calculate the `labor_force_multiplier`, your labor force will artificially collapse to zero regardless of disease dynamics, completely breaking `capital.py` production.

### How to fix the Plan
Update **Task D2** to resolve the aging disconnect. The `SEIRModule` cannot maintain parallel absolute population stocks without mirroring the aging fluxes from `population.py`.

### How to fix the Code
Instead of absolute persons in `seir.py`, modify `SEIRModule` to track **fractions** (dimensionless proportions of each cohort that are Susceptible, Exposed, Infected, Recovered). 
1. **In `seir.py`**: Change `S_C1`, `E_C1`, etc., from absolute persons to fractions (summing to 1.0 per cohort). 
2. In the `compute()` step, multiply these fractions by the true population counts (`P1`, `P2`, `P3`, `P4`) read from `population.py` to get absolute numbers for infection force calculation.
3. Because they are fractions, the complex aging dynamics (people aging in and out of cohorts) are safely handled by `population.py`, while `seir.py` purely calculates disease state transitions.

---

## 5. The Minsky Moment Impossibility

### Deep Explanation
In `v2_scenarios.py`, the `minsky_moment` scenario tests financial contagion by overriding `finance.interest_rate` to accelerate debt accumulation. However, looking at the debt ODE in `finance.py`:
```python
loan_taking_rate = max(-L, 0.0) * gov_mult
dD_g = loan_taking_rate - D_g / max(self.debt_repayment_time, 1.0)
```
The model **ONLY** takes out loans when the global liquid funds (`L`) drop below zero. If the economy is profitable, `L` grows linearly, `loan_taking_rate` is strictly zero, and existing debt just amortizes to zero. 

It is impossible to accumulate debt during economic growth in pyWorldX. Real economies use debt to finance investment (leveraging). Because `finance.py` treats debt solely as an emergency bankruptcy overdraft, the `minsky_moment` scenario is structurally impossible to trigger through interest rates alone; debt will always remain near zero unless the physical economy collapses first (which defeats the purpose of testing a *financial* collapse).

### How to fix the Plan
Add a new task to update the debt ODEs in `finance.py` before attempting the Minsky Moment scenario.

### How to fix the Code
Modify `finance.py` to take out loans proportional to physical investment demand, even when `L > 0`.
```python
# Borrowing to finance growth, not just to cover deficits
target_investment = profit * self.reinvestment_fraction * optimism_multiplier
actual_investment = min(L, target_investment)
loan_taking_rate = max(target_investment - L, 0.0) * gov_mult
```

---

## 6. The Ability-to-Pay Structural Disconnect (Task A3)

### Deep Explanation
Task A3 correctly identifies that the `CentralRegistrar` always falls back to equal-scaling because no sector writes `liquid_funds_{sector_name}`. The plan "fixes" this by just formalizing the fallback behavior. 

This formally breaks the core architectural requirement of the `CentralRegistrar` (from Q52), which explicitly states: *"NOT equal scaling — Ability to Pay... determine access."* 

The real bug isn't that sectors forgot to export their bank balances; the bug is that `pyWorldX` (and World3) is a *macroeconomic* model with a single global capital pool. `finance.py` rightly simulates a single global `liquid_funds` (`L`). The `CentralRegistrar` was written assuming a *microeconomic* model where each sector has its own wallet (`liquid_funds_{sector}`). Fixing this by permanently disabling Ability-to-Pay is a feature regression. 

### How to fix the Plan
Update **Task A3** to correctly map the macro-economic `finance.py` to the `CentralRegistrar`. Do not accept the "demand-weighted fallback" as the final solution.

### How to fix the Code
Since `liquid_funds` is global, `CentralRegistrar` should use the global `L` to determine overall system financial resilience, but allocate specifically based on `security_value` (strategic priority) rather than individual sector wallets. Alternatively, if sectors *must* compete based on wallets, `finance.py` must be upgraded to allocate the global `L` into sectoral accounts (`L_agri`, `L_cap`, etc.) based on their respective revenues.

---

## 7. The Dissipative Trade Phantom Loop

### Deep Explanation
In `regional_trade.py`, you implemented a transport loss mechanism for food moving between regions (`received_trade = trade_flows * (1.0 - self.transport_loss)`). It successfully subtracts 5% from the regional receipts.

However, `regional_trade.py` never exports a `transport_loss` or `food_dissipated` variable to the engine! Because the global `agriculture.py` sector (which holds the master `food` stock) is completely blind to this calculation, the 5% of food that "rots in transit" is never actually deducted from the global food supply. Mass conservation is violated; the simulation models the trade friction, but magically refunds the lost food back into existence.

### How to fix the Plan
Add a new task dictating that `regional_trade.py` must export the total food loss, and `agriculture.py` must deduct it.

### How to fix the Code
1. **In `regional_trade.py`**: Calculate `total_food_loss = (trade_flows * self.transport_loss).sum()`. Add `"trade_food_loss": Quantity(total_food_loss, "food_units")` to the return dictionary and `declares_writes()`.
2. **In `agriculture.py`**: Read `"trade_food_loss"` and subtract it from the total global food output or add it to the food consumption/decay terms.

---

## 8. The 65% Energy Ceiling Math Bug

### Deep Explanation
In `central_registrar.py`, the engine enforces a 65% energy ceiling (`_ENERGY_CEILING = 0.65`). The explicit design spec (and literature) defines this as: *"Society collapses if more than 65% of total industrial output is dedicated to energy extraction."*
However, look at how the `CentralRegistrar` actually applies this limit in code:
```python
total_supply_ej = total_supply_abstract * _EJ_SCALE
total_supply = total_supply_ej * self.energy_ceiling
ceiling_breached = total_demand > total_supply
```
The math is completely backwards! It multiplies the *Energy Supply* by 0.65. This means if the energy sectors produce 100 EJ, the Registrar artificially caps societal demand at 65 EJ and throws away the other 35 EJ. It restricts energy distribution, but completely fails to limit capital investment in energy (which is what the 65% ceiling actually means).

### How to fix the Plan
Add a new Task A6 to rewrite the ceiling logic in `central_registrar.py`.

### How to fix the Code
1. **In `central_registrar.py`**: Remove `total_supply = total_supply_ej * self.energy_ceiling`. The available supply is simply `total_supply_ej`.
2. To enforce the actual 65% capital ceiling, the Registrar must read the investment variables from the energy sectors (`fossil_sector_investment`, `tech_sector_investment`, `sustainable_sector_investment`) and compare their sum against total `industrial_output`. If the ratio exceeds 0.65, *then* the ceiling is breached and a collapse multiplier should trigger.

---

## 9. The Free Technology "Magic" Bug

### Deep Explanation
The `adaptive_technology.py` sector calculates the fractional cost of R&D (`tech_cost_fraction`) along with three performance multipliers (`resource_tech_mult`, `pollution_tech_mult`, `agriculture_tech_mult`) and exports all four variables.

A global codebase search reveals that **not a single one of these variables is read by any other sector**. 
1. `capital.py` ignores `tech_cost_fraction`, meaning the massive investments in R&D are completely free and don't drain the physical economy.
2. `resources.py` and `pollution.py` hardcode their multipliers to `1.0`, entirely ignoring the technological breakthroughs.

This sector is an isolated ghost module that calculates a bunch of numbers and throws them into the void.

### How to fix the Plan
Add a new task explicitly dictating the engine wiring for `adaptive_technology.py`. 

### How to fix the Code
1. **In `capital.py`**: Read `tech_cost_fraction` and subtract it from the `ic_investment` pool so that technology actually costs capital to develop.
2. **In `resources.py`**: Read `resource_tech_mult` and use it to dynamically alter `NRUF` (Non-Renewable Usage Factor) instead of hardcoding it to `1.0`.
3. **In `pollution.py`**: Read `pollution_tech_mult` and use it to scale down pollution generation from industrial/agricultural sources.

---

## 10. The Toxin-Health Isolation Bug

### Deep Explanation
In `pollution_toxins.py`, the sector runs a complex 111.8-year 3rd-order cascaded delay ODE to track the buildup of endocrine disruptors and persistent micro-toxins. It exports `toxin_health_multiplier` and `toxin_fertility_multiplier`.

However, a codebase search reveals that **`population.py` completely ignores these variables.** It never declares them in `declares_reads()` and never applies them to the `death_rate` or `birth_rate` ODEs. Just like the technology module, the micro-toxin module is totally isolated. The simulation models the slow buildup of lethal toxins, but nobody ever dies from them.

### How to fix the Plan
Add a new task explicitly wiring `pollution_toxins.py` to `population.py`.

### How to fix the Code
1. **In `population.py` `declares_reads()`**: Add `"toxin_health_multiplier"` and `"toxin_fertility_multiplier"`.
2. **In `population.py` `compute()`**: 
Multiply the baseline `death_rate` by `toxin_health_multiplier`. 
Multiply the baseline `birth_rate` by `toxin_fertility_multiplier`.

---

## 11. The Technology Metals Demand Wiring Bug

### Deep Explanation
In `energy_technology.py`, the code calculates and explicitly exports `tech_metals_demand` (which is proportional to installed technology capital). 
However, Task C1 in your remediation plan instructs `resources.py` to calculate the extraction rate from `technology_capital` flow directly. This explicitly tells `resources.py` to ignore the `tech_metals_demand` signal already exported by the technology sector, resulting in duplicated logic and a broken wiring spec.

### How to fix the Plan
Update **Task C1** to explicitly instruct `resources.py` to declare a read on `"tech_metals_demand"` from the shared state, and use that signal to drive the extraction rate of technology metals.

### How to fix the Code
1. **In `resources.py` `declares_reads()`**: Add `"tech_metals_demand"`.
2. **In `resources.py` `compute()`**: Use the `tech_metals_demand` directly to compute the cumulative extraction rate, instead of attempting to recalculate it from `technology_capital`.

---

## 12. The Trapped Capital Destruction Bug

### Deep Explanation
In `energy_technology.py`, when technology metals are scarce, the sector calculates `trapped_capital = investment * (1.0 - metals_avail)`. It then subtracts this trapped capital from its own effective investment (`effective_investment = investment - trapped_capital`).

However, in **Task B10**, you instructed `capital.py` to subtract the FULL `tech_sector_investment` (`investment`) from its Industrial Capital pool. 
Because the trapped portion is subtracted from `IC` but never added to `technology_capital`, the capital simply evaporates from the simulation. This causes a massive violation of mass/value conservation. The simulation will physically destroy capital into the void.

### How to fix the Plan
Add a task (e.g., Task B12) to handle the conservation of `trapped_capital` exported by `energy_technology.py`.

### How to fix the Code
1. **In `capital.py` `declares_reads()`**: Add `"trapped_capital"`.
2. **In `capital.py` `compute()`**: Read `"trapped_capital"` and add it back to the `ic_investment` pool (essentially refunding the economy for the trapped capital that couldn't be deployed). Alternatively, `finance.py` could read it and register it as a direct financial write-off (loss) against global Liquid Funds (`L`).

---

## 13. The Ecosystem Temperature Scale Confusion Bug

### Deep Explanation
In `ecosystem_services.py`, the ecosystem regeneration rate is determined by `temp_anomaly`, which is the °C deviation above the pre-industrial baseline (where pre-industrial is 0.0°C). 
However, the code sets the constants `T_opt = 15.0` (optimal temperature) and `T_crit = 35.0` (critical temperature). 

These are clearly **absolute temperatures** (°C) applied to a relative anomaly variable! An anomaly of +15.0°C would mean the global absolute temperature is 30°C. As the code is currently written, ecosystem regeneration will actually *increase* as the Earth warms up, peaking only when the oceans are boiling. This is a massive thermodynamic scale error.

### How to fix the Plan
Add a new task dictating the correction of the temperature scales in `ecosystem_services.py`.

### How to fix the Code
1. **In `ecosystem_services.py`**: Update the constants so they are evaluated on an anomaly scale. For example, `T_opt = 0.0` (optimal is pre-industrial) and `T_crit = 4.0` (ecosystem collapse at +4°C warming).

---

## 14. The Population Time-Scale Hardcoding Cascade

### Deep Explanation
This is a direct and fatal downstream consequence of **Hole 2** (Time Scale Schizophrenia) that the remediation plan completely misses. In `population.py`, there are two hardcoded time-scale conversions:

```python
# Line 213:
iphst_sim = _IPHST - 1900        # Converts calendar 1940 → relative 40

# Line 280:
calendar_year = t + 1900         # Converts relative t → calendar year
```

These lines **assume** that `t` is in relative time (0–200). If the remediation plan's Task A0 migrates the engine to absolute calendar years (`t_start=1900, t_end=2100`), both conversions will double-apply the 1900 offset:

1. **IPHST**: `iphst_sim` remains 40, but now `t` starts at 1900. The check `if t < iphst_sim` evaluates `if 1900 < 40` → always `False`. The LMHS2 (post-1940 health services table) will be applied from 1900 onwards, giving the pre-industrial population unrealistically high life expectancies from year zero.

2. **ZPGT/FCEST/PET**: `calendar_year = 1900 + 1900 = 3800`. These thresholds are set to 4000 (inactive in the base run). Under absolute time, they would accidentally trigger at `t = 2100` because `2100 + 1900 = 4000`. This would force zero population growth and maximum fertility control effectiveness in the final simulation year — an artificial population ceiling that appears as an inexplicable demographic cliff.

The remediation plan instructs standardizing `t` to absolute years (Hole 2) but **never mentions updating `population.py`'s internal time conversions**. The sector will silently produce wrong demographic dynamics.

### How to fix the Plan
Expand **Task A0** (time scale standardization) to explicitly audit and update every sector that performs internal `t ± 1900` conversions. `population.py` is the critical case.

### How to fix the Code
1. **In `population.py`**: Remove both hardcoded conversions:
   - Replace `iphst_sim = _IPHST - 1900` with direct comparison: `if t < _IPHST:` (since `t` is now absolute calendar year 1940).
   - Replace `calendar_year = t + 1900` with `calendar_year = t` (since `t` is now the calendar year directly).
2. Verify that `_ZPGT = 4000`, `_FCEST = 4000`, and `_PET = 4000` remain correctly inactive (since `t` maxes at 2100, which is less than 4000, they will never trigger — correct behavior).

---

## 15. The Duplicate Radiative Forcing Logic Bug

### Deep Explanation
In **Task C3**, your remediation plan instructs `climate.py` to read `C_atm` from the 5-stock carbon model (`pollution_ghg.py`), convert it to `co2_ppm`, and then calculate the greenhouse gas radiative forcing using `rf_ghg = 5.35 * math.log(...)`.

However, the 5-stock carbon model (`pollution_ghg.py`) **already** natively computes and exports `ghg_radiative_forcing` (Line 188: `rf = 5.35 * math.log(...)`). 

By having `climate.py` re-derive the radiative forcing from the carbon mass, the plan creates a duplicate thermodynamic calculation across two separate sectors. If the forcing constants are updated in one module but not the other, the engine will mathematically diverge. `pollution_ghg.py` should be the single source of truth for carbon thermodynamics.

### How to fix the Plan
Update **Task C3** so that `climate.py` reads the explicitly exported `ghg_radiative_forcing` signal directly from the central state, rather than reading `C_atm` to recalculate it.

### How to fix the Code
1. **In `climate.py` `declares_reads()`**: Add `"ghg_radiative_forcing"`.
2. **In `climate.py` `compute()`**: Remove the manual `co2` and `rf_ghg` logarithmic calculations. Directly use the input `ghg_radiative_forcing` in the Temperature ODE.
