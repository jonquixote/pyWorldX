# pyWorldX — Technical Specification
## Version 0.2.9
### Build-ready bridge spec between v0.2.0 foundation and later forecasting architecture

**Status:** Authoritative implementation spec for the 0.2.9 build target  
**Audience:** Core engine, sector, data, calibration, and tooling developers  
**Intent:** This file supersedes 0.2.8 by resolving the CrossValidationConfig/NRMSD window
conflict, defining capital_productivity_factor inline, reconciling the WILIAM substep_ratio
contract with BaseSector.timestep_hint, specifying the nrmsd_direct denominator, specifying
sub-step integrator behavior, fixing the analytical sub-case near-zero instability, promoting
dist_type and shape to Enums, pinning the PySD generator version, and correcting semver
wording in Section 4.1.

### Changelog from v0.2.8

- **FIX-19** Section 9.4: `CrossValidationConfig` default `train_end` remains `2010` for
  general use. Named constant `NEBEL_2023_CALIBRATION_CONFIG` introduced with
  `train_end=2020`, `validate_end=2023`. World3-03 historical validation workflow (Section
  13.1) is required to use `NEBEL_2023_CALIBRATION_CONFIG` explicitly.
- **FIX-20** Section 17.1: `capital_productivity_factor(pollution_efficiency)` defined
  inline as a linear passthrough: `capital_productivity_factor(pe) = pe`. No additional
  parameters. This makes the canonical test world fully self-contained from the spec alone.
- **FIX-21** Section 15.1 / 5.3: WILIAM sector `timestep_hint` is now a computed property
  `master_dt / substep_ratio`, derived at engine init when master dt is known.
  `resolve_substep_ratio()` is still called on it — the single validation path is preserved.
  `WiliamAdapterConfig.substep_ratio` expresses intent; the engine enforces the contract.
- **FIX-22** Section 9.1: `nrmsd_direct` normalization denominator specified as
  mean-normalization matching Nebel et al. (2023). Formula added verbatim.
- **FIX-23** Section 6.1 / 6.4: Sub-stepped sectors use RK4 at the sub-step level by
  default. Sectors may override via `preferred_substep_integrator` metadata field.
- **FIX-24** Section 17.4: Analytical sub-case pass criterion made hybrid — relative error
  `< 1e-4` for `t ≤ 100`; absolute error `< 1e-6` for `t > 100` — to avoid
  ill-conditioned relative error when `P` approaches zero.
- **FIX-25** Sections 10.3 / 11.1: `ParameterDistribution.dist_type` promoted to
  `DistributionType` enum. `PolicyEvent.shape` promoted to `PolicyShape` enum.
- **FIX-26** Section 17.3: PySD generator version pinned to `PySD==3.14.0`. A
  `requirements-canonical.txt` file committed alongside `generate_reference.py` pins the
  exact dependency. Minor PySD releases that change integrator or interpolation behavior
  require a new pinned version and a FROZEN update.
- **FIX-27** Section 4.1: "versioned at the minor level" corrected to "versioned at the
  patch-group level" to avoid confusion with standard semver semantics.

### Milestone Positioning

Version 0.2.9 is a correctness patch on the 0.2.8 milestone. It introduces no new scope.

---

## Table of Contents

1. Purpose and Scope
2. Design Principles
3. Architecture Overview
4. Repository Layout
5. Sector Contract
6. Engine Primitives
7. Ontology and Adapter Layer
8. Data Pipeline
9. Calibration and Sensitivity
10. Ensemble Forecasting Layer
11. Scenario Management
12. Observability and Provenance
13. Validation Strategy
14. Sector Library — v1.0 (World3-03)
15. Sector Library — v1.1 (WILIAM Economy Adapter)
16. Sector Library — v2.0-Ready Interfaces
17. Canonical Test World
18. Metadata Reference
19. Deferred Items
20. Implementation Sequence

---

## 1. Purpose and Scope

pyWorldX is a modular, unit-safe, auditable forecasting platform for long-horizon global
systems modeling. It begins from World3-03 compatibility, extends into richer biophysical
and economic adapters, and is designed so that future regionalization, tipping dynamics, and
endogenous decision layers can be added without breaking core contracts.

### 1.1 The Forecasting Standard

The primary output of pyWorldX is not a single "best run." The primary output is a structured
forecast object that can answer:

- What trajectories occur under a defined scenario?
- What range emerges under parameter uncertainty?
- Which assumptions dominate forecast spread?
- What threshold crossings are plausible by a given date?
- Which sectors, adapters, or exogenous series drive the result?

Accordingly, 0.2.9 must support both:

- **Deterministic reference runs** for debugging, validation, and historical reproduction.
- **Ensemble runs** for uncertainty-aware forecasting using repeated scenario execution with
  perturbed parameters and/or exogenous inputs.

### 1.2 Scope

Included in scope:

- Deterministic ODE / stock-flow engine with RK4 and a fixed master timestep.
- Optional **multi-rate execution by fixed-ratio sector sub-stepping** beneath that master timestep.
- Typed sector interface using `Quantity`-based runtime unit checking.
- Dependency graph build, topological sort, algebraic loop detection, intra-sector loop hints,
  cross-sector loop resolution, and balance auditing.
- Ontology registry plus explicit adapter layer between sector-native variables and canonical
  pyWorldX entities, including state-dependent weight functions.
- Connectors for baseline historical data and unit-safe transformation chains.
- Deterministic calibration and sensitivity tooling using NRMSD, Morris screening, Sobol
  decomposition, and profile-likelihood identifiability checks.
- Scenario dataclass, typed `PolicyEvent` records, built-in scenarios, and parallel execution.
- Ensemble wrapper, forecast summaries, percentile bands, pre-declared threshold probability
  queries, and uncertainty decomposition.
- Traceability, provenance, and validation against World3-03 reference behavior.
- World3 v1.0 sector set plus WILIAM economy adapter v1.1.

Explicitly out of scope:

- Regionally disaggregated 12-region production models.
- Heterogeneous agents / ABM scheduler.
- Full tipping-point stochastic differential modules.
- NeuralODE or other learned surrogate engines.
- MCMC / SMC Bayesian calibration as mandatory tooling.
- Endogenous technology learning curves as active forecasting sectors.

### 1.3 Definition of Done

v0.2.9 is complete when:

- A clean install can execute the canonical test world deterministically.
- Historical validation against World3-03 passes documented tolerances using
  `NEBEL_2023_CALIBRATION_CONFIG`.
- Scenario and ensemble APIs return auditable forecast objects.
- WILIAM adapter sectors can run inside the same engine contract.
- Provenance captures code version, config hash, connector versions, parameter set,
  cross-validation config, and scenario metadata.
