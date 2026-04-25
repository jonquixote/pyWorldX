# Calibration Engine: Learnings and Decisions (T2-1 → T4-1)

As we have progressed through the full Phase 2 sequential calibration (Population, Capital, Agriculture, Resources, Pollution) and into Phase 3 joint calibration, we encountered several deep structural challenges regarding how empirical data maps to a system dynamics engine.

Here is a summary of the key learnings and architectural decisions we have made to resolve them.

---

## 1. Instance Attribute Injection vs. Runtime Exogenous Overrides
**The Problem:** 
World3 sectors utilize many parameters (e.g., `initial_population`, `initial_ic`, `initial_al`) strictly during their `init_stocks()` phase, which executes exactly once at $t=0$. Previously, the calibration optimizer fed parameter samples purely into the runtime `inputs` dictionary. This meant initial boundary conditions and hardcoded class constants were completely ignored by the engine, causing flat or stunted calibration runs.

**The Decision:** 
We implemented `build_sector_engine_factory` in `empirical.py`. This factory explicitly intercepts the optimizer's parameter samples and maps them directly to the instance attributes of the instantiated sector objects (e.g., `setattr(ag_sector, "initial_arable_land", val)`) *before* the `Engine` is assembled and initialized.

**The Learning:** 
True structural calibration requires tuning the initial state of the differential equations, not just overriding the dynamic signals mid-loop. 

## 2. Sequential Sector Lock-in (`frozen_params`)
**The Problem:** 
Running Sobol/Morris optimization across the entire coupled 5-sector pyWorldX model simultaneously has too high dimensionality. The optimizer struggles to find global minima and often compensates for errors in one sector by aggressively breaking the physics of another.

**The Decision:**
We implemented a sequential calibration architecture via a `--frozen-params` CLI flag and `EmpiricalCalibrationRunner` support. This allows us to calibrate Population (T2-1), save the outputs, and pass them as locked constants into the Capital calibration (T2-2), and so on. 

**The Learning:**
Coupled system dynamics models must be calibrated sequentially from the most independent sectors (Population) down to the most dependent sectors (Agriculture, Resources).

## 3. Strict Decoupling of Model Units and Display Units
**The Problem:** 
During the Agriculture sector calibration (T2-3), the integration tests failed because the `food_per_capita` output was expected to hit real-world targets (~2200 `kcal/day`). Forcing the engine to output 2200 mathematically shattered the arable land equilibrium, because the engine uses generic "vegetable-equivalent kg/person/yr" units.

**The Decision:**
We decoupled structural units from display units. The engine and optimizer are now strictly gated to check for plausible structural bounds (`100–1000 kg/yr`). All real-world conversions (`FOOD_KG_TO_KCAL_DAY = 4.93`) are segregated entirely to the `display_units.py` layer. 

**The Learning:** 
The mathematical equilibrium of the internal differential equations must never be sacrificed for real-world display convenience. Calibrate the structural representation, then map the display representation.

## 4. Prioritized Multi-Source Deduplication
**The Problem:** 
When pulling data for the same engine variable (e.g., Food per capita) from multiple Parquet sources (OWID, FAOSTAT FBS, FAOSTAT Historical), we ended up with overlapping years with conflicting values. This created massive artificial vertical spikes in the calibration target, which destroyed the optimizer's gradients.

**The Decision:**
We added a `source_priority` array to the `ENTITY_TO_ENGINE_MAP` in `bridge.py`. The `DataBridge` now ranks overlapping data points by source priority and drops duplicates, enforcing a single, cohesive spline. 

**The Learning:**
Data cleanliness and continuity are vastly more important than data volume. The optimizer can interpolate gaps easily, but artificial discontinuities will permanently break the NRMSD objective function.

## 5. Differentiating Ingestion Gates vs. Cross-Validation Gates
**The Problem:** 
We introduced a strict `< 3` data points threshold for loading raw targets from Parquet to ensure meaningful splines. However, when applied globally, it accidentally affected `_clip_targets_to_window`, causing valid 2-point holdout validation windows (e.g., `[1990, 2000]`) to be silently dropped, resulting in `NaN` validation errors.

