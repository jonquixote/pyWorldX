#!/bin/bash
# Full validation: tests, type checking, linting
set -e

VENV_PYTHON=".venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    echo "Run: poetry install"
    exit 1
fi

echo "==== Running Tests with Coverage ===="
$VENV_PYTHON -m pytest \
    --cov=pyworldx \
    --cov-report=term-missing \
    --cov-fail-under=90 \
    "$@"

echo ""
echo "==== Type Checking (mypy) ===="
$VENV_PYTHON -m mypy pyworldx

echo ""
echo "==== Linting (ruff) ===="
$VENV_PYTHON -m ruff check pyworldx

echo ""
echo "✓ All validations passed!"
