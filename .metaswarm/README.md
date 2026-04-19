# Metaswarm Configuration

This directory contains metaswarm configuration and development utilities for pyWorldX.

## Files

- **`project-profile.json`** — Project configuration (language, test runner, coverage thresholds, etc.)
- **`KNOWLEDGE_BASE.md`** — Project architecture, patterns, and important decisions
- **`scripts/`** — Utility scripts for common development tasks

## Quick Start

### Setup
```bash
poetry install
poetry install -E pipeline  # if using data pipeline
```

### Development Workflow

1. **Write tests first (TDD)**
   ```bash
   # Edit tests/test_*.py
   ```

2. **Implement code**
   ```bash
   # Edit pyworldx/*.py
   ```

3. **Run validation**
   ```bash
   ./.metaswarm/scripts/validate.sh
   ```

### Common Commands

**Run tests with coverage:**
```bash
./.metaswarm/scripts/test-with-coverage.sh
```

**Full validation (tests + type checking + linting):**
```bash
./.metaswarm/scripts/validate.sh
```

**Type check only:**
```bash
.venv/bin/python -m mypy pyworldx
```

**Lint only:**
```bash
.venv/bin/python -m ruff check pyworldx
```

## Requirements

- **Coverage**: 90%+ (enforced in CI)
- **Type Checking**: mypy strict mode
- **Linting**: ruff with project config
- **Python**: 3.11+

## GitHub Actions

CI pipeline automatically:
- Runs all tests with coverage check
- Validates mypy strict mode
- Runs ruff linting
- Enforces 90% coverage threshold

All checks must pass before merging PRs.

## See Also

- **[CLAUDE.md](../CLAUDE.md)** — Development guide for Claude Code
- **[README.md](../README.md)** — Project overview
- **[pyproject.toml](../pyproject.toml)** — Poetry configuration
