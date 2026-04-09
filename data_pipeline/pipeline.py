"""pyWorldX Data Pipeline — Master pipeline orchestrator.

Coordinates all stages: collect → validate → transform → align → quality → export.
Enforces the transform dependency DAG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from data_pipeline.config import PipelineConfig
from data_pipeline.storage.metadata_db import init_db, record_transform
from data_pipeline.storage.parquet_store import list_sources, list_entities


# Transform dependency DAG
TRANSFORM_DEPENDENCIES: dict[str, list[str]] = {
    "reshape": [],                    # No deps — always runs first
    "interpolation": ["reshape"],     # Needs long format
    "aggregation": ["reshape"],       # Can run in parallel with interpolation
    "deflation": ["reshape"],         # BUT requires world_bank raw data (validated at runtime)
    "per_capita": ["reshape"],        # Runtime check: population series must be in raw store
    "unit_conversion": ["deflation"], # Constant prices before unit harmonization
    "gap_detection": [                # Runs on final clean data
        "interpolation", "aggregation",
        "per_capita", "unit_conversion",
    ],
    "outlier_detection": ["gap_detection"],  # Last — runs on flagged data
    "nebcal_transform": [             # Needs raw supplement + deflator
        "reshape",
    ],  # Runtime check: world_bank deflator must be in raw store
}

# Runtime data requirements (source IDs that must exist in raw store)
RUNTIME_DATA_REQUIREMENTS: dict[str, list[str]] = {
    "deflation": ["world_bank_NY.GDP.DEFL.KD.ZG"],
    "per_capita": ["world_bank_SP.POP.TOTL"],
    "nebcal_transform": [
        "world_bank_NY.GDP.MKTP.CD",
        "world_bank_NY.GDP.DEFL.KD.ZG",
    ],
}


def validate_transform_dependencies(
    transform_name: str,
    completed_transforms: list[str],
    raw_dir: Path,
) -> tuple[bool, list[str]]:
    """Check if a transform can be executed.

    Args:
        transform_name: Name of the transform to validate.
        completed_transforms: List of transforms that have completed successfully.
        raw_dir: Path to the raw store (for data requirement checks).

    Returns:
        Tuple of (can_run, reasons) where reasons explains any blockers.
    """
    deps = TRANSFORM_DEPENDENCIES.get(transform_name, [])
    reasons = []

    # Check transform dependencies
    for dep in deps:
        if dep not in completed_transforms:
            reasons.append(f"Missing transform dependency: {dep}")

    # Check runtime data requirements
    data_reqs = RUNTIME_DATA_REQUIREMENTS.get(transform_name, [])
    available_sources = set(list_sources(raw_dir))
    for req in data_reqs:
        if req not in available_sources:
            reasons.append(f"Missing source data: {req}")

    can_run = len(reasons) == 0
    return can_run, reasons


def run_transform_pipeline(
    config: PipelineConfig,
    transform_registry: dict[str, Callable],
) -> dict[str, Any]:
    """Run the full transform pipeline with dependency validation.

    Args:
        config: Pipeline configuration.
        transform_registry: Dict mapping transform names to callables.
            Each callable takes (df, config) and returns a DataFrame.

    Returns:
        Dict with results, warnings, and errors.
    """
    init_db(config.metadata_db)

    completed: list[str] = []
    skipped: list[str] = []
    errors: dict[str, str] = {}
    results: dict[str, pd.DataFrame] = {}

    # Topological sort based on dependencies
    order = _topological_sort(TRANSFORM_DEPENDENCIES)

    for transform_name in order:
        can_run, reasons = validate_transform_dependencies(
            transform_name,
            completed,
            config.raw_dir,
        )

        if not can_run:
            skipped.append(transform_name)
            for reason in reasons:
                print(f"  ⚠️ Skipping {transform_name}: {reason}")
            continue

        if transform_name not in transform_registry:
            skipped.append(transform_name)
            continue

        try:
            transform_fn = transform_registry[transform_name]
            result = transform_fn(config)
            results[transform_name] = result
            completed.append(transform_name)
            print(f"  ✅ {transform_name}")
        except Exception as e:
            errors[transform_name] = str(e)
            print(f"  ❌ {transform_name}: {e}")

    return {
        "completed": completed,
        "skipped": skipped,
        "errors": errors,
        "results": results,
    }


def _topological_sort(
    dependencies: dict[str, list[str]],
) -> list[str]:
    """Topological sort of transform names.

    Args:
        dependencies: Dict mapping transform names to their dependencies.

    Returns:
        List of transform names in execution order.
    """
    visited = set()
    order = []

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        for dep in dependencies.get(name, []):
            visit(dep)
        order.append(name)

    for name in dependencies:
        visit(name)

    return order
