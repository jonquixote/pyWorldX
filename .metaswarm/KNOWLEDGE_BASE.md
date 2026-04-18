# pyWorldX Knowledge Base

## Project Architecture

### Core Concepts
- **Unit Safety**: Physical units are tracked throughout calculations to prevent dimensional errors
- **Auditability**: All calculations must be traceable and verifiable
- **Modularity**: Components are designed to be independently testable and composable

### Key Modules

#### Main Package (`pyworldx/`)
Core forecasting platform for global systems modeling.

#### Data Pipeline (`data_pipeline/`)
Optional module for data ingestion, transformation, and preprocessing. Requires pipeline extras to be installed.

## Code Patterns

### Type Annotations
- All public APIs must have complete type hints
- Private functions should have type hints where they aid clarity
- Use `from typing import TYPE_CHECKING` for circular imports
- Pydantic models preferred for data validation

### Testing Patterns
- **TDD First**: Write tests before implementation
- **Isolation**: Unit tests should be independent and fast
- **Network Tests**: Mark with `@pytest.mark.network` if they require external calls
- **Fixtures**: Keep fixtures in `conftest.py` at appropriate directory levels

### Error Handling
- Use specific exception types (not generic `Exception`)
- Document error conditions in docstrings
- Provide actionable error messages

## mypy Strict Mode Exceptions

Two modules have mypy assignment errors disabled:
- `pyworldx.data.transforms.normalization`
- `pyworldx.data.bridge`

These are temporary exceptions. Aim to remove them by improving type annotations in those modules.

## Important Decisions

### Testing with Python venv
- Always use `.venv/bin/python -m pytest` instead of `poetry run pytest` or bare `python`
- This ensures proper isolation and accurate error reporting
- Tests run within the isolated environment

### Coverage Target (90%+)
- This is a high standard but appropriate for a scientific computing platform
- Focus on testing the core logic and edge cases
- Integration tests can count toward coverage

## CI/CD Integration

GitHub Actions pipeline validates:
- ✓ All tests pass
- ✓ Coverage >= 90%
- ✓ mypy strict mode passes
- ✓ ruff lint checks pass

PR merges require all checks to pass.

## Development Utilities

### Quick Test & Coverage
```bash
./.metaswarm/scripts/test-with-coverage.sh
```

### Full Validation
```bash
./.metaswarm/scripts/validate.sh
```

### Manual Commands
```bash
# Tests only
.venv/bin/python -m pytest

# Type checking
.venv/bin/python -m mypy pyworldx

# Linting
.venv/bin/python -m ruff check pyworldx
```

## Recent Notes

- Project uses Poetry for reproducible environments
- Python 3.11+ required
- Pandas, NumPy, and Pydantic are core dependencies
- Pipeline functionality is optional but heavily used in practice

---

## Phase 2 Remediation Learnings (2026-04-17)

### Sector API Gotchas

**ResourcesSector takes no constructor arguments.**
`ResourcesSector(policy_year=0.0)` raises `TypeError`. Set class-level attributes after construction:

```python
s = ResourcesSector()
s.policy_year = 0.0
s.fcaor_switch_time = 0.0
```

**`compute()` returns derivatives, not stocks.**
`compute(t, stocks, inputs, ctx)` returns `{"d_NR": ..., "extraction_rate": ...}`.
The stock `NR` is an *input* (via `stocks` dict). Assert `"d_NR" in out`, not `"NR" in out`.

**PolicyEvent STEP is a silent no-op if the key is absent from shared state.**
The engine only applies `policy_applier` to keys that already exist in `shared` and are not stocks. `supply_multiplier_fossil` and similar multipliers are not in shared state unless CentralRegistrar emits them. STEP/RAMP events on these keys have no effect in tests that don't use CentralRegistrar.

**GiniDistributionSector is redistributive in abundance.**
At high FPC (food_scarcity ≈ 1.0), `top10_weight=0.10`, `bot90_weight=0.90`; after per-capita normalization (`/ 0.1` and `/ 0.9`), `bot90_per_capita > top10_per_capita`. The intuitive expectation (top10 always gets more) is wrong at abundance. Scarcity pushes inequality upward; abundance equalizes or inverts it.

**PhosphorusSector dissipation dominates at default parameters.**
Default: `sedimentation_rate=0.002`, `P_soc=14000` → dissipation = 28 > profitability_factor cap of 2.0.
To test the profitability-driven PRR increase mechanism in isolation, set `sedimentation_rate=0.0`.

### Trajectory Behavior (counter-intuitive)

**GHG stock falls in the first decades of a 200-year run.**
At 1900, natural sinks exceed emissions. `ghg_stock` falls from ~600 GtC before rising later.
Tests must assert `ghg_stock >= 0` (non-negative), not "rises monotonically".

**Pollution index is non-monotonic over 200 years.**
It falls 0.18 → 0.09 → 0.17; not monotone-increasing with industrial output.
Assert `pollution_index >= 0`, not `pollution_index[−1] > pollution_index[0]`.

**DRFM_top10 stays non-zero unless FPC > ~1885.**
Because `food_top10 = gini_weight × FPC / 0.1` and subsistence = 230, very high FPC is required for DRFM_top10 to reach 0. Don't assert DRFM=0 at FPC=600; assert it *declines* as FPC rises.

### Time System

**pyWorldX uses relative time t ∈ [0, 200], not absolute years 1900–2100.**

- `t = 0` → 1900, `t = 120` → 2020, `t = 200` → 2100
- `RunContext(t_start=0.0, t_end=200.0)` — always use relative bounds
- `calendar_year = t + 1900` (see `population.py:280`)

**Population sector time-threshold branches (_ZPGT/_FCEST/_PET) require t ≥ 2100.**
The constants are set to `calendar_year = 4000`, which corresponds to `t = 2100` (relative).
`t = 200.0` (relative) = year 2100 does NOT trigger these branches; only `t ≥ 2100.0` does.
Use `s.compute(2100.0, ...)` in tests targeting these branches.

### Climate / Physics Ordering

**Aerosol quasi-equilibrium must be computed before `rf_aero` in `climate.py`.**
Computing `rf_aero` before `aerosol_index` causes a cooling runaway: the stale previous-timestep aerosol value drives a compounding negative feedback. Commit `c1f046e` documents the correct ordering.

### Coverage

**`validation/regression_tests.py` and `validation/sector_tests.py` are expected low.**
These files (74% and 51% coverage) use network/data fixtures not available in unit tests.
They should be excluded from the unit coverage gate or covered in separate integration runs.
The hard gate in `.coverage-thresholds.json` (100%) conflicts with CLAUDE.md (90%);
`.coverage-thresholds.json` is the CI-blocking truth.

### Phase 3 Scope Boundary (explicitly deferred)

The following were scoped out of Phase 2 and must NOT be implemented until Phase 3:

- SEIR cohort aging (fraction-based stocks)
- Minsky growth-financing debt model
- CentralRegistrar Ability-to-Pay macro redesign
- Full `C_scale` connectivity severance for lifeboating
- N-region engine wrapper
- Dynamic phosphorus recycling control beyond static PRR floor
- Energy ceiling capital-investment semantics (Registrar redesign)