- CI validates units, sector tests, reference trajectories, and forecast summaries.
- The multi-rate scheduler is exercised by a sub-stepped sector in the canonical test world.
- The algebraic loop resolver is exercised by a single-rate intra-sector loop in the
  canonical test world.

---

## 2. Design Principles

### 2.1 Sector Versioning

Every sector declares semantic version metadata. Engine compatibility is enforced by explicit
contracts, not by convention.

### 2.2 Explicit Approximations

All aggregation, proxy mappings, interpolation assumptions, and data imputation rules must be
represented as metadata or configuration fields. Hidden assumptions are forbidden.

### 2.3 Conservation Enforcement

Where a sector models conserved stocks or balance-constrained flows, the engine audits net
creation/destruction over a time step. Violations above tolerance are surfaced as errors or
warnings depending on sector metadata.

### 2.4 Forecast Output Is the Product

Single trajectories are diagnostic artifacts. External-facing model usage should default toward
scenario bundles and ensemble summaries.

### 2.5 Calibration and Sensitivity Are Pre-eminent

Every adjustable parameter must be tagged with bounds, rationale, provenance, and
identifiability risk. A model with elegant structure but weak calibration discipline is not
acceptable.

### 2.6 Reproducibility Is Mandatory

Given the same code revision, inputs, parameters, random seed bundle, cross-validation config,
and scenario specification, pyWorldX must reproduce the same deterministic run and the same
ensemble summary.

### 2.7 Structural Honesty

If a causal mechanism is absent, pyWorldX reports it as absent. Interface placeholders are
allowed; deceptive completeness is not.

### 2.8 The Smart TV Principle

The system must be powerful internally but operable externally through simple high-level
commands. A user should be able to run a scenario bundle and obtain forecast summaries without
understanding every engine primitive.

---

## 3. Architecture Overview

The 0.2.9 architecture is composed of nine layers:

1. **Core Engine** — integration, graph resolution, multi-rate stepping, balance auditing.
2. **Sector Library** — World3 and adapter-backed sectors implementing the common contract.
3. **Ontology Layer** — canonical variable names, dimensions, and stock/flow semantics.
4. **Adapter Layer** — maps external model or data nomenclature into ontology entities.
5. **Data Pipeline** — connectors, transformations, unit normalization, gap handling, provenance.
6. **Calibration Layer** — objective functions, parameter registries, sensitivity scans,
   deterministic fitting.
7. **Scenario Layer** — structured interventions, typed policy events, exogenous overrides.
8. **Ensemble Forecasting Layer** — repeated scenario execution, summaries, pre-declared
   threshold queries.
9. **Observability Layer** — traces, run manifests, audit logs, and validation reports.

### 3.1 Runtime Flow

```
config -> ontology registry -> sectors -> dependency graph -> scenario application ->
integration loop -> trace/audit -> run result -> ensemble summarization
```

### 3.2 Key Runtime Objects

- `ModelConfig`
- `CrossValidationConfig`
- `NEBEL_2023_CALIBRATION_CONFIG`
- `SectorDefinition`
- `OntologyRegistry`
- `Scenario`
- `RunContext`
- `RunResult`
- `EnsembleSpec`
- `EnsembleResult`
- `ProvenanceManifest`

### 3.3 Compatibility Goal

All 0.2.9 interfaces must be forward-compatible with regional dimensions added to state
vectors, stochastic drivers added to the run context, surrogate models inserted as optional
execution backends, and agent layers consuming or emitting ontology variables.

---

## 4. Repository Layout

### 4.1 Patch-Group Version Naming Convention

Spec files are versioned at the patch-group level (z-level), e.g. `pyWorldX_spec_0.2.9.md`.
In this project's versioning scheme, `0.2.x` is the patch-group (third digit), and four-part
versions like `0.2.9.0` represent frozen implementation targets within that group.

### 4.2 File Structure

```
pyWorldX/
  docs/
    specs/
      pyWorldX_spec_0.2.9.md      <- this document
      latest.md                   <- symlink to current spec
  pyworldx/
    config/
      model_config.py
      scenario_config.py
      ensemble_config.py
      calibration_config.py       <- includes CrossValidationConfig,
                                     NEBEL_2023_CALIBRATION_CONFIG
    core/
      quantities.py
      state.py
      graph.py
      integrators.py
      multirate.py
      loops.py
      balance.py
      result.py
      stochastic.py
    ontology/
      registry.py
      entities.py
      dimensions.py
    adapters/
      base.py
      world3_adapter.py
      wiliam_adapter.py
      data_adapters/
    data/
      connectors/
        world_bank.py
        un_pop.py
        faostat.py
        noaa_co2.py
        our_world_in_data.py
        unido.py
        undp_hdr.py
        footprint_network.py
        fred.py
      transforms/
        units.py
        interpolation.py
        normalization.py
        gap_fill.py
      schemas/
      cache/
    sectors/
      base.py
      population.py
      capital.py
      agriculture.py
      resources.py
      pollution.py
      adaptive_technology.py
      welfare.py
      wiliam/
    calibration/
      metrics.py
      parameters.py
      sensitivity.py
      workflow.py
      profile_likelihood.py
      morris.py
      sobol.py
    forecasting/
      ensemble.py
      thresholds.py
      summaries.py
      uncertainty.py
    scenarios/
      builtin.py
      runner.py
    observability/
      trace.py
      provenance.py
      reports.py
    validation/
      world3_reference.py
      sector_tests.py
      regression_tests.py
  tests/
    unit/
    integration/
    validation/
    canonical/
      rip_canonical.xmile
      generate_reference.py
      requirements-canonical.txt  <- pins PySD==3.14.0 and dependencies
      reference_trajectory.csv
```

### 4.2 Repository Rules

- Specs live in `docs/specs/` and are versioned alongside code.
- `latest.md` is a symlink to the current spec; CI must resolve it at build time.
- Canonical ontology names must not be duplicated across modules.
- Connectors must expose source metadata, version dates, and transformation logs.
- Validation fixtures and historical reference outputs must be committed or fetchable from
  pinned manifests.

---

## 5. Sector Contract

### 5.1 Interface Definition

```python
class BaseSector(Protocol):
    name: str
    version: str
    timestep_hint: float | None

    def init_stocks(self, ctx: "RunContext") -> dict[str, Quantity]: ...
    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: "RunContext",
    ) -> dict[str, Quantity]: ...

    def algebraic_loop_hints(self) -> list[dict]: ...
    def metadata(self) -> dict: ...
```

Rules:

- `init_stocks()` returns canonical stock names with units.
- `compute()` returns named flows / auxiliaries / output observables as `Quantity` values.
- Sector outputs must use ontology-approved names or sector-local names with explicit adapter
  mapping.
- Metadata must declare conservation properties, free parameters, validation status,
  approximation notes, and optionally `preferred_substep_integrator`.

### 5.2 Algebraic Loop Hints

