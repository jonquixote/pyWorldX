"""CLI entry point: python -m pyworldx.cli.audit [--aligned-dir PATH]

Audits unit consistency of aligned Parquet targets against the
ENTITY_TO_ENGINE_MAP. Exits 0 if all entities are unit-safe,
exits 1 if any UNIT_MISMATCH entries are found.

Usage:
    python -m pyworldx.cli.audit --aligned-dir output/aligned
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyworldx.calibration.metrics import CrossValidationConfig
from pyworldx.data.bridge import DataBridge, DataBridgeError


def _build_audit_report(bridge: DataBridge) -> list[dict[str, str]]:
    """Inspect the entity map and classify each entity's unit status."""
    report: list[dict[str, str]] = []
    for entity, entry in bridge.entity_map.items():
        engine_var = entry.get("engine_var", "")
        unit = entry.get("unit", "")
        unit_mismatch = entry.get("unit_mismatch", False)
        excluded = entry.get("excluded_from_objective", False)

        if unit_mismatch:
            status = "UNIT_MISMATCH"
            detail = f"engine_var={engine_var} unit={unit} [excluded_from_objective={excluded}]"
        elif excluded:
            status = "EXCLUDED"
            detail = f"engine_var={engine_var} unit={unit} [not in objective]"
        elif not engine_var:
            status = "NO_ENGINE_VAR"
            detail = f"unit={unit}"
        else:
            status = "OK"
            detail = f"engine_var={engine_var} unit={unit}"

        report.append({"entity": entity, "status": status, "detail": detail})

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit unit consistency of aligned Parquet targets."
    )
    parser.add_argument(
        "--aligned-dir",
        type=Path,
        default=Path("output/aligned"),
        help="Path to aligned Parquet store (default: output/aligned)",
    )
    args = parser.parse_args()

    bridge = DataBridge(
        aligned_dir=args.aligned_dir,
        config=CrossValidationConfig(),
    )

    try:
        report = _build_audit_report(bridge)
    except DataBridgeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    mismatches: list[dict[str, str]] = []
    for row in report:
        status = row["status"]
        print(f"[{status:<14}] {row['entity']:<50}  {row.get('detail', '')}")
        if status == "UNIT_MISMATCH":
            mismatches.append(row)

    print()
    if mismatches:
        print(f"{len(mismatches)} UNIT_MISMATCH(es) found:", file=sys.stderr)
        for row in mismatches:
            print(f"  - {row['entity']}: {row['detail']}", file=sys.stderr)
        return 1

    total = len(report)
    excluded = sum(1 for r in report if r["status"] == "EXCLUDED")
    ok = sum(1 for r in report if r["status"] == "OK")
    print(f"All entities unit-safe. ✓  ({ok} OK, {excluded} excluded, {total} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
