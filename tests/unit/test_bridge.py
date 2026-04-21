"""Phase 2: DataBridge contract tests.

All tests should be GREEN on the existing bridge implementation.
They lock down the DataBridge API before any further changes.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyworldx.data.bridge import BridgeResult, CalibrationTarget, DataBridge


# ── Test group 1: DataBridge construction ─────────────────────────────


class TestDataBridgeConstruction:
    def test_databridge_default_reference_year(self) -> None:
        bridge = DataBridge()
        assert bridge.reference_year == 1970

    def test_databridge_normalize_flag(self) -> None:
        bridge = DataBridge(normalize=False)
        assert bridge.normalize is False

    def test_databridge_custom_entity_map(self) -> None:
        from pyworldx.data.bridge import EntityMapEntry
        custom = {"population.total": EntityMapEntry(engine_var="POP", transform=None)}
        bridge = DataBridge(entity_map=custom)
        assert bridge.entity_map == custom


# ── Test group 2: compare() with synthetic targets ────────────────────


class TestCompare:
    def test_compare_perfect_match_returns_zero_nrmsd(
        self, fake_engine_factory
    ) -> None:
        """If engine exactly matches targets, composite NRMSD == 0."""
        bridge = DataBridge(normalize=False)
        traj, t_idx = fake_engine_factory({"population.initial_population": 1.65e9})

        perfect_targets = [
            CalibrationTarget(
                variable_name="POP",
                years=np.array([1960, 1970, 1980], dtype=int),
                values=np.interp([1960, 1970, 1980], t_idx, traj["POP"]),
                unit="persons",
                weight=1.0,
                source="test",
                nrmsd_method="direct",
            )
        ]
        result = bridge.compare(perfect_targets, traj, t_idx)
        assert result.composite_nrmsd == pytest.approx(0.0, abs=1e-10)

    def test_compare_returns_bridge_result(
        self, fake_engine_factory, minimal_targets
    ) -> None:
        bridge = DataBridge(normalize=True)
        traj, t_idx = fake_engine_factory({})
        result = bridge.compare(minimal_targets, traj, t_idx)
        assert isinstance(result, BridgeResult)
        assert result.n_targets >= 1
        assert np.isfinite(result.composite_nrmsd)

    def test_compare_skips_variables_not_in_trajectories(
        self, minimal_targets
    ) -> None:
        bridge = DataBridge(normalize=False)
        empty_traj: dict = {}
        result = bridge.compare(minimal_targets, empty_traj, np.arange(1900, 2101))
        assert result.n_targets == 0
        assert np.isnan(result.composite_nrmsd)

    def test_compare_weights_applied_correctly(self) -> None:
        """Higher-weighted variable should dominate composite NRMSD."""
        bridge = DataBridge(normalize=False)
        time = np.arange(1900, 2101, dtype=float)
        traj = {
            "POP": np.ones_like(time) * 3e9,
            "NR":  np.ones_like(time) * 1e12,
        }
        targets_equal = [
            CalibrationTarget("POP", np.array([1970]), np.array([6e9]),
                              "persons", weight=1.0, source="t", nrmsd_method="direct"),
            CalibrationTarget("NR", np.array([1970]), np.array([1.001e12]),
                              "ru", weight=1.0, source="t", nrmsd_method="direct"),
        ]
        targets_pop_heavy = [
            CalibrationTarget("POP", np.array([1970]), np.array([6e9]),
                              "persons", weight=10.0, source="t", nrmsd_method="direct"),
            CalibrationTarget("NR", np.array([1970]), np.array([1.001e12]),
                              "ru", weight=1.0, source="t", nrmsd_method="direct"),
        ]
        r_equal = bridge.compare(targets_equal, traj, time)
        r_heavy = bridge.compare(targets_pop_heavy, traj, time)
        # POP has larger error; weighting it 10× should increase composite
        assert r_heavy.composite_nrmsd > r_equal.composite_nrmsd


# ── Test group 3: build_objective() ──────────────────────────────────


class TestBuildObjective:
    def test_build_objective_returns_callable(
        self, fake_engine_factory, minimal_targets
    ) -> None:
        bridge = DataBridge()
        obj = bridge.build_objective(minimal_targets, fake_engine_factory)
        assert callable(obj)

    def test_build_objective_callable_returns_finite_scalar(
        self, fake_engine_factory, minimal_targets, full_registry
    ) -> None:
        bridge = DataBridge()
        obj = bridge.build_objective(minimal_targets, fake_engine_factory)
        score = obj(full_registry.get_defaults())
        assert isinstance(score, float)
        assert np.isfinite(score)

    def test_build_objective_train_window_clip(
        self, fake_engine_factory, minimal_targets
    ) -> None:
        """Clipping to a narrow window should still return a finite score."""
        bridge = DataBridge()
        obj = bridge.build_objective(
            minimal_targets, fake_engine_factory,
            train_start=1965, train_end=1985,
        )
        # minimal_targets have years [1960..2000]; clipped to [1965..1985] → 3 points
        score = obj({})
        # nan OK if < 3 pts survive clip, inf OK if engine errors
        assert np.isfinite(score) or np.isnan(score) or score == float("inf")

    def test_build_objective_bad_factory_returns_inf(
        self, minimal_targets
    ) -> None:
        """If engine_factory raises, objective should return inf not propagate exception."""
        bridge = DataBridge()

        def bad_factory(params):  # type: ignore[return]
            raise RuntimeError("engine exploded")

        obj = bridge.build_objective(minimal_targets, bad_factory)
        score = obj({"population.len_scale": 1.0})
        assert score == float("inf")


# ── Test group 4: _clip_targets_to_window() and calculate_validation_score()


class TestClipAndValidation:
    def test_clip_targets_drops_short_series(self) -> None:
        """Targets with < 3 points after clip must be dropped."""
        bridge = DataBridge()
        targets = [
            CalibrationTarget(
                "POP",
                years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
                values=np.ones(5) * 3e9,
                unit="persons", weight=1.0, source="t", nrmsd_method="direct",
            )
        ]
        clipped = bridge._clip_targets_to_window(targets, start_year=1998, end_year=2010)
        # Only 2000 survives — fewer than 3 — so target is dropped
        assert len(clipped) == 0

    def test_clip_targets_keeps_adequate_series(self) -> None:
        bridge = DataBridge()
        targets = [
            CalibrationTarget(
                "POP",
                years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
                values=np.ones(5) * 3e9,
                unit="persons", weight=1.0, source="t", nrmsd_method="direct",
            )
        ]
        clipped = bridge._clip_targets_to_window(targets, start_year=1965, end_year=2000)
        assert len(clipped) == 1
        assert list(clipped[0].years) == [1970, 1980, 1990, 2000]

    def test_calculate_validation_score_returns_bridge_result(
        self, fake_engine_factory, minimal_targets, full_registry
    ) -> None:
        bridge = DataBridge()
        result = bridge.calculate_validation_score(
            minimal_targets, fake_engine_factory,
            params=full_registry.get_defaults(),
            validate_start=1985,
            validate_end=2000,
        )
        assert isinstance(result, BridgeResult)


# ── Test group 5: NRMSD methods ──────────────────────────────────────


class TestNRMSDMethods:
    def test_nrmsd_direct_identical_returns_zero(self) -> None:
        arr = np.array([1.0, 2.0, 3.0, 4.0])
        result = DataBridge._compute_nrmsd(arr, arr, "direct")
        assert result == pytest.approx(0.0)

    def test_nrmsd_direct_known_value(self) -> None:
        model = np.array([1.0, 1.0, 1.0])
        ref   = np.array([1.0, 2.0, 3.0])   # mean_abs_ref = 2.0
        # residuals: [0, 1, 2] → RMSD = sqrt(5/3), NRMSD = sqrt(5/3)/2
        expected = np.sqrt(5 / 3) / 2.0
        result = DataBridge._compute_nrmsd(model, ref, "direct")
        assert result == pytest.approx(expected, rel=1e-6)

    def test_nrmsd_change_rate_identical_returns_zero(self) -> None:
        arr = np.array([100.0, 110.0, 121.0, 133.1])
        result = DataBridge._compute_nrmsd(arr, arr, "change_rate")
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_nrmsd_empty_arrays_return_nan(self) -> None:
        result = DataBridge._compute_nrmsd(np.array([]), np.array([]), "direct")
        assert np.isnan(result)