`algebraic_loop_hints()` declares **intra-sector** loop candidates or sector-local expectations
about cyclic dependencies. It does not define the complete set of cross-sector loops in the
assembled model.

```python
[
  {
    "name": "food_birth_feedback",
    "variables": ["food_per_capita", "birth_rate"],
    "scope": "intra_sector",
    "solver": "fixed_point",
    "tol": 1e-8,
    "max_iter": 50,
  }
]
```

Cross-sector loops are detected only after the global dependency graph is built. The engine
compares detected cycles against declared sector hints. Undeclared or unexplained cross-sector
cycles raise `UndeclaredAlgebraicLoopError` at initialization.

### 5.3 Multi-Rate Declaration and Conversion Contract

Sectors may declare `timestep_hint: float` (in years) to signal that they benefit from
sub-stepping beneath the master step.

The engine converts `timestep_hint` to an integer `substep_ratio` as follows:

```python
def resolve_substep_ratio(master_dt: float, timestep_hint: float, tol: float = 1e-9) -> int:
    ratio = master_dt / timestep_hint
    ratio_int = int(round(ratio))
    if abs(ratio - ratio_int) > tol:
        raise IncompatibleTimestepError(
            f"master_dt={master_dt} / timestep_hint={timestep_hint} = {ratio:.6f}, "
            f"which is not an integer within tolerance {tol}. "
            f"Adjust master_dt or timestep_hint so that their ratio is a whole number."
        )
    return ratio_int
```

`timestep_hint` is the human-readable form; `substep_ratio` is what the engine operates on.
The engine must validate all sector `timestep_hint` values at initialization and fail loudly
on non-integer ratios. Arbitrary asynchronous scheduling remains out of scope for 0.2.9.

**Adapter sectors** (e.g. WILIAM) that express intent as an integer `substep_ratio` must
expose `timestep_hint` as a computed property `master_dt / substep_ratio`, resolved at engine
init. `resolve_substep_ratio()` is still called on that computed value — the single
validation path is never bypassed. See Section 15.1 for the WILIAM implementation pattern.

### 5.4 Sector Metadata Contract

Required metadata fields:

- `validation_status`
- `equation_source`
- `world7_alignment`
- `approximations`
- `free_parameters`
- `conservation_groups`
- `observables`
- `unit_notes`
- `preferred_substep_integrator` *(optional; defaults to `"rk4"` if absent)*

---

## 6. Engine Primitives

### 6.1 Integration

The engine supports:

- Euler (debug only at master step; may be selected for sub-steps via sector metadata)
- RK4 (default integrator, both at master step and sub-step level)
- Fixed-step execution at the **master-clock** level

**Clarification:** "Fixed-step execution" means the model advances on a single global
communication grid at `dt`. "Multi-rate" in 0.2.9 means certain sectors may be sub-stepped
at fixed integer ratios beneath the master step, with communication only at master
boundaries. This is constrained multi-rate co-simulation, not a contradiction of fixed-step
execution.

**Sub-step integrator policy:** Sub-stepped sectors use RK4 at the sub-step level by default.
A sector may declare `preferred_substep_integrator: "euler"` in its metadata to request
Euler at the sub-step level (acceptable for smooth, slowly-varying dynamics). The engine
logs a warning if Euler is selected for a sector whose dynamics include a stiff transition
(e.g. a Hill function with exponent > 1). The default is always RK4; Euler requires
explicit opt-in.

RK4 guardrails:

- reject NaN / inf intermediate states,
- reject unit-inconsistent derivative accumulation,
- surface event logs when state clipping occurs,
- allow analytical sub-cases in canonical tests.

### 6.2 Dependency Graph and Topological Sort

The engine constructs a directed graph of sector input/output dependencies. A topological
order is produced for the acyclic remainder. Cross-sector cycles are detected centrally after
graph construction.

Loop policy:

- sector-declared `algebraic_loop_hints()` provide local expectations and preferred solver
  metadata,
- graph analysis identifies actual cycles in the assembled model,
- undeclared cross-sector cycles raise `UndeclaredAlgebraicLoopError` at initialization.

### 6.3 Algebraic Loop Resolution

Supported loop solvers:

- fixed-point iteration,
- damped fixed-point iteration,
- optional Newton-style hook if sector provides derivative approximations.

Loop diagnostics must report:

- whether the loop is intra-sector or cross-sector,
- iterations used,
- convergence status,
- final residual,
- fallback mode if convergence fails.

### 6.4 Multi-Rate Co-Simulation Master

The engine sub-steps fast sectors at fixed integer subdivisions of the master step, derived
from each sector's `timestep_hint` via `resolve_substep_ratio()` (Section 5.3). The master
scheduler must preserve deterministic reproducibility. Balance auditor checks occur at
master-step communication boundaries.

Slow sectors provide **frozen last-known values** to fast sectors between communication
points. This means any cycle that crosses a multi-rate boundary is not a simultaneous
algebraic loop — it is a delayed coupling. The algebraic loop resolver is only invoked for
cycles that exist entirely within the single-rate communication domain.

Sub-stepped sectors use RK4 at the sub-step level by default (see Section 6.1).

### 6.5 Balance Auditor

```python
BalanceAuditResult(
    group="nonrenewable_resource_mass",
    expected_delta=-extraction,
    observed_delta=stock_t1 - stock_t0,
    residual=observed_delta - expected_delta,
    status="PASS|WARN|FAIL",
)
```

### 6.6 Stochastic State

```python
@dataclass
class StochasticState:
    master_seed: int
    stream_seeds: dict[str, int]
    draws_used: dict[str, int]
```

Deterministic runs may omit it. Ensemble runs must record it. Random perturbations must use
named streams, not ambient global RNG state.

### 6.7 Run Result

Every run returns a structured result object with:

- time index,
- state trajectories,
- observables,
- trace reference,
- balance audits,
- warnings,
- scenario metadata,
- provenance manifest reference.

---

## 7. Ontology and Adapter Layer

### 7.1 Two-Layer Boundary Checking

1. **Sector boundary** — sector outputs and inputs are runtime unit-checked through `Quantity`.
2. **Ontology boundary** — mapped variables are checked for semantic dimension, stock/flow
   role, and aggregation semantics.

### 7.2 Ontology Registry

The registry defines canonical entities such as:

- `population.total`
- `food.per_capita`
- `capital.industrial_stock`
- `resources.nonrenewable_stock`
- `pollution.persistent_load`
- `welfare.index`

Each entity stores dimension / unit family, stock vs flow vs auxiliary role, aggregation
semantics, typical source mappings, and notes on approximation legitimacy.

The registry must support **state-dependent mapping weights** for cross-generation adapters:

```python
class OntologyRegistry:
    def register_mapping(
        self,
        source_var: str,
        target_vars: list[str],
        weight_fn: Callable[[dict, float], list[float]],
        equation_source: str,
        notes: str,
    ) -> None: ...
```

