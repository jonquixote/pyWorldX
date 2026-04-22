# Sobol Uncertainty Decomposition Plan

## Goal
Transform the ensemble forecasting system from a descriptive tool into a prescriptive decision engine by implementing mathematically rigorous Sobol variance decomposition. This will allow decision-makers to distinguish between epistemic uncertainty (parameter ignorance needing more research) and aleatory uncertainty (policy/scenario choices).

## Proposed Changes

### Dependencies
- Add `SALib` via Poetry (`poetry add SALib`) to handle Saltelli sampling and Sobol analysis.

### `pyworldx/forecasting/`
#### [MODIFY] `ensemble.py`
- Modify `EnsembleSpec` to flag when a Sobol analysis is requested (`run_sobol: bool = False`).
- Refactor the sampling front-end in `run_ensemble()`:
  - If `run_sobol` is True, bypass the native `numpy` random uniform samplers and instead use `SALib.sample.saltelli.sample()`.
  - **Sample Size Guard:** Add an explicit recommendation for base sample count `N=512`. Implement a warning log if $N \times (2D + 2) > 10,000$ to prevent accidentally launching 6-hour runs.
- Replace the fake `TODO` variance decomposition block at the end of `run_ensemble()`:
  - Feed the final model outputs back into `SALib.analyze.sobol.analyze()`.
  - Extract the First-Order ($S_1$) and Total-Order ($S_T$) indices.
  - **Variance Mapping Spec:** Partition the SALib `problem` dict's `names` list into three explicitly labeled groups (`parameter`, `scenario`, `initial_condition`). After analysis, aggregate the $S_1$ indices by group to correctly map the variance back to these buckets.

## Verification Plan
### Automated Tests
- Write a test using a known dummy objective function (e.g., the Ishigami function) plugged into the ensemble runner to assert that `SALib` correctly calculates the analytical Sobol indices.
- Ensure the ensemble runner correctly falls back to standard Monte Carlo sampling when `run_sobol=False`.
- **Sanity Check Test:** Assert that when `run_sobol=True`, the resulting first-order indices sum to at most 1.0 ($\sum S_1 \leq 1.0$) to catch malformed `problem` dicts before they produce silently wrong indices.
