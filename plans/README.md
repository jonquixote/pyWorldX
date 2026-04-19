# pyWorldX Implementation Plans — Index

**Date:** 2026-04-14  

---

## Plan Overview

| Phase | Focus | Duration | Tasks | New Tests | Total Tests | Status |
|-------|-------|----------|-------|-----------|-------------|--------|
| **Phase 0** | Finish v1 (release gate checklist) | 3 weeks | 6 | 29 | 499 | ✅ Complete |
| **Phase 0.5** | v1 correctness fixes | 1-2 weeks | 3 | 17 | 516 | ✅ Complete |
| **Phase 1** | v2 core architecture | 6-8 weeks | 6 | 60 | 576 | ✅ Complete |
| **Phase 2** | v2.1 biophysical realism | 6-8 weeks | 7 (+3 prereq) | TBD | TBD | 📋 Plan complete — ready to implement |
| **Phase 2.1** | Society & uncertainty layer | 4-6 weeks | 4 | 27 | 647 | 🟡 Not started |

**Grand total completed:** 15 tasks, 106 new tests, 535 total tests — all passing.  
**Independent verification:** 3 subagents reviewed all 3 completed phases. **All tasks VERIFIED.**

---

## File Map

| File | Content |
|------|---------|
| [`phase_0_plan.md`](phase_0_plan.md) | Policy wiring, exogenous injection, canonical R-I-P vs PySD, World3-03 validation, connector cleanup, TAI→CAI→AI investment chain |
| [`phase_0.5_plan.md`](phase_0.5_plan.md) | Nonlinear depreciation, PPTD recalibration (20→111.8), FIOAA deduplication |
| [`phase_1_plan.md`](phase_1_plan.md) | CentralRegistrar, FinanceSector (merged WILIAM), Energy sector split, Pollution split, Gini matrix, v2 scenarios |
| [`phase_2_plan.md`](phase_2_plan.md) | SEIR module, Regional objects, Climate module, Human Capital, Phosphorus mass-balance, Ecosystem Services |
| [`phase_2.1_plan.md`](phase_2.1_plan.md) | Change Resistance, Hedonic Ratchet, 1850 spin-up, Full uncertainty decomposition |

---

## Dependency Graph

```
Phase 0 ✅ ──→ Phase 0.5 ✅ ──→ Phase 1 ✅ ──→ Phase 2 🟡 ──→ Phase 2.1 🟡
   │                │                │               │               │
   │                │                │               │               └─ Uncertainty quantification
   │                │                │               └─ Ecosystem Services, Phosphorus, Climate
   │                │                └─ Gini, v2 scenarios, Pollution split, Energy split
   │                └─ Nonlinear depreciation, PPTD, FIOAA
   └─ Policy + exogenous wiring, canonical test, validation, TAI chain
```

**Critical path:** Phase 0 → Phase 0.5 → Phase 1 → Phase 2 → Phase 2.1  
**Completed estimate:** ~20-27 weeks for all 5 phases (including Phase 2 + 2.1)

---

## Audit Trail

All plans have been audited against:
- **Actual codebase** — every file read and verified
- **Notebook conversations** — all 57 Q&A files cross-referenced
- **Spec v0.2.9.0** — section-by-section compliance checked
- **Independent subagent review** — 3 agents verified all 3 completed phases against source code

### Key Audit Findings Incorporated

| Phase | Finding | Fix Applied |
|-------|---------|-------------|
| Phase 0 | Policy hook placed AFTER sector compute (would have no effect) | Moved to BEFORE Phase 1 (sub-stepped sectors) |
| Phase 0 | Policy targets use dotted namespace not matching engine variables | Fixed to flat engine variable names |
| Phase 0 | Exogenous overrides use ontology names, not engine names | Added ENTITY_TO_ENGINE_MAP translation |
| Phase 0 | Canonical reference is self-referential (pyWorldX vs pyWorldX) | Rewrote generate_reference.py to use PySD |
| Phase 0 | Variable name mismatch in NEBEL validation | Added NEBEL_TO_ENGINE mapping layer |
| Phase 0 | MLYMC treated as lookup table (it's numerical derivative of LYMC) | Compute MLYMC as numerical derivative |
| Phase 0 | Capital sector doesn't declare_reads for FIOAA | Added to declares_reads(), removed from declares_writes() |
| Phase 0.5 | φ formula is design choice, not from notebooks | Documented as design choice; quadratic formula satisfies boundary conditions |
| Phase 0.5 | PPTD already 3rd-order delay (not 1st-order) | Confirmed correct; only default value needs changing |
| Phase 0.5 | Topological sort won't auto-order without declares_reads update | Added explicit declares_reads() update requirement |
| Phase 1 | `broadcast_demands()` is invented method name, would break all sectors | Use existing `RunContext.shared_state` dict instead |
| Phase 1 | "Security Value" allocation missing from CentralRegistrar | Added alongside "Ability to Pay" |
| Phase 1 | WILIAM military not subtracted from capital derivative | Fixed in merge plan |
| Phase 1 | Gradual gating (governance multiplier) replaced by hard cutoff | Added gradual governance multiplier |
| Phase 1 | Gallium omitted from Technology Metals | Added (Ag, Ga, In, Nd) |
| Phase 1 | Financial capital trapping mechanism omitted | Added |
| Phase 1 | GHG sources incomplete (only "fossil combustion") | Added calcination, natural gas leakage |
| Phase 1 | Social Suicide mechanism underspecified | Added Governance Multiplier, 3 stratified mortality multipliers |
| Phase 1 | Decoupling scenario override count: Q51 abbreviates to 4, but Q22 (definitive source) specifies 5 | Confirmed 5 overrides correct (includes 100% PRR at zero cost) |
| Phase 1 | Minsky Moment Nature variant omitted | Added |

### Subagent Review Findings

Three independent agents verified all 15 completed tasks against source code:

| Phase | Tasks Reviewed | Verdict | Notes |
|-------|---------------|--------|-------|
| Phase 0 | 7 (6 tasks + 1 bug fix) | All VERIFIED | Zero structural bugs, zero missing implementations |
| Phase 0.5 | 3 | All VERIFIED | No regressions detected |
| Phase 1 | 7 (6 tasks + tests) | All VERIFIED | Only gap: v2 scenario tests are construction-level, not behavioral |

**Overall: 17/17 tasks verified complete and correct. 535/535 tests pass.**

---

## Beyond Phase 2.1 (Deferred — v3+)

Per spec Section 19:
- 12-region spatial disaggregation
- Trade and migration flow networks
- Heterogeneous agents / ABM scheduler
- Tipping-point SDE modules and cascade propagation
- Endogenous Wright's-law technology learning curves
- NeuralODE or other learned surrogate registry
- MCMC / SMC Bayesian calibration
- Real-time assimilation via Ensemble Kalman Filter
