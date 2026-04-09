"""Tests for manifest schema validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from data_pipeline.export.manifest_validation import (
    validate_manifest,
    validate_manifest_directory,
    MANIFEST_SCHEMA,
)


@pytest.fixture
def valid_manifest():
    """Create a valid manifest dict."""
    return {
        "generated_at": "2026-04-08T00:00:00+00:00",
        "pipeline_version": "0.1.0",
        "sources": {
            "gcp_fossil_co2": {
                "version": "GCB2024v18",
                "fetched_at": "2026-04-08T00:00:00+00:00",
                "checksum_sha256": "abc123",
                "records_fetched": 23863,
                "url": "https://zenodo.org/...",
                "format": "csv",
            },
        },
        "aligned_entities": {
            "emissions.co2_fossil": {
                "source_id": "gcp_fossil_co2",
                "year_min": 1750,
                "year_max": 2023,
                "records": 274,
                "unit": "Mt_CO2",
            },
        },
    }


@pytest.fixture
def manifest_file(valid_manifest, tmp_path):
    """Create a temporary manifest file."""
    path = tmp_path / "manifest.json"
    with open(path, "w") as f:
        json.dump(valid_manifest, f)
    return path


class TestManifestSchema:
    """Tests for manifest schema definitions."""
    
    def test_has_required_fields(self):
        """Schema should define required fields."""
        assert "required_fields" in MANIFEST_SCHEMA
        assert "generated_at" in MANIFEST_SCHEMA["required_fields"]
        assert "sources" in MANIFEST_SCHEMA["required_fields"]
    
    def test_has_source_fields(self):
        """Schema should define source fields."""
        assert "source_fields" in MANIFEST_SCHEMA
        assert "version" in MANIFEST_SCHEMA["source_fields"]
        assert "records_fetched" in MANIFEST_SCHEMA["source_fields"]
    
    def test_has_entity_fields(self):
        """Schema should define entity fields."""
        assert "entity_fields" in MANIFEST_SCHEMA
        assert "year_min" in MANIFEST_SCHEMA["entity_fields"]
        assert "year_max" in MANIFEST_SCHEMA["entity_fields"]


class TestValidateManifest:
    """Tests for manifest validation function."""
    
    def test_valid_manifest_passes(self, manifest_file):
        """Valid manifest should have no errors."""
        result = validate_manifest(manifest_file)
        assert len(result["errors"]) == 0
    
    def test_missing_file_returns_error(self, tmp_path):
        """Missing file should return error."""
        result = validate_manifest(tmp_path / "nonexistent.json")
        assert len(result["errors"]) > 0
    
    def test_invalid_json_returns_error(self, tmp_path):
        """Invalid JSON should return error."""
        path = tmp_path / "bad.json"
        path.write_text("{invalid json")
        
        result = validate_manifest(path)
        assert len(result["errors"]) > 0
    
    def test_missing_required_field(self, tmp_path):
        """Missing required field should be detected."""
        manifest = {
            "generated_at": "2026-04-08T00:00:00+00:00",
            # Missing "sources" and "aligned_entities"
        }
        path = tmp_path / "incomplete.json"
        with open(path, "w") as f:
            json.dump(manifest, f)
        
        result = validate_manifest(path)
        assert any("sources" in e for e in result["errors"])
    
    def test_missing_source_field_warns(self, tmp_path):
        """Missing source field should generate warning."""
        manifest = {
            "generated_at": "2026-04-08T00:00:00+00:00",
            "pipeline_version": "0.1.0",
            "sources": {
                "gcp_fossil_co2": {
                    # Missing most fields
                },
            },
            "aligned_entities": {},
        }
        path = tmp_path / "partial.json"
        with open(path, "w") as f:
            json.dump(manifest, f)
        
        result = validate_manifest(path)
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) > 0


class TestValidateManifestDirectory:
    """Tests for directory validation."""
    
    def test_validates_all_manifests(self, valid_manifest, tmp_path):
        """Should validate all JSON files in directory."""
        # Create multiple manifests
        for name in ["manifest1.json", "manifest2.json"]:
            path = tmp_path / name
            with open(path, "w") as f:
                json.dump(valid_manifest, f)
        
        results = validate_manifest_directory(tmp_path)
        assert "manifest1.json" in results
        assert "manifest2.json" in results
    
    def test_missing_directory_returns_error(self, tmp_path):
        """Missing directory should return error."""
        result = validate_manifest_directory(tmp_path / "nonexistent")
        assert "error" in result
    
    def test_ignores_non_json_files(self, valid_manifest, tmp_path):
        """Should only process .json files."""
        # Create a JSON manifest
        with open(tmp_path / "manifest.json", "w") as f:
            json.dump(valid_manifest, f)
        
        # Create a non-JSON file
        (tmp_path / "notes.txt").write_text("Some notes")
        
        results = validate_manifest_directory(tmp_path)
        assert "manifest.json" in results
        assert "notes.txt" not in results
