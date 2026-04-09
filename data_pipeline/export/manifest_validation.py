"""Manifest schema validation — ensures data manifests are well-formed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Expected manifest schema
MANIFEST_SCHEMA = {
    "required_fields": [
        "generated_at",
        "pipeline_version",
        "sources",
        "aligned_entities",
    ],
    "source_fields": {
        "version": str,
        "fetched_at": str,
        "checksum_sha256": str,
        "records_fetched": int,
        "url": str,
        "format": str,
    },
    "entity_fields": {
        "source_id": str,
        "year_min": int,
        "year_max": int,
        "records": int,
        "unit": str,
    },
}


def validate_manifest(manifest_path: Path) -> dict[str, list[str]]:
    """Validate a data manifest against the schema.
    
    Args:
        manifest_path: Path to the manifest JSON file.
    
    Returns:
        Dict with "errors" and "warnings" lists.
    """
    errors = []
    warnings = []
    
    # Check file exists
    if not manifest_path.exists():
        errors.append(f"Manifest file not found: {manifest_path}")
        return {"errors": errors, "warnings": warnings}
    
    # Load JSON
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return {"errors": errors, "warnings": warnings}
    
    # Check required top-level fields
    for field in MANIFEST_SCHEMA["required_fields"]:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
    
    # Validate sources
    if "sources" in manifest:
        sources = manifest["sources"]
        if not isinstance(sources, dict):
            errors.append("'sources' should be a dict")
        else:
            for source_id, info in sources.items():
                if not isinstance(info, dict):
                    errors.append(f"Source '{source_id}' info should be a dict")
                    continue
                for field, field_type in MANIFEST_SCHEMA["source_fields"].items():
                    if field not in info:
                        warnings.append(f"Source '{source_id}' missing field: {field}")
                    elif not isinstance(info[field], field_type):
                        warnings.append(
                            f"Source '{source_id}' field '{field}' has wrong type: "
                            f"expected {field_type.__name__}, got {type(info[field]).__name__}"
                        )
    
    # Validate aligned entities
    if "aligned_entities" in manifest:
        entities = manifest["aligned_entities"]
        if not isinstance(entities, dict):
            errors.append("'aligned_entities' should be a dict")
        else:
            for entity, info in entities.items():
                if not isinstance(info, dict):
                    errors.append(f"Entity '{entity}' info should be a dict")
                    continue
                for field, field_type in MANIFEST_SCHEMA["entity_fields"].items():
                    if field not in info:
                        warnings.append(f"Entity '{entity}' missing field: {field}")
    
    return {"errors": errors, "warnings": warnings}


def validate_manifest_directory(manifest_dir: Path) -> dict[str, Any]:
    """Validate all manifests in a directory.
    
    Args:
        manifest_dir: Directory containing manifest JSON files.
    
    Returns:
        Dict with per-manifest validation results.
    """
    results = {}
    
    if not manifest_dir.exists():
        return {"error": f"Directory not found: {manifest_dir}"}
    
    for manifest_file in manifest_dir.glob("*.json"):
        results[manifest_file.name] = validate_manifest(manifest_file)
    
    return results
