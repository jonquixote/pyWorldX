"""Phase 4: Tests for build_sector_engine_factory.

Will be RED until the function is implemented in empirical.py.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyworldx.calibration.empirical import build_sector_engine_factory  # noqa: F401


class TestBuildSectorEngineFactory:

    def test_returns_callable(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        assert callable(factory)

    def test_factory_returns_tuple(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        result = factory(full_registry.get_defaults())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_factory_trajectories_is_dict(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        trajectories, time_index = factory(full_registry.get_defaults())
        assert isinstance(trajectories, dict)

    def test_factory_time_index_is_array(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        trajectories, time_index = factory(full_registry.get_defaults())
        assert isinstance(time_index, np.ndarray)
        assert len(time_index) > 0

    def test_factory_time_index_starts_at_1900(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        _, time_index = factory(full_registry.get_defaults())
        # Engine runs 0→200 sim time; factory maps to calendar years 1900→2100
        assert time_index[0] == pytest.approx(1900.0, abs=1.0)

    def test_factory_pop_variable_present(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        trajectories, _ = factory(full_registry.get_defaults())
        assert "POP" in trajectories

    def test_factory_pop_trajectory_length_matches_time(self, full_registry) -> None:
        factory = build_sector_engine_factory(sector="population")
        trajectories, time_index = factory(full_registry.get_defaults())
        assert len(trajectories["POP"]) == len(time_index)

    def test_factory_all_5_sectors_produce_output(self, full_registry) -> None:
        """All 5 World3 sectors must be constructable."""
        for sector in ["population", "capital", "agriculture", "resources", "pollution"]:
            factory = build_sector_engine_factory(sector=sector)
            trajectories, time_index = factory(full_registry.get_defaults())
            assert isinstance(trajectories, dict), f"sector {sector} returned no dict"
            assert len(time_index) > 10, f"sector {sector} time index too short"

    def test_different_params_produce_different_trajectories(
        self, full_registry
    ) -> None:
        factory = build_sector_engine_factory(sector="population")
        defaults = full_registry.get_defaults()
        modified = dict(defaults)
        modified["population.len_scale"] = 1.4  # near upper bound → longer life

        traj_default, time = factory(defaults)
        traj_modified, _ = factory(modified)

        # Higher len_scale → lower death rate → different population trajectory
        assert not np.allclose(traj_default["POP"], traj_modified["POP"])

    def test_unknown_sector_raises_value_error(self, full_registry) -> None:
        with pytest.raises(ValueError, match="Unknown sector"):
            build_sector_engine_factory(sector="nonexistent")
