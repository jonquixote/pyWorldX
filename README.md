# pyWorldX

Modular, unit-safe, auditable forecasting platform for long-horizon global systems modeling, compliant with the World3-03 specification.

## Overview

pyWorldX is an advanced Python rewrite of the classic World3 model (Meadows et al., 1972/2004), designed for modern computational science. It provides a robust, strictly typed, and auditable framework for global systems simulation, featuring:

- **Unit Safety**: Built on `Pint` for strict dimensional analysis across all operations, eliminating abstract scalar translation errors.
- **Algebraic Loop Resolution**: Automated detection and numerical resolution of dependency cycles.
- **Multi-rate Integration**: Supports `timestep_hint` sector configuration, allowing fast and slow dynamics to run at independent integration rates within a master orchestration step.
- **Auditable Provenance**: Emits structural `CausalTraceRef` objects to track variable state directly to underlying spec equations.
- **Real-World Data Pipelines**: Modular data ingestion mapping 32 API sources directly to pyWorldX ontology entities to support continuous automated recalibration.
- **Extensible Ontology**: A canonical variable namespace allowing external models (e.g., WILIAM IAM model) to interoperate modularly with core system dynamics.

## Quick Start
1. Ensure you have Python 3.11+ and [Poetry](https://python-poetry.org/) installed.
2. Clone the repository and navigate to the directory.
3. Install dependencies:
   ```bash
   # Core engine only
   poetry install

   # Core engine + data pipeline
   poetry install --extras pipeline
   ```
4. Run the test suite:
   ```bash
   poetry run pytest
   ```

## Data Pipeline

pyWorldX ships with a **reference data pipeline** that collects, transforms, and aligns real-world data from 37 sources (World Bank, NOAA, EDGAR, OWID, FRED, and more) into NRMSD-ready calibration series. The pipeline is optional — the core engine works with any data source that produces a `ConnectorResult` (see `pyworldx/data/connectors/base.py`).

Install with pipeline dependencies, then run:

```bash
poetry install --extras pipeline

# Collect data from all available sources
poetry run python -m data_pipeline collect

# Run the full pipeline (collect → transform → align → export → report)
poetry run python -m data_pipeline run

# Check pipeline status
poetry run python -m data_pipeline status
```

See [`data_pipeline/README.md`](data_pipeline/README.md) for full documentation, including how to add your own connectors.

## Repository Structure

- `pyworldx/core/`: The core simulation engine, including multi-rate scheduling (`multirate.py`), abstract dependencies (`graph.py`), balance auditing (`balance.py`), and snapshot tracing (`engine.py`).
- `pyworldx/sectors/`: Sub-model implementations (e.g., Capital, Population, Pollution, Resources, Agriculture, Adaptive Technology). Sub-models are strictly bounded via explicitly declared `reads`/`writes` namespaces.
- `pyworldx/ontology/`: A canonical dimensional alignment architecture governing standard variable naming schemas.
- `pyworldx/adapters/`: Interfaces for structural backward compatibility (e.g., World3Adapter) and interoperability with other IAM ecosystems (e.g., `wiliam/`).
- `pyworldx/calibration/`: Pipeline logic for NRMSD validation against historical targets, sensitivity analysis (Sobol, Morris), and dynamic threshold mapping.
- `data_pipeline/`: Reference data pipeline — 37 connectors, 9 transforms, ontology alignment, and NRMSD calibration export. Optional; install with `poetry install --extras pipeline`.
- `pyworldx/observability/`: Comprehensive recording logic, including runtime assertions, dependency provenance tracking, and reporting.

## Key Design Principles

1. **Strict Type Safety**: The codebase aims to be 100% `mypy --strict` compliant. Typing covers integration solvers, configuration dictionaries, and data flow.
2. **Explicit Interfaces**: Sectors cannot read the global namespace. They must specify explicitly every variable they consume externally.
3. **Immutability Boundaries**: Sectors are evaluated as deterministic steps (`rk4`, `euler`). Values are passed functionally; state is orchestrated at the `Engine` level.
4. **Transparent Calibration**: All structural equations map directly to their underlying source (e.g., `MEADOWS_SPEC`), tracked explicitly in the source metadata map.
5. **Specification Compliance**: Ground-truth correctness maps to the v0.2.9.0 detailed markdown specification logic. Validation bounds track tightly to the NRMSD standards.
