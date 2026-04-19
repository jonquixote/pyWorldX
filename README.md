# pyWorldX

**A Python platform for long-horizon global systems forecasting**, built on the World3-03
structural model (Meadows et al., 2004) and extended with empirical calibration, biophysical
sector extensions, and a 37-source real-world data pipeline.

> Calibrated against observed data · Auditable to the equation level · Ready for ensemble forecasting

[![CI](https://github.com/jonquixote/pyWorldX/actions/workflows/ci.yml/badge.svg)](https://github.com/jonquixote/pyWorldX/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen)](#development)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-blue)](http://mypy-lang.org/)

---

## What's Inside

| Module | What it does |
|---|---|
| **Core Engine** | RK4 + Euler multi-rate integration, algebraic loop resolution, sector isolation via explicit `reads`/`writes` namespaces |
| **World3 Sectors** | Capital, Population, Pollution, Resources, Agriculture, SEIR — fully spec-compliant with World3-03 |
| **Phase-2 Sectors** | 5-stock carbon cycle, thermodynamic EROI limits, ecosystem services thresholds, phosphorus cycle, human capital |
| **Empirical Calibration** | `DataBridge` → Optuna TPE Bayesian search → Morris screening → Nelder-Mead fine-tune, with train/validation holdout |
| **Data Pipeline** | 37 connectors (World Bank, FAOSTAT, BP Statistical Review, USGS, NOAA, EDGAR, FRED, OWID, and more) |
| **Ensemble Forecasting** | Monte Carlo + SALib Sobol variance decomposition (S1/ST) → compact `.parquet` output |
| **Observability** | Runtime assertions, dependency provenance tracking, balance auditing, snapshot tracing |

---

## Quick Start

**Requirements:** Python 3.11+, [Poetry](https://python-poetry.org/)

```bash
# 1. Clone and install
git clone https://github.com/jonquixote/pyWorldX
cd pyWorldX

poetry install                       # core engine only
poetry install --extras pipeline     # + data pipeline + Optuna/SALib analytics

# 2. Run the test suite
poetry run pytest tests/ -q

# 3. Run a scenario
poetry run python -c "
from pyworldx.scenarios import StandardRun
from pyworldx.presets import load_preset

scenario = StandardRun()
result = scenario.run(start=1970, end=2100)
print(result.summary())
"
```

**First empirical calibration run:**

```bash
# Fetch and align empirical data from all 37 sources
poetry run python -m data_pipeline run

# Audit unit consistency across all calibration targets
poetry run python -m pyworldx.data.bridge --audit-units

# Dry-run the calibrator — checks data coverage without running the optimizer
poetry run python -m pyworldx.calibration.empirical \
  --dry-run \
  --train-window 1970-2010 \
  --holdout-window 2010-2023
```

---

## What's New — Phase 2 Calibration (April 2026)

The `phase-2-calibration` branch completed the empirical grounding layer, making the
calibration pipeline numerically correct for the first time against real-world data.

**Tier 1 — Hard blockers fixed:**

- **Unit-safe entity map** — World3 reference trajectories are segregated from empirical
  targets in `ENTITY_TO_ENGINE_MAP`, eliminating silent NRMSD inflation from unit collisions
  (e.g., dimensionless pollution index vs. atmospheric CO₂ in ppm; kg/person/yr vs. kcal/capita/day).
- **FAOSTAT area code** — corrected world aggregate code from `"WLD"` → `"5000"`,
  restoring the full 1961–2013 Food Balance Sheet Historical series.
- **Initial conditions default year** — `get_initial_conditions()` now defaults to
  `CrossValidationConfig.train_start` dynamically; all literal `1970` integers replaced
  across `pyworldx/` and `data_pipeline/`.
- **BP Statistical Review connector** — proved fossil fuel reserves (1965–2023, EJ) provide
  the first empirical anchor for the nonrenewable resource sector.

**Tier 2 — Data quality:**

- **Deterministic source arbitration** — multi-source entities (`service_capital`,
  `industrial_capital`, `arable_land`) resolve via explicit priority waterfall, not
  Python dict iteration order.
- **Zero-guard normalization** — `DataBridge._normalize_to_index` handles zero base-year
  values with a ±5-year fallback and a typed `DataBridgeError` — no more silent `inf`/`NaN`
  propagation into NRMSD.
- **Parquet cache diagnostics** — missing cache now raises a `DataBridgeError` naming the
  exact connector and regeneration command; stale cache (>30 days) emits a `WARNING`.

See [`plans/2026-04-18-preflight-plan.md`](plans/2026-04-18-preflight-plan.md) for the full
TDD specification with failing tests, contracts, and gate commands for each fix.

---

## Calibration Architecture

pyWorldX implements a multi-stage calibration pipeline designed to avoid the common failure
modes of global search (overfitting, poor identifiability, silent unit errors).

```
Raw connectors (37 sources)
        │
        ▼
data_pipeline collect → transform → align → output/aligned/*.parquet
        │
        ▼
DataBridge.load_targets()
  · source priority arbitration
  · _normalize_to_index (zero-guard, ±5yr fallback)
  · train/validation window split
        │
        ▼
CrossValidationConfig  (train_start=1970, train_end=2010, validation_end=2023)
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  Stage 1: Structural Identifiability profiling           │
│  Stage 2: Morris elementary effects screening            │
│  Stage 3: Optuna TPE global Bayesian search              │
│  Stage 4: Bounded Nelder-Mead local fine-tune            │
└─────────────────────────────────────────────────────────┘
        │
        ▼
Ensemble: Monte Carlo + Saltelli sampling
  → SALib S1/ST Sobol decomposition
  → uncertainty buckets: Parameter / Exogenous / Initial Condition
  → output/ensemble/*.parquet
```

**Objective function:** Normalized RMSD (NRMSD) matching Nebel et al. 2023, evaluated
independently over the training window (1970–2010) and the holdout validation window (2010–2023).

---

## Data Pipeline

The reference pipeline collects, transforms, and aligns real-world time-series from 37 sources
into NRMSD-ready calibration targets. The core engine works with any data source that produces
a `ConnectorResult` — the pipeline is optional.

```bash
# Full pipeline run (collect → transform → align → export → report)
poetry run python -m data_pipeline run

# Individual stages
poetry run python -m data_pipeline collect    # fetch from all 37 sources
poetry run python -m data_pipeline status     # check connector health

# Inspect alignment output
ls output/aligned/*.parquet
```

**Source coverage:**

| Sector | Primary sources |
|---|---|
| Population | UN WPP, World Bank |
| Food / Agriculture | FAOSTAT Food Balance Sheet (1961–2013, 2014+), World Bank |
| Industrial & Service Capital | Penn World Table, World Bank Capital Stock |
| Nonrenewable Resources | BP Statistical Review of World Energy (1965–2023) |
| Pollution / Carbon | EDGAR, OWID, Global Carbon Budget |
| Arable Land | FAOSTAT Resource Land, World Bank Land |
| GDP / Development | Penn World Table, World Bank, Maddison Project |
| Energy | IEA, OWID, BP |
| Climate | NOAA, HadCRUT |
| Financial | FRED |

See [`data_pipeline/README.md`](data_pipeline/README.md) for full connector documentation,
including how to write your own connector.

---

## Repository Structure

```
pyWorldX/
│
├── pyworldx/
│   ├── core/           # Engine, multi-rate scheduler, algebraic loop resolver,
│   │                   # balance auditing, snapshot tracing
│   ├── sectors/        # World3 sectors (Capital, Population, Pollution, Resources,
│   │                   # Agriculture, SEIR) + Phase-2 sectors (Carbon, EROI,
│   │                   # Ecosystem Services, Phosphorus, Human Capital)
│   ├── calibration/    # DataBridge, CrossValidationConfig, Optuna TPE,
│   │                   # Morris screening, Nelder-Mead, initial_conditions
│   ├── forecasting/    # Monte Carlo ensemble runner, SALib Sobol decomposition,
│   │                   # scenario threshold queries
│   ├── scenarios/      # Scenario definitions (StandardRun, etc.)
│   ├── ontology/       # Entity registry and unit definitions
│   ├── observability/  # Runtime assertions, provenance tracking, reporting
│   ├── validation/     # Cross-sector constraint validation
│   ├── adapters/       # External format adapters
│   ├── config/         # Configuration schemas
│   └── presets.py      # Preset parameter bundles
│
├── data_pipeline/
│   ├── connectors/     # 37 source connectors
│   ├── transforms/     # 9 alignment transforms
│   ├── alignment/      # Ontology alignment logic
│   └── map.py          # ENTITY_TO_ENGINE_MAP + WORLD3_NAMESPACE
│
├── tests/
│   ├── unit/           # TDD unit tests (contracts from preflight plans)
│   └── integration/    # End-to-end calibration and scenario tests
│
└── plans/              # TDD preflight plans and implementation audit reports
```

---

## Key Design Principles

1. **Strict Type Safety** — `mypy --strict` throughout. Typing covers integration solvers,
   configuration dictionaries, calibration targets, and all data flow. Entity map values
   use `TypedDict` (not bare `dict[str, Any]`).

2. **Explicit Sector Interfaces** — Sectors cannot read the global namespace. Every external
   variable consumed must be declared explicitly via `reads`. Every variable written must be
   declared via `writes`. Undeclared access raises at construction time.

3. **Immutability Boundaries** — Sectors are evaluated as deterministic steps (`rk4`, `euler`).
   Values are passed functionally; state is orchestrated exclusively at the `Engine` level.

4. **Transparent Calibration** — All structural equations map to their source (e.g.,
   `MEADOWS_SPEC`), tracked in the source metadata map. Calibration targets are empirically
   grounded via unit-safe `ENTITY_TO_ENGINE_MAP`; World3 reference trajectories are confined
   to `WORLD3_NAMESPACE` and excluded from the objective function.

5. **Specification Compliance** — Ground-truth correctness maps to the v0.2.9.0 detailed
   markdown specification. Validation bounds track to NRMSD standards from Nebel et al. 2023.

6. **Fail Loud, Fail Early** — Missing pipeline data raises a typed `DataBridgeError` with
   the exact regeneration command. Unit mismatches are detected at entity-map construction
   time, not silently at NRMSD calculation time.

---

## Development

```bash
# Full validation (tests + mypy strict + ruff lint)
./.metaswarm/scripts/validate.sh

# Tests with coverage report (enforces ≥90% threshold)
./.metaswarm/scripts/test-with-coverage.sh

# Individual checks
poetry run mypy pyworldx           # type checking
poetry run ruff check pyworldx     # lint
poetry run pytest tests/ -x -q    # tests, stop on first failure
```

**CI enforces on every PR:**
- ≥90% test coverage
- `mypy --strict` passes with zero errors
- `ruff` lint passes with zero warnings
- All tests green — no regressions

**TDD workflow:** Preflight plans in `plans/` define failing tests → contracts → gate commands
for each feature. Write the failing test first, confirm it is RED, implement to the contract,
confirm the gate command is GREEN. No ticket is done until its gate passes *and* the full
unit suite stays green.

---

## References

- Meadows, D. H., Randers, J., & Meadows, D. L. (2004). *Limits to Growth: The 30-Year Update.*
- Forrester, J. W. (1971). *World Dynamics.*
- Nebel, B., et al. (2023). Revisiting the limits to growth after peak oil.
- BP Statistical Review of World Energy (2024 edition).
- FAOSTAT Food Balance Sheets Historical (1961–2013) and current (2014+).
