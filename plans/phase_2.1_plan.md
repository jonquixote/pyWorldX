# Phase 2.1 — Society & Uncertainty Layer

**Date:** 2026-04-14  
**Goal:** Add social dynamics, policy resistance, and full uncertainty quantification  
**Duration:** 4-6 weeks  
**Scope:** 4 tasks — Change Resistance, Hedonic Ratchet, 1850 Spin-Up, Full Uncertainty Decomposition  

---

## Rationale

Phase 2 adds the biophysical detail (SEIR, Regional, Climate, Human Capital, Phosphorus, ESP). Phase 2.1 adds the social dynamics that determine whether the model's agents can respond to crises, and the uncertainty quantification that makes forecasts useful for decision-making. These are the last pieces before the model is "complete" in the v2 sense.

---

## Task 1: Change Resistance Layer (Policy Adoption with Social Inertia)

**Status:** ❌ Not implemented  
**Source:** Notebook Q07  
**Effort:** 1-2 weeks  

### What It Is

Policy changes don't take effect instantly. They pass through a Change Resistance filter:

```
CA = 1 - Change Resistance
d(Policy_applied)/dt = ((Policy_proposed × CA) - Policy_applied) / Social_Adjustment_Delay
```

**Social Adjustment Delay:** 10-30 years (generational), shortened by biophysical crisis signals.

**Change Resistance drivers (from Q07):**
- **Political Truth Literacy (PTL):** LTQ (~8%) + DTQ (Democratic Truth Quotient)
- **Life Form Goal Alignment (LGA):** ≈ 28% current (Corporate Dominance ~90%, Common Good Corp ~20%)
- **Dueling Loops:** Rationality vs. Degeneration; "false memes" can be infinitely scaled while truth bounded at 1.0

**Biophysical crisis signals that accelerate adoption:**
- PPOLX saturation → public awareness rises
- FPC below subsistence → "Social Tension" multiplier accelerates adoption
- EROEI decline + debt-to-GDP → growth paradigm loses legitimacy → Dominance_Corp decreases

### Implementation

This integrates with the existing policy wiring (Phase 0 Task 1). Instead of policies taking effect immediately at `t_start`, they pass through the Change Resistance SMOOTH filter.

**Files Modified:**
- `pyworldx/scenarios/scenario.py` — Extend PolicyEvent to include Change Resistance filtering
- `pyworldx/core/engine.py` — Change Resistance state variable, biophysical crisis signal inputs
- `pyworldx/observability/manifest.py` — Record Change Acceptance in provenance

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_change_acceptance_filters_policy` | Policy_proposed × CA → Policy_applied with delay |
| 2 | `test_social_adjustment_delay_10_30_years` | Policy takes 10-30 years to fully take effect |
| 3 | `test_crisis_signals_accelerate_adoption` | FPC subsistence → Social Tension → shorter delay |
| 4 | `test_ptl_low_value` | Political Truth Literacy defaults to ~8% |
| 5 | `test_lga_current_value` | Life Form Goal Alignment defaults to ~28% |
| 6 | `test_dueling_loops` | False memes scale infinitely, truth bounded at 1.0 |
| 7 | `test_policy_never_fully_adopted_with_low_ca` | Low Change Acceptance → policy never reaches full effect |
| 8 | `test_change_resistance_in_engine` | End-to-end: policy adoption filtered through Change Resistance |

### Acceptance Criteria

- [ ] Change Resistance state variable in engine
- [ ] Policy adoption filtered through CA SMOOTH filter
- [ ] Social Adjustment Delay 10-30 years, crisis-responsive
- [ ] PTL, LGA, Dueling Loops implemented
- [ ] Biophysical crisis signals accelerate adoption
- [ ] All 8 tests pass
- [ ] All previous tests still pass

---

## Task 2: Hedonic Ratchet (Desired Standard of Living Under Scarcity)

**Status:** ❌ Not implemented  
**Source:** Notebook q45  
**Effort:** 1 week  

### What It Is

Human expectations adapt upwards via income averaging delay. Society refuses to scale back consumption.

```
Desired_Standard = Rolling_Average(Actual_Income, averaging_time)
Social_Tension = f(Actual_Income / Desired_Standard)
```

**Key dynamics (from q45):**
- "Progress reinforcing loop" — if people feel standard of living is continually improving, social tension falls
- If progress merely stagnates (even at high absolute wealth), massive social tension generated
- "More is always better" paradigm → unchecked industrial feedback loop drives exponential demand
- Consumption only choked off at 65% Energy Ceiling

### Implementation

**Files Created/Modified:**
- `pyworldx/sectors/hedonic_ratchet.py` — New: Desired Standard of Living, Social Tension
- `pyworldx/sectors/capital.py` — Connect: Social Tension → consumption behavior
- `pyworldx/sectors/welfare.py` — Extend: HWI includes Social Tension penalty

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_desired_standard_adapts_upwards` | Rolling average of income creates ratchet effect |
| 2 | `test_social_tension_when_progress_stagnates` | Stagnation at high wealth generates tension |
| 3 | `test_unchecked_industrial_feedback` | Demand for growth persists despite resource scarcity |
| 4 | `test_65_percent_ceiling_chokes_consumption` | Only Energy Ceiling stops consumption growth |
| 5 | `test_hedonic_ratchet_in_engine` | End-to-end: ratchet affects consumption trajectory |
| 6 | `test_hwi_includes_social_tension` | HWI penalized by Social Tension |

