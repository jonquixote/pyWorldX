#!/bin/bash
# Run tests with coverage report
set -e

VENV_PYTHON=".venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    echo "Run: poetry install"
    exit 1
fi

echo "Running tests with coverage..."
$VENV_PYTHON -m pytest \
    --cov=pyworldx \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-fail-under=90 \
    "$@"

echo ""
echo "Coverage report generated in htmlcov/"