`weight_fn(state, t)` must be a pure function returning weights that sum to 1.0. This is
mandatory wherever a composite variable maps into multiple physical stocks whose relative
contributions evolve over time. A static coefficient is not acceptable for such mappings.

### 7.3 Adapter Responsibilities

Adapters are responsible for:

- name translation,
- unit conversion,
- stock/flow interpretation,
- temporal alignment,
- proxy declaration,
- provenance annotation,
- state-dependent disaggregation where required.

### 7.4 Worked Mapping Example

`World3::nonrenewable_resources` must map through a time-varying allocator, not through fixed
coefficients. The adapter must separately represent remaining stock, extraction flow, depletion
fraction, and any empirical reserve proxy.

### 7.5 Adapter Failure Rules

An adapter must fail loudly when:

- a required ontology entity is absent,
- units are incompatible,
- a stock is inferred from a flow without declared reconstruction logic,
- temporal frequency mismatch exceeds configured tolerance,
- a mapping that requires `weight_fn(state, t)` is implemented with undocumented static
  coefficients.

---

## 8. Data Pipeline

### 8.1 Empirical Data Connectors (mandatory)

Globally central connector set (all required for World3-03 calibration):

- World Bank
- UN population source
- FAOSTAT or equivalent food / agriculture source
- NOAA / Global Carbon Project or equivalent atmospheric series
- Our World in Data / BP-style historical energy series for cumulative fossil-use reconstruction
- USGS minerals / nonrenewables source
- UNIDO or equivalent industrial output source
- UNDP HDR / ecological-footprint style welfare sources where used in validation

Optional macro connector:

- FRED, when needed for deflators, price normalization, or macro-financial auxiliary series.
  If included in a run, its purpose must be declared in connector metadata.

```python
@dataclass
class ConnectorResult:
    series: pd.Series
    unit: str
    source: str
    source_series_id: str
    retrieved_at: str
    vintage: str | None
    proxy_method: str | None
    transform_log: list[str]
```

`proxy_method` is mandatory whenever the connector output is a proxy rather than a direct
measurement. The calibration layer must enforce that all runs being NRMSD-compared share the
same `proxy_method` for each variable.

### 8.2 Food Per Capita Unit Chain

The food pipeline must make the normalization chain explicit:

1. obtain total food output / supply,
2. convert to calories or mass-equivalent using declared factors,
3. normalize to annual per-capita quantity,
4. convert to daily per-capita representation if needed,
5. annotate approximation and conversion source.

### 8.3 Non-Renewable Resources Proxy

The nonrenewables connector must not confuse extraction flow with remaining stock.

Acceptable approaches:

- direct reserve / stock proxy with caveats,
- reconstruction from cumulative extraction plus reserve estimates,
- indexed depletion proxy explicitly marked as non-physical stock.

The chosen method must be declared in `proxy_method`, stored in provenance, and enforced as
a comparability constraint by the calibration layer.

### 8.4 Connector Failure Modes

Failure modes to encode explicitly:

- missing observation windows,
- frequency mismatch,
- methodological breaks,
- source revisions,
- unit ambiguity,
- silent schema changes,
- proxy invalidation.

### 8.5 Transformation Pipeline

Explicit stages:

1. raw ingest,
2. schema normalization,
3. unit conversion,
4. interpolation / resampling,
5. gap handling,
6. ontology mapping,
7. cache write.

### 8.6 Caching and Versioning

Connector outputs are cached with source version and retrieval date. A run manifest must
record the exact data vintage and `proxy_method` used for each connector.

---

## 9. Calibration and Sensitivity

### 9.1 NRMSD Metric

Two formulations required:

```python
def nrmsd_direct(series_true: pd.Series, series_pred: pd.Series) -> float: ...
def nrmsd_change_rate(series_true: pd.Series, series_pred: pd.Series) -> float: ...
def weighted_nrmsd(metrics: dict[str, float], weights: dict[str, float]) -> float: ...
```

**`nrmsd_direct` — mean-normalized RMSD:**

Used for level-compared variables (population, HDI, ecological footprint).

```python
def nrmsd_direct(series_true: pd.Series, series_pred: pd.Series) -> float:
    rmsd = np.sqrt(np.mean((series_pred.values - series_true.values) ** 2))
    return rmsd / np.mean(series_true.values)
```

Normalization is by `mean(true)` over the comparison window. This matches the Nebel et al.
2023 formulation and is the denominator that makes the Section 13.1 bounds reproducible.
Implementations using range, std, or any other denominator will produce non-comparable scores.

**`nrmsd_change_rate` — change-rate NRMSD:**

Used for rate-compared variables (industrial output, food per capita, pollution,
non-renewables, service per capita).

Both series are first transformed to annual percentage change rates (matching the Nebel et al. 2023 formulation):

```python
def annual_pct_change(series: pd.Series) -> pd.Series:
    return 100.0 * (series.diff() / series.shift(1))
```

`nrmsd_change_rate` is then computed as `nrmsd_direct` applied to the transformed series,
dropping the first NaN row introduced by `.diff()`. This formulation is the one used to
derive the tolerance bounds in Section 13.1.

### 9.2 Free Parameters

Every free parameter entry must include:

- name,
- default value,
- bounds,
- units,
- sector owner,
- rationale,
- empirical anchor if any,
- `IDENTIFIABILITY_RISK` flag with assignment rationale,
- scenario mutability flag.

`IDENTIFIABILITY_RISK` is assigned by structural or empirical evidence: historically large
recalibrations relative to literature defaults, slow-state parameters with weak observation
leverage, or flat-plateau results detected during profile-likelihood screening. It must never
be assigned by intuition alone.

### 9.3 Calibration Workflow

**Step 0 — Structural identifiability pre-screen (mandatory):**

- Fit from multiple random initial configurations.
- Run profile likelihood on all parameters flagged `IDENTIFIABILITY_RISK`.
- Classify each as identifiable, flat-plateau / fix-at-literature, or threshold-gated.
- Budget: 20 grid points per screened parameter, parallelized across available cores.
  See Section 9.6 for full specification.

**Step 1 — Morris elementary effects screening:**

- Run SALib Morris screening across all non-excluded candidate parameters.
- Retain the reduced set that drives the overwhelming majority of variance in validation
  targets.

**Step 2 — Deterministic calibration:**

- Apply the deterministic NRMSD optimization loop only to the screened parameter subset.
- Use documented bounds and termination criteria.
- Record the final parameter registry and calibration report.

**Step 3 — Sobol variance decomposition:**

- Compute first-order and total-order Sobol indices on the calibrated reduced set.
- Publish as the authoritative sensitivity ranking for the milestone.

### 9.4 Cross-Validation

The train/validate split is a named field on `CrossValidationConfig`, not a hardcoded constant:

