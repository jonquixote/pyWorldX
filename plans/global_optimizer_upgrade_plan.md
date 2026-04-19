# Global Optimizer Upgrade Plan

## Goal
Prevent the deterministic calibration pipeline from getting trapped in sub-optimal local minima. The highly nonlinear 5-sector ODE system of pyWorldX has a rugged parameter space, making the current Nelder-Mead simplex optimizer highly susceptible to early convergence. We will inject a global Bayesian Optimization pass prior to Nelder-Mead.

## Proposed Changes

### Dependencies
- Add `optuna` via Poetry (`poetry add optuna`). Bayesian optimization is selected over Differential Evolution to strictly minimize the number of expensive ODE integrations.

### `pyworldx/calibration/`
#### [MODIFY] `pipeline.py`
- Implement a new `_bayesian_optimize(n_trials: int = 100, timeout: int = 600)` function utilizing `optuna.create_study()`. 
  - **Sampler Specification:** Explicitly configure the study to use `sampler=optuna.samplers.TPESampler(seed=42)` to ensure reproducibility and guard against future default changes.
  - **Trial Pruning / Timeout:** Pass both `n_trials` and `timeout` to the optimize call to provide a sensible wall-clock ceiling.
- Update `run_calibration_pipeline()`:
  - **Step 1:** Profile likelihood (existing).
  - **Step 2:** Morris screening (existing).
  - **[NEW] Step 3:** Global Optimization. Run the `_bayesian_optimize()` pass over the screened parameters.
  - **Step 4:** Local Fine-Tuning. Take the best parameters discovered by Optuna and feed them as the `initial_params` into the existing `_nelder_mead_optimize()` function for final simplex tightening.

## Verification Plan
### Automated Tests
- Mock the objective function and assert that `_bayesian_optimize()` successfully creates an Optuna study, runs $N$ trials, and returns the best parameters.
- Verify the hand-off in `run_calibration_pipeline()`: assert that Nelder-Mead's `initial_params` are strictly equal to the output of the Bayesian pass.
- **Bounds Respect Test:** Assert that `_bayesian_optimize()` strictly respects parameter bounds, ensuring no trial proposes a value outside the `[lower, upper]` bounds of the screened parameter space.

### Manual Verification
- Run a full empirical calibration on the historical dataset and verify that the final composite NRMSD score is **not higher** (i.e., less than or equal to) the score achieved using the Nelder-Mead-only baseline, confirming we are either improving the fit or verifying we were already near-optimal.
