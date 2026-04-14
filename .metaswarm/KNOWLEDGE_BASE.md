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