**The Decision:**
We separated the gates: raw ingestion (`load_targets`) remains at `< 3` to ensure base spline quality, while sub-window clipping (`_clip_targets_to_window`) was restored to `< 2` to permit standard 2-point holdout validation.

**The Learning:**
Cross-validation semantics require different length constraints than raw data ingestion.

## 6. Mismatch Between Empirical Targets and Engine Keys
**The Problem:**
During the T2-5 Pollution sector calibration, the objective function returned `NaN` across all trials. This occurred because the empirical data target's variable name (`PPOLX`) was hardcoded in the `ENTITY_TO_ENGINE_MAP`, but the `PollutionSector` actually published its output under the trajectory key `pollution_index`. The `compare()` function silently skipped the variable since it couldn't find a matching engine trajectory.

**The Decision:**
We explicitly updated the entity map's `engine_var` to exactly match the internal sector output key (`pollution_index`).

**The Learning:**
Silent mismatches between target names and engine state keys will permanently break calibration by resulting in NaN objective values. 

## 7. Complete Freezing of Upstream Sector Parameters
**The Problem:**
The T2-5 synthetic calibration tests failed because the optimizer was still exploring unbounded dimensions. The `frozen_params` dict in the test harness failed to include all parameters for the upstream Population, Capital, Agriculture, and Resources sectors (e.g., `initial_land_fertility`, `policy_year`). 

**The Decision:**
We must freeze *all* parameters outside the sector being calibrated. We verified the registry and ensured all 13 non-pollution parameters were properly included in the `frozen_params` dictionary during the T2-5 pollution calibration run.

**The Learning:**
When running a sequential calibration on a single downstream sector, the `frozen_params` dictionary must strictly encompass the complete universe of parameters from all upstream sectors. If any are missed, the optimizer will attempt to drift them, leading to mathematical instability (`NaN`).

## 8. Composite Mode: Self-Contained Joint Calibration
**The Problem:**
After completing all 5 sequential sector calibrations (T2-1 → T2-5), the next step (T3-1) requires joint multi-sector optimisation over the 5–6 most influential cross-sector parameters simultaneously. The existing `EmpiricalCalibrationRunner.run()` required external `registry` and `engine_factory` arguments, tightly coupling it to the single-sector CLI workflow.

**The Decision:**
We added a `composite: bool = False` flag to `EmpiricalCalibrationRunner`. When `True`, the runner becomes fully self-contained: it builds its own registry from all 5 sectors, constructs the engine factory internally, applies mandated composite weights (`population=1.5, co2=1.5, food_per_capita=1.0, industrial_capital=1.0, resources=0.75`), and delegates to `_run_optimizer()` — a dedicated method that wraps the calibration pipeline and is easily patchable for fast unit tests.

**The Learning:**
Separating the optimiser invocation into a distinct `_run_optimizer()` method enables test-driven development without Optuna overhead. The composite/single-sector split keeps the existing sequential workflow untouched while opening the door to joint fine-tuning.

## 9. Regression Baselines: Graceful Degradation Guards
**The Problem:**
After calibrating across all sectors, there is no mechanism to detect if a future code change silently degrades NRMSD scores. A seemingly innocent refactor could worsen a sector's fit by 10–20% without anyone noticing until a full calibration re-run.

**The Decision:**
We introduced `output/calibration_baseline.json` as a machine-readable manifest recording `optimized_params`, `sector_nrmsd`, `composite_train_nrmsd`, `composite_validation_nrmsd`, and `overfit_flagged`. Three regression tests in `test_regression.py` validate against this manifest with a 5% tolerance gate. All three tests skip gracefully when the baseline or aligned data directory is absent, making them safe for CI before the first real calibration.

**The Learning:**
The `quick_evaluate()` method needed a new return type (`QuickEvaluateResult`) with a `sector_nrmsd` dict rather than the raw `BridgeResult`. This decouples the regression API from internal bridge internals and makes the test contract explicit. Seeding the manifest with Nebel 2023 upper bounds provides a conservative starting point that any real calibration will improve upon.