### Acceptance Criteria

- [ ] Desired Standard of Living with income averaging delay
- [ ] Social Tension generated by progress stagnation
- [ ] Unchecked industrial feedback loop
- [ ] 65% Energy Ceiling is the only consumption limiter
- [ ] All 6 tests pass
- [ ] All previous tests still pass

---

## Task 3: 1850 Spin-Up Initialization

**Status:** ❌ Not implemented (t_start from ModelConfig, typically 1900)  
**Source:** Notebook Q56  
**Effort:** 1 week  

### What It Is

Run the model from 1850 (not 1900) to let 100+ year delays naturally settle before the 20th-century exponential boom.

**Key decisions from Q56:**
- **Free-run unconstrained from 1850.** No forcing functions. No overriding endogenous feedback with historical time-series data.
- Manually set initial stocks/fluxes at t=1850 to be thermodynamically/biophysically balanced.
- 50-year burn-in lets 100+ year delays (carbon cycle, persistent pollution, heavy infrastructure) naturally settle.
- **Empirical data used ONLY post-run** for optimization penalties (L²[0,T], ROC-Value). Never dynamically force state variables during run.

### Implementation

**Files Modified:**
- `pyworldx/config/model_config.py` — Add `spin_up_start: float | None = None` (default: 1850.0)
- `pyworldx/core/engine.py` — If spin_up_start set, run from spin_up_start to t_start, discard spin-up trajectories, keep final state as initial conditions
- `pyworldx/presets.py` — Update presets with spin_up_start=1850

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_spin_up_runs_from_1850` | Engine runs from 1850, discards spin-up, starts validation at 1900 |
| 2 | `test_no_forcing_functions` | Spin-up is free-run, no empirical overrides |
| 3 | `test_100_year_delays_settle` | DELAY3 stocks (pollution, carbon) reach equilibrium by 1900 |
| 4 | `test_spin_up_initial_state_balanced` | Stocks/fluxes thermodynamically balanced at t=1850 |
| 5 | `test_validation_uses_only_post_spin_up` | NRMSD computed on 1900-2023, not 1850-2023 |
| 6 | `test_backward_compatible_no_spin_up` | Without spin_up_start, behavior identical to Phase 2 |

### Acceptance Criteria

- [ ] Engine supports spin_up_start configuration
- [ ] Free-run from 1850, no forcing functions
- [ ] Spin-up trajectories discarded, final state used as initial conditions
- [ ] Validation runs on 1900-2023 only
- [ ] All 6 tests pass
- [ ] All previous tests still pass

---

## Task 4: Full Uncertainty Decomposition

**Status:** ⚠️ Simplified (parameter-only attribution)  
**Source:** Spec Section 10.8, Notebook q20  
**Effort:** 1-2 weeks  

### What It Is

The ensemble layer currently attributes all variance to parameter perturbations. Full decomposition requires:

- **Parameter uncertainty:** perturbed parameter values
- **Scenario uncertainty:** different scenario configurations
- **Exogenous input uncertainty:** perturbed external forcing series
- **Initial condition uncertainty:** perturbed initial stocks
- **Structural uncertainty:** different model configurations (e.g., with/without FinanceSector)

### Implementation

**Files Modified:**
- `pyworldx/forecasting/ensemble.py` — Extend `EnsembleSpec` to tag each member with uncertainty source
- `pyworldx/forecasting/uncertainty.py` — Implement full variance decomposition
- `pyworldx/forecasting/summaries.py` — Per-source summary statistics

### Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_parameter_uncertainty_tagged` | Parameter perturbation members tagged as PARAMETER |
| 2 | `test_scenario_uncertainty_tagged` | Scenario difference members tagged as SCENARIO |
| 3 | `test_exogenous_uncertainty_tagged` | Exogenous perturbation members tagged as EXOGENOUS_INPUT |
| 4 | `test_initial_condition_uncertainty_tagged` | IC perturbation members tagged as INITIAL_CONDITION |
| 5 | `test_variance_decomposition_sums_to_total` | Sum of per-source variances ≈ total variance |
| 6 | `test_structural_uncertainty` | Different model configs produce spread |
| 7 | `test_decomposition_report` | Full uncertainty decomposition report generated |