```python
@dataclass
class CrossValidationConfig:
    train_start: int = 1970
    train_end: int = 2010
    validate_start: int = 2010
    validate_end: int = 2023
    overfit_threshold: float = 0.20
```

For reproducing the Nebel et al. (2023) `Recalibration23` result and comparing against the
Section 13.1 NRMSD bounds (which are defined on a 1970–2020 training window), callers must
use the named constant:

```python
NEBEL_2023_CALIBRATION_CONFIG = CrossValidationConfig(
    train_start=1970,
    train_end=2020,
    validate_start=2020,
    validate_end=2023,
    overfit_threshold=0.20,
)
```

The World3-03 historical validation workflow (Section 13.1) is **required** to use
`NEBEL_2023_CALIBRATION_CONFIG`. Using the default `CrossValidationConfig` will produce a
shorter training window and non-comparable NRMSD values against the Section 13.1 bounds.

An instance of the config used must be recorded in the provenance manifest. A calibration
that improves training NRMSD but worsens validation NRMSD by more than `overfit_threshold`
(default 20% relative) is flagged as potential overfit in metadata.

### 9.5 Sensitivity Outputs

Required output artifacts:

- Morris screening report with ranked elementary effects,
- Sobol first-order and total-order indices,
- sign of effect where stable,
- interaction notes if discovered,
- compact report of unstable or non-identifiable parameter dimensions.

### 9.6 Profile Likelihood Specification

For a model with `k` candidate `IDENTIFIABILITY_RISK` parameters:

- Grid resolution: 20 points per parameter over admissible bounds.
- Re-optimization: for each grid point on parameter `i`, re-optimize over all remaining
  screened parameters using the standard NRMSD calibration procedure.
- Total evaluations: `k x 20 x (cost of one calibration pass)`.
- Execution: must be parallelized across available cores; serial execution is acceptable
  only for `k <= 3` and `n_workers == 1`.
- Output: `IdentifiabilityReport` with per-parameter classification and profile curve.

This is mandatory before any parameter search step and must be recorded in the provenance
manifest.

### 9.7 Bayesian Compatibility Hooks

0.2.9 does not mandate MCMC or SMC, but parameter registries and objective functions must
be structured so later probabilistic calibration can reuse them without redesign.

---

## 10. Ensemble Forecasting Layer

### 10.1 Design Goal

The deterministic engine remains the numerical kernel. The ensemble layer repeatedly executes
that kernel under controlled perturbations and summarizes the resulting forecast distribution.

### 10.2 Uncertainty Classes

```python
class UncertaintyType(Enum):
    PARAMETER = "parameter"
    SCENARIO = "scenario"
    EXOGENOUS_INPUT = "exogenous_input"
    INITIAL_CONDITION = "initial_condition"
    STRUCTURAL_NOTE = "structural_note"
```

`STRUCTURAL_NOTE` is metadata only and is not sampled directly.

**This definition in Section 10.2 is authoritative. Section 18.4 reproduces it for
reference only.**

### 10.3 ParameterDistribution

```python
class DistributionType(Enum):
    UNIFORM = "uniform"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    TRUNCATED_NORMAL = "truncated_normal"

@dataclass
class ParameterDistribution:
    dist_type: DistributionType
    params: dict[str, float]       # e.g. {"low": 0.5, "high": 1.5}
    seed_stream: str               # named RNG stream key in StochasticState
    uncertainty_type: UncertaintyType  # mandatory — no default; must be set explicitly
```

`uncertainty_type` is mandatory with no default. Callers constructing
`initial_condition_perturbations` must set `uncertainty_type=UncertaintyType.INITIAL_CONDITION`
explicitly. This prevents provenance mislabeling.

### 10.4 Threshold Query Types

Thresholds are **declared in `EnsembleSpec`** and computed **eagerly at run time** as the
ensemble accumulates. They are not computed lazily over stored member trajectories.

```python
@dataclass(frozen=True)
class ThresholdQuery:
    name: str
    variable: str
    op: str           # "below" | "above" | "crosses"
    threshold: float
    by_year: int
    unit: str | None = None

@dataclass
class ThresholdQueryResult:
    query: ThresholdQuery
    probability: float
    member_count: int
```

### 10.5 EnsembleSpec

```python
@dataclass
class EnsembleSpec:
    n_runs: int
    base_scenario: "Scenario"
    parameter_distributions: dict[str, ParameterDistribution]
    exogenous_perturbations: dict[str, ParameterDistribution]
    initial_condition_perturbations: dict[str, ParameterDistribution]
    threshold_queries: list[ThresholdQuery]
    seed: int
    store_member_runs: bool = False
```

### 10.6 EnsembleResult

```python
@dataclass
class EnsembleResult:
    members: list["RunResult"] | None
    summary: dict[str, pd.DataFrame]
    threshold_results: dict[str, ThresholdQueryResult]
    uncertainty_decomposition: dict[str, dict[str, float]]
    manifest_refs: list[str]
```

`summary` must include, per variable: mean, median, p05, p25, p75, p95, min, max.

### 10.7 Threshold Probability Access

```python
def probability_of_threshold(ensemble: EnsembleResult, query_name: str) -> float:
    return ensemble.threshold_results[query_name].probability
```

If a threshold was not declared in `EnsembleSpec`, accessing it raises
`UndeclaredThresholdQueryError`. Re-running the ensemble with the query declared is the
correct resolution.

### 10.8 Uncertainty Decomposition

Minimum decomposition of forecast spread attributable to:

- parameter perturbations,
- scenario differences,
- exogenous input perturbations,
- initial condition uncertainty.

### 10.9 Storage Policy

By default, store only summaries and manifests unless `store_member_runs=True`.

---

## 11. Scenario Management

### 11.1 PolicyEvent Dataclass

```python
class PolicyShape(Enum):
    STEP = "step"
    RAMP = "ramp"
    PULSE = "pulse"
    CUSTOM = "custom"

@dataclass
class PolicyEvent:
    target: str
    shape: PolicyShape
    t_start: float
    t_end: float | None = None
    magnitude: float | None = None
    rate: float | None = None
    custom_fn: Callable[[float, float], float] | None = None  # (baseline_value, t)
    description: str = ""

    def apply(self, baseline_value: float, t: float) -> float: ...
```

For `shape=PolicyShape.CUSTOM`, `custom_fn(baseline_value, t)` receives both the baseline
value and the current time and must return the modified value. The signature matches
`apply()`.

### 11.2 Scenario Dataclass

```python
@dataclass
class Scenario:
    name: str
    description: str
    start_year: int
    end_year: int
    parameter_overrides: dict[str, float]
    exogenous_overrides: dict[str, pd.Series]
    policy_events: list[PolicyEvent]
    tags: list[str]
```

### 11.3 Built-in Scenarios

Minimum built-ins:

