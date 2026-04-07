"""Tests for observability manifest."""

from __future__ import annotations

from pyworldx.observability.manifest import (
    RunManifest,
    build_manifest,
    finalize_manifest,
)
from pyworldx.sectors.rip_sectors import (
    IndustrySector,
    PollutionSector,
    ResourceSector,
)


class TestRunManifest:
    def test_to_dict(self) -> None:
        m = RunManifest(
            pyworldx_version="0.2.9",
            scenario_name="test",
            active_sectors=["resources", "industry"],
        )
        d = m.to_dict()
        assert d["pyworldx_version"] == "0.2.9"
        assert d["scenario_name"] == "test"
        assert "resources" in d["active_sectors"]

    def test_build_manifest(self) -> None:
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        m = build_manifest(
            sectors=sectors,
            parameter_values={"icor": 3.0},
            scenario_name="baseline",
        )
        assert m.pyworldx_version == "0.2.9"
        assert "resources" in m.active_sectors
        assert m.parameter_values["icor"] == 3.0
        assert m.started_at != ""
        assert m.hostname != ""
        assert m.python_version != ""

    def test_finalize_manifest(self) -> None:
        sectors = [ResourceSector()]
        m = build_manifest(sectors=sectors)
        finalize_manifest(m)
        assert m.completed_at != ""
        assert m.wall_clock_seconds >= 0.0

    def test_sector_versions_captured(self) -> None:
        sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
        m = build_manifest(sectors=sectors)
        assert "resources" in m.sector_versions
