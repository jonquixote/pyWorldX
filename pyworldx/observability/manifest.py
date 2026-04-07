"""Run provenance and observability (Section 12).

Provides the RunManifest for full provenance tracking of every
simulation run, including git commit, parameter registry version,
connector vintages, and calibration references.
"""

from __future__ import annotations

import datetime
import subprocess
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunManifest:
    """Full run provenance manifest (Section 12.3).

    Every run must record all information needed to reproduce
    the result exactly.
    """

    # Code identity
    pyworldx_version: str = ""
    git_commit: str = ""
    code_hash: str = ""

    # Scenario identity
    scenario_name: str = ""
    scenario_hash: str = ""

    # Ensemble info
    ensemble_seed: int | None = None
    ensemble_size: int | None = None

    # Parameter registry
    parameter_registry_version: str = ""
    parameter_values: dict[str, float] = field(default_factory=dict)

    # Data provenance
    connector_vintages: dict[str, str] = field(default_factory=dict)
    proxy_methods: dict[str, str] = field(default_factory=dict)

    # Calibration
    calibration_config: dict[str, Any] = field(default_factory=dict)
    calibration_report_ref: str = ""
    identifiability_screen_ref: str = ""

    # Ontology
    ontology_registry_version: str = ""

    # Model structure
    active_sectors: list[str] = field(default_factory=list)
    sector_versions: dict[str, str] = field(default_factory=dict)
    substep_integrators: dict[str, str] = field(default_factory=dict)

    # Runtime
    wall_clock_seconds: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    hostname: str = ""
    python_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage/export."""
        return {
            "pyworldx_version": self.pyworldx_version,
            "git_commit": self.git_commit,
            "scenario_name": self.scenario_name,
            "scenario_hash": self.scenario_hash,
            "ensemble_seed": self.ensemble_seed,
            "ensemble_size": self.ensemble_size,
            "parameter_registry_version": self.parameter_registry_version,
            "parameter_values": self.parameter_values,
            "connector_vintages": self.connector_vintages,
            "proxy_methods": self.proxy_methods,
            "calibration_config": self.calibration_config,
            "calibration_report_ref": self.calibration_report_ref,
            "identifiability_screen_ref": self.identifiability_screen_ref,
            "ontology_registry_version": self.ontology_registry_version,
            "active_sectors": self.active_sectors,
            "sector_versions": self.sector_versions,
            "substep_integrators": self.substep_integrators,
            "wall_clock_seconds": self.wall_clock_seconds,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "hostname": self.hostname,
            "python_version": self.python_version,
        }


def _get_git_commit() -> str:
    """Try to get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "unknown"


def build_manifest(
    sectors: list[Any],
    parameter_values: dict[str, float] | None = None,
    scenario_name: str = "",
    ensemble_seed: int | None = None,
    ensemble_size: int | None = None,
    calibration_config: dict[str, Any] | None = None,
) -> RunManifest:
    """Build a RunManifest from current model state.

    Automatically captures git commit, hostname, timestamp, etc.
    """
    import platform
    import sys

    manifest = RunManifest(
        pyworldx_version="0.2.9",
        git_commit=_get_git_commit(),
        scenario_name=scenario_name,
        ensemble_seed=ensemble_seed,
        ensemble_size=ensemble_size,
        parameter_values=parameter_values or {},
        calibration_config=calibration_config or {},
        active_sectors=[s.name for s in sectors],
        sector_versions={
            s.name: getattr(s, "version", "unknown") for s in sectors
        },
        substep_integrators={
            s.name: str(
                s.metadata().get("preferred_substep_integrator", "rk4")
            )
            for s in sectors
            if hasattr(s, "metadata")
        },
        started_at=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        hostname=platform.node(),
        python_version=sys.version.split()[0],
    )
    return manifest


def finalize_manifest(manifest: RunManifest) -> None:
    """Mark a manifest as completed with wall-clock time."""
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    manifest.completed_at = now

    if manifest.started_at:
        try:
            start = datetime.datetime.fromisoformat(manifest.started_at)
            end = datetime.datetime.fromisoformat(now)
            manifest.wall_clock_seconds = (end - start).total_seconds()
        except (ValueError, TypeError):
            manifest.wall_clock_seconds = 0.0