- `baseline_world3`
- `high_resource_discovery`
- `pollution_control_push`
- `agricultural_efficiency_push`
- `capital_reallocation_to_maintenance`
- `wiliam_high_military_drag`

### 11.4 Parallel Scenario Runner

The scenario runner must execute multiple scenarios against a common model definition and
emit a harmonized set of run or ensemble results.

### 11.5 Scenario Semantics

Scenarios are interventions or exogenous narratives; they are not hidden parameter edits.
Every override must be typed, dated, and recorded in provenance.

---

## 12. Observability and Provenance

### 12.1 Trace Emission Levels

| Level | Description |
|---|---|
| `OFF` | No trace |
| `SUMMARY` | Sector order, major balance audits, warnings |
| `FULL` | Per-step CausalTraceRef emission for all variables |

### 12.2 Causal Trace Query

Tracing uses a two-type pattern to decouple zero-overhead emission from potentially expensive
materialization.

**CausalTraceRef** is emitted during the run at zero materialization cost. It stores indices
and keys only:

```python
@dataclass
class CausalTraceRef:
    variable: str
    t: float
    raw_value: float
    unit: str
    upstream_keys: list[str]
    state_snapshot_ref: int      # index into run-internal snapshot ring buffer
    equation_source: EquationSource
    sector: str
    loop_resolved: bool

    def render(self, run_result: "RunResult") -> "CausalTrace": ...
```

`loop_resolved` is True when the variable's value at this timestep was produced by the
algebraic loop resolver rather than direct topological evaluation.

**CausalTrace** is the fully materialized form, produced by calling `.render()` on a ref:

```python
@dataclass
class CausalTrace:
    variable: str
    t: float
    value: Quantity
    upstream_inputs: dict[str, Quantity]
    equation_source: EquationSource
    sector: str
    loop_resolved: bool
```

The single materialization API is `ref.render(run_result) -> CausalTrace`. There is no
`CausalTrace.from_ref()` class method in the public interface.

**Snapshot Ring Buffer Contract:**

The run-internal snapshot ring buffer used by `state_snapshot_ref` must implement the
following contract:

- **Size:** configurable via `RunConfig.trace_ring_buffer_size` (default: `2`, retaining
  current and previous master-step snapshots).
- **Eviction policy:** FIFO — oldest snapshot is evicted first when the buffer is full.
- **Index validity:** `state_snapshot_ref` stores the absolute step index at emission time.
  On `.render()`, the engine checks whether the referenced step is still within the buffer
  window. If it has been evicted, `.render()` raises `StaleTraceRefError` with the step
  index and current buffer window.
- **FULL trace mode with post-hoc analysis:** callers who need to materialize refs across
  the full run must set `trace_ring_buffer_size >= total_steps`, or collect and render refs
  within the buffer window during the run.

### 12.3 Run Provenance

Every run manifest must include:

- pyWorldX version,
- git commit or equivalent code hash,
- scenario hash,
- ensemble seed bundle if used,
- parameter registry version,
- data connector vintages and proxy methods,
- `CrossValidationConfig` snapshot (including whether `NEBEL_2023_CALIBRATION_CONFIG` was used),
- ontology registry version,
- active sectors and versions,
- active sub-step integrators per sector,
- calibration report reference (including identifiability screen results),
- wall-clock runtime and environment metadata.

### 12.4 Forecast Report Artifact

A compact machine-readable report must be emitted for each run or ensemble, suitable for
dashboards and notebooks.

---

## 13. Validation Strategy

### 13.1 World3-03 Historical Validation

Target: reproduce Nebel et al. (2023) `Recalibration23` result.

Pass criterion: total NRMSD <= 0.2719 on the **1970–2020** training window.

**This bound is only reproducible using `NEBEL_2023_CALIBRATION_CONFIG` (Section 9.4) and
the `nrmsd_direct` mean-normalization and `nrmsd_change_rate` annual-pct-change formulations
defined in Section 9.1. Any deviation in config or metric formula makes this table
non-reproducible.**

Individual variable upper bounds (inherited from Nebel et al. 2023; represent the best fit
achievable with World3-03's structural equations against the proxy series used, not
independently verified production tolerances):

| Variable | Upper bound | NRMSD function |
|---|---|---|
| Population | 0.019 | direct |
| Industrial output | 0.474 | change-rate |
| Food per capita | 1.108 | change-rate |
| CO2 / Pollution | 0.337 | change-rate |
| Non-renewable resources | 0.757 | change-rate |
| Service per capita | 0.619 | change-rate |
| Human welfare (HDI) | 0.178 | direct |
| Ecological footprint | 0.343 | direct |

### 13.2 Sector-Level Unit Tests

Each sector must have tests for:

- unit consistency,
- sign and monotonicity of key responses where theoretically expected,
- nonnegative stock guards where appropriate,
- declared algebraic loop convergence.

### 13.3 Validation Status Tags

| Sector | EquationSource | ValidationStatus | WORLD7Alignment |
|---|---|---|---|
| Population | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |
| Capital | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |
| Agriculture | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |
| Non-renewable resources | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |
| Pollution | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |
| Adaptive technology | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |
| Welfare (HWI, EF) | MEADOWS_SPEC | REFERENCE_MATCHED | NONE |

### 13.4 Ensemble Validation

- deterministic equivalence when all perturbation widths are zero,
- stable percentile summaries under repeated seeded execution,
- correct threshold counting on synthetic fixtures.

### 13.5 Regression Tests

Known reference scenarios must be pinned in CI so accidental structural drift is caught
immediately.

---

## 14. Sector Library — v1.0 (World3-03)

World3-03 compatibility is the baseline. All 0.2.9 sectors must be verified against
reconstructed World3 behavior.

---

## 15. Sector Library — v1.1 (WILIAM Economy Adapter)

### 15.1 Multi-Rate Sub-stepping Contract

The WILIAM economy adapter sector expresses intent for multi-rate execution via
`WiliamAdapterConfig.substep_ratio`. At engine initialization, when the master `dt` is
known, the sector exposes its `timestep_hint` as a computed property:

```python
@property
def timestep_hint(self) -> float:
    return self.master_dt / self.config.substep_ratio
```

The engine's `resolve_substep_ratio(master_dt, sector.timestep_hint)` is then called
on this computed value exactly as for any other sector. The single validation path is never
bypassed. If `substep_ratio` does not evenly divide `master_dt`, `IncompatibleTimestepError`
is raised at init.

Recommended default rationale: WILIAM's annual accounting cycle uses quarterly internal
investment and depreciation flows. A 4:1 ratio (0.25 yr substep beneath 1.0 yr master
step) preserves smooth interpolation of capital stock transitions that would otherwise
alias at annual resolution. This is a numerical stability argument, not an empirical
frequency argument. If the master step is changed from 1.0 yr, `substep_ratio` should be
re-evaluated to maintain substep <= 0.25 yr.