### Acceptance Criteria

- [ ] Ensemble members tagged with uncertainty source
- [ ] Variance decomposition computes per-source contribution
- [ ] Per-source summary statistics (mean, median, percentiles)
- [ ] Structural uncertainty supported (different model configs)
- [ ] All 7 tests pass
- [ ] All previous tests still pass

---

## Task Dependencies

```
Task 1 (Change Resistance) ──── needs Phase 0 Task 1 (Policy wiring)
Task 2 (Hedonic Ratchet) ────── needs Phase 1 Task 1 (CentralRegistrar for 65% ceiling)
Task 3 (1850 Spin-Up) ───────── independent of other Phase 2.1 tasks
Task 4 (Uncertainty Decomposition) ── independent

All 4 tasks can run in parallel. No dependencies between them.
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Change Resistance parameters (LTQ, LGA) are speculative | High | Low — document as sensitivity ranges, not point estimates | Use ranges from literature. Make parameters configurable. |
| Hedonic Ratchet adds another feedback that could destabilize model | Medium | Medium — more feedback loops = harder to calibrate | Run ensemble to characterize behavior. Document expected dynamics. |
| 1850 spin-up doubles computational cost | Certain | Low — spin-up is one-time initialization, not ensemble | Acceptable for validation runs. For ensemble, use cached 1900 initial state. |
| Uncertainty decomposition requires many more ensemble members | Medium | Medium — 5 sources × 100 members = 500 runs | Use Sobol sampling for efficiency. Document minimum member counts. |

---

## Definition of Done

- [ ] All 4 tasks completed
- [ ] All new tests pass (8 + 6 + 6 + 7 = 27 tests)
- [ ] All Phase 0 + 0.5 + 1 + 2 tests still pass (620 tests)
- [ ] Total test count: 620 + 27 = 647 tests
- [ ] mypy strict passes on all modified files
- [ ] ruff check passes on all modified files
- [ ] Policy adoption filtered through Change Resistance with biophysical crisis acceleration
- [ ] Hedonic Ratchet produces social tension when progress stagnates
- [ ] 1850 spin-up runs free-run, discards spin-up trajectories, validates from 1900
- [ ] Full uncertainty decomposition reports per-source variance contribution

---

## Beyond Phase 2.1

After Phase 2.1, the following items are explicitly **deferred beyond v2** (per spec Section 19):

- 12-region spatial disaggregation (beyond the N-region architecture of Phase 2 Task 2)
- Trade and migration flow networks
- Heterogeneous agents / ABM scheduler
- Tipping-point SDE modules and cascade propagation
- Endogenous Wright's-law technology learning curves
- NeuralODE or other learned surrogate registry
- MCMC / SMC Bayesian calibration
- Real-time assimilation via Ensemble Kalman Filter

These are v3+ items. The v2 architecture (Phase 0 → Phase 2.1) provides the hooks for all of them but does not implement them.