```python
@dataclass
class WiliamAdapterConfig:
    substep_ratio: int = 4
    price_base_year: int = 2015
    price_base_currency: str = "EUR"
```

### 15.2 Integration Strategy

Adapter may expose WILIAM-derived variables as pyWorldX pseudo-sectors. Ontology layer
mediates naming differences. Price base year: 2015 constant euros.

### 15.3 Capital Stock Mapping

Adapter must support mapping of global capital stock categories into canonical pyWorldX
economic entities, preserving unit notes and price-base metadata.

### 15.4 Military and Criminal Capital Treatment

Represented as distinct economic allocations or folded into broader capital accounting; the
choice must be explicit and documented.

### 15.5 Investment Allocation Equations

Investment allocation logic must be adapter-visible and parameterized, not hidden in opaque
preprocessing.

### 15.6 Variable Name Adapter

A verified mapping table is required between WILIAM names and pyWorldX ontology entities.

---

## 16. Sector Library — v2.0-Ready Interfaces

Not active 0.2.9 build requirements. Interfaces must not block them.

### 16.1 Energy Module

Reserve interface slots for primary energy production, EROI variables, and energy-capital
coupling.

### 16.2 Metals Sectors

Reserve ontology entities for physically distinct mineral stocks and extraction flows.

### 16.3 Society, Governance, Military

Reserve interface hooks for institutional and coercive-capacity sectors without implementing
them in 0.2.9.

---

## 17. Canonical Test World

### 17.1 Model Definition

The canonical test world is a compact multi-sector R-I-P model designed to exercise two
distinct engine capabilities **independently**:

1. **The algebraic loop resolver** — via a mutual I<->P dependency within the single-rate domain.
2. **The multi-rate scheduler** — via Sector R sub-stepped at 4:1 beneath the master step.

These are deliberately separated. The R<->I coupling crosses the multi-rate boundary and is
therefore a **delayed coupling** (frozen last-known values), not a simultaneous loop. The
loop resolver is only invoked for the I<->P cycle.

**Sector R (Resources) — sub-stepped at 4:1:**

```
Stock:      R (resource units, initial=1000)
Flow:       extraction_rate = k_ext * R * industrial_output * (1 - pollution_fraction)
native_dt:  0.25 yr  (timestep_hint=0.25; substep_ratio=4 at master dt=1.0)
Reads:      industrial_output, pollution_fraction (frozen at last master-step boundary)
Writes:     R, extraction_rate
```

**Sector I (Industry) — single-rate:**

```
Stock:      K (capital units, initial=100)
Flows:      investment   = alpha * industrial_output
            depreciation = delta * K
Auxiliary:  industrial_output = A * K^beta * extraction_rate^(1-beta)
                                  * capital_productivity_factor(pollution_efficiency)
            where: capital_productivity_factor(pe) = pe
            (linear passthrough — pollution efficiency directly scales output,
             no additional parameters)
Reads:      extraction_rate (from R at communication boundary)
            pollution_efficiency (from P — SIMULTANEOUS, forms I<->P algebraic loop)
Writes:     K, industrial_output
```

**Sector P (Pollution) — single-rate:**

```
Stock:      P (pollution units, initial=0)
Flows:      pollution_inflow  = mu * industrial_output
            pollution_outflow = P / tau_p
Auxiliary:  pollution_fraction   = P / (P + P_half)   [Hill function — stiff transition]
            pollution_efficiency = 1 - gamma * pollution_fraction
                                   [SIMULTANEOUS input to I — forms I<->P algebraic loop]
Reads:      industrial_output (from I — SIMULTANEOUS, forms I<->P algebraic loop)
Writes:     P, pollution_fraction, pollution_efficiency
native_dt:  None  (runs at master step)
```

**I<->P Algebraic Loop:**

- I requires `pollution_efficiency` from P to compute `industrial_output`.
- P requires `industrial_output` from I to compute `pollution_inflow` and
  `pollution_efficiency`.
- This is a simultaneous intra-single-rate-domain loop, resolvable by fixed-point iteration.

Parameters:

```
k_ext=0.01, alpha=0.2, delta=0.05, A=1.0, beta=0.7,
mu=0.1, tau_p=20.0, P_half=500.0, gamma=0.3
dt=1.0, t_start=0, t_end=200
```

### 17.2 Required Test Fixtures

The canonical fixture must exercise each capability explicitly:

- **Algebraic loop resolver:** the I<->P mutual dependency within the single-rate domain.
- **Multi-rate scheduler:** Sector R with `timestep_hint=0.25` and `substep_ratio=4`.
- **Stiff transition:** Hill function in Sector P near P=500.
- **Analytical mini-case:** isolated exponential decay for integrator correctness.
- **Deterministic World3-aligned smoke test.**
- **Scenario bundle regression test.**
- **Zero-width ensemble equivalence test.**
- **Threshold probability synthetic test.**

### 17.3 Reference Trajectory

```
Stored as:              tests/canonical/reference_trajectory.csv
XMILE source:           tests/canonical/rip_canonical.xmile
Generator:              PySD==3.14.0; see tests/canonical/generate_reference.py
Pinned dependencies:    tests/canonical/requirements-canonical.txt
Columns:                [t, R, K, P, extraction_rate, industrial_output,
                         pollution_fraction, pollution_efficiency]
Update policy:          FROZEN. Any change requires documented rationale and
                        version increment.
```

`rip_canonical.xmile` must encode the Section 17.1 R-I-P model exactly, with all parameters
set to the values listed above, including `capital_productivity_factor(pe) = pe`.

`generate_reference.py` must be a standalone script that:

1. reads `requirements-canonical.txt` and asserts the installed PySD version matches,
2. loads `rip_canonical.xmile` via PySD,
3. runs the simulation,
4. writes `reference_trajectory.csv` with a header comment recording PySD version, xmile
   sha256, and generation timestamp.

`requirements-canonical.txt` must pin `PySD==3.14.0` and all of its transitive dependencies
at exact versions. Any PySD upgrade that changes default integrator behavior or table
interpolation must produce a new pinned version and a new FROZEN reference trajectory with
documented rationale.

### 17.4 Pass Criteria

All tolerances are normative and must be reproduced in CI fixture files. No CI configuration
may silently relax them without a corresponding spec revision.

**Integration test (full canonical model):**

```
max over all (t, variable) of:
    |pyWorldX_value - reference_value| / |reference_value| < 1e-4
```

**Closed-form analytical sub-case:**

Configuration: `pollution_inflow=0`, `pollution_outflow=P/tau_p`, `P(0)=100`, `tau_p=20.0`,
`t_end=200`.

Analytical solution: `P(t) = 100 * exp(-t / tau_p)`

Pass criterion (hybrid, to avoid ill-conditioned relative error near zero):

- For `t <= 100` (where `P(t) >= 100 * exp(-5) ≈ 6.74e-3`):
  max relative error `< 1e-4`
- For `t > 100` (where `P(t)` falls below `~6.74e-3` and relative error is
  numerically ill-conditioned):
  max absolute error `< 1e-6`

**Historical World3 validation (using `NEBEL_2023_CALIBRATION_CONFIG`):**

- Total NRMSD <= 0.2719 on the 1970–2020 training window.
- Variable-level upper bounds as listed in Section 13.1.

---

## 18. Metadata Reference

### 18.1 EquationSource

```python
class EquationSource(Enum):
    MEADOWS_SPEC = "meadows_spec"
    WORLD3_RECONSTRUCTED = "world3_reconstructed"
    EMPIRICAL_FIT = "empirical_fit"
    ADAPTER_DERIVED = "adapter_derived"
    SYNTHESIZED_FROM_PRIMARY_LITERATURE = "synthesized_from_primary_literature"
    PLACEHOLDER = "placeholder"
```

### 18.2 ValidationStatus

```python
class ValidationStatus(Enum):
    REFERENCE_MATCHED = "reference_matched"
    EMPIRICALLY_ANCHORED = "empirically_anchored"
    STRUCTURAL_PLACEHOLDER = "structural_placeholder"
    EXPERIMENTAL = "experimental"
```

### 18.3 WORLD7Alignment

```python
class WORLD7Alignment(Enum):
    DIRECT = "direct"
    APPROXIMATE = "approximate"
    NONE = "none"
```

### 18.4 UncertaintyType

*Reproduced from Section 10.2 for reference. Section 10.2 is authoritative.*

```python
class UncertaintyType(Enum):
    PARAMETER = "parameter"
    SCENARIO = "scenario"
    EXOGENOUS_INPUT = "exogenous_input"
    INITIAL_CONDITION = "initial_condition"
    STRUCTURAL_NOTE = "structural_note"
```

### 18.5 DistributionType

*Authoritative definition. See Section 10.3 for usage context.*

```python
class DistributionType(Enum):
    UNIFORM = "uniform"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    TRUNCATED_NORMAL = "truncated_normal"
```

### 18.6 PolicyShape

*Authoritative definition. See Section 11.1 for usage context.*

```python
class PolicyShape(Enum):
    STEP = "step"
    RAMP = "ramp"
    PULSE = "pulse"
    CUSTOM = "custom"
```

---

## 19. Deferred Items

Deferred beyond 0.2.9:

- 12-region spatial disaggregation,
- trade and migration flow networks,
- heterogeneous households / firms / states,
- tipping-point SDE modules and cascade propagation,
- endogenous Wright's-law technology learning,
- NeuralODE or other learned surrogate registry,
- MCMC / SMC posterior calibration,
- real-time assimilation via Ensemble Kalman Filter.

---

## 20. Implementation Sequence

Recommended order:

1. Core quantities, state container, and sector contract (including `preferred_substep_integrator` metadata field).
2. Deterministic integrator with `resolve_substep_ratio()` validation; sub-step RK4 default enforced.
3. Ontology registry and adapter boundary definitions.
4. Dependency graph, loop detection / resolution, and balance auditor.
5. World3 v1.0 sectors with canonical test world (I<->P loop + R multi-rate).
6. Data connectors and transformation pipeline.
7. Calibration metrics (`nrmsd_direct` with mean-normalization, `nrmsd_change_rate` with
   annual-pct-change transform), profile-likelihood screen, Morris screening, and parameter
   registry. Export `NEBEL_2023_CALIBRATION_CONFIG` from `calibration_config.py`.
8. Scenario dataclasses with `PolicyShape` enum, typed policy events, and parallel runner.
9. Provenance and trace system with `CausalTraceRef` / `CausalTrace` two-type pattern
   and ring buffer contract.
10. Ensemble wrapper, summaries, pre-declared threshold queries, and uncertainty decomposition.
    `ParameterDistribution` uses `DistributionType` enum.
11. WILIAM adapter v1.1 integration with computed `timestep_hint` property and
    `resolve_substep_ratio()` validation at init.
12. CI validation harness and regression fixtures. Pin `PySD==3.14.0` in
    `requirements-canonical.txt`. Commit `rip_canonical.xmile` with
    `capital_productivity_factor(pe) = pe` encoded exactly.

### 20.1 Release Gate Checklist

Before tagging 0.2.9, confirm:

- [ ] Unit-safe execution across all active sectors
- [ ] Canonical ontology mapping table committed
- [ ] World3 historical validation report generated with total NRMSD <= 0.2719
      using `NEBEL_2023_CALIBRATION_CONFIG` (train_end=2020)
- [ ] `nrmsd_direct` uses mean-normalization; `nrmsd_change_rate` uses annual-pct-change transform
- [ ] Profile likelihood screen run for all IDENTIFIABILITY_RISK parameters
- [ ] CrossValidationConfig (including named constant used) recorded in provenance manifest
- [ ] Scenario API uses `PolicyShape` enum; no raw string literals in `PolicyEvent.shape`
- [ ] Ensemble API uses `DistributionType` enum; no raw string literals in `ParameterDistribution.dist_type`
- [ ] Ensemble API documented with pre-declared ThresholdQuery examples
- [ ] CausalTraceRef / CausalTrace two-type pattern implemented and exercised
- [ ] Ring buffer contract implemented; StaleTraceRefError tested
- [ ] resolve_substep_ratio() validated at init; IncompatibleTimestepError tested
- [ ] WILIAM sector exposes computed timestep_hint property; resolve_substep_ratio() called on it
- [ ] I<->P algebraic loop in canonical test world exercising the loop resolver
- [ ] Sector R sub-stepped at 4:1 exercising the multi-rate scheduler
- [ ] Sub-step integrator defaults to RK4; Euler requires explicit opt-in via metadata
- [ ] capital_productivity_factor(pe) = pe encoded in rip_canonical.xmile and verified
- [ ] reference_trajectory.csv generated with PySD==3.14.0; sha256 and timestamp in header
- [ ] requirements-canonical.txt committed with PySD==3.14.0 pinned
- [ ] Analytical sub-case hybrid pass criterion implemented (relative t<=100, absolute t>100)
- [ ] Provenance manifest emitted for every run
- [ ] WILIAM adapter mapping verified
- [ ] CI passing on deterministic and ensemble regression tests
- [ ] `latest.md` symlink resolves to pyWorldX_spec_0.2.9.md

---

## Closing Note

0.2.9 is the first version of this spec that is fully self-contained: every function
formula is defined inline, every named config constant is explicit, every type is an Enum,
every sub-step integrator decision is documented, and every validation bound is reproducible
from the spec alone without consulting external papers. The canonical test world can now be
independently implemented and verified by any developer reading only this document.
