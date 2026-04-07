"""Tests for ensemble forecasting layer."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from pyworldx.forecasting.ensemble import (
    DistributionType,
    EnsembleResult,
    EnsembleSpec,
    ParameterDistribution,
    ThresholdQuery,
    UncertaintyType,
    UndeclaredThresholdQueryError,
    run_ensemble,
)
from pyworldx.scenarios.scenario import Scenario


def _simple_sector_factory(overrides: dict[str, float]) -> list[Any]:
    """Build minimal RIP sectors for ensemble testing."""
    from pyworldx.sectors.rip_sectors import (
        IndustrySector,
        PollutionSector,
        ResourceSector,
    )

    return [ResourceSector(), IndustrySector(), PollutionSector()]


class TestParameterDistribution:
    def test_uniform_sample(self) -> None:
        pd = ParameterDistribution(
            DistributionType.UNIFORM,
            {"low": 0.0, "high": 1.0},
            "stream1",
            UncertaintyType.PARAMETER,
        )
        rng = np.random.default_rng(42)
        samples = pd.sample(rng, 100)
        assert len(samples) == 100
        assert np.all(samples >= 0.0)
        assert np.all(samples <= 1.0)

    def test_normal_sample(self) -> None:
        pd = ParameterDistribution(
            DistributionType.NORMAL,
            {"mean": 5.0, "std": 1.0},
            "stream1",
            UncertaintyType.PARAMETER,
        )
        rng = np.random.default_rng(42)
        samples = pd.sample(rng, 1000)
        assert abs(np.mean(samples) - 5.0) < 0.2

    def test_truncated_normal(self) -> None:
        pd = ParameterDistribution(
            DistributionType.TRUNCATED_NORMAL,
            {"mean": 0.5, "std": 0.1, "low": 0.0, "high": 1.0},
            "stream1",
            UncertaintyType.INITIAL_CONDITION,
        )
        rng = np.random.default_rng(42)
        samples = pd.sample(rng, 100)
        assert np.all(samples >= 0.0)
        assert np.all(samples <= 1.0)

    def test_uncertainty_type_mandatory(self) -> None:
        # uncertainty_type has no default — must be set explicitly
        pd = ParameterDistribution(
            DistributionType.UNIFORM,
            {"low": 0.0, "high": 1.0},
            "stream1",
            UncertaintyType.PARAMETER,
        )
        assert pd.uncertainty_type == UncertaintyType.PARAMETER


class TestThresholdQuery:
    def test_frozen(self) -> None:
        tq = ThresholdQuery("q1", "NR", "below", 5e11, 2050)
        assert tq.name == "q1"
        # Frozen dataclass — cannot mutate
        with pytest.raises(AttributeError):
            tq.name = "changed"  # type: ignore[misc]


class TestEnsembleResult:
    def test_undeclared_threshold_raises(self) -> None:
        er = EnsembleResult(
            members=None,
            summary={},
            threshold_results={},
            uncertainty_decomposition={},
        )
        with pytest.raises(UndeclaredThresholdQueryError):
            er.probability_of_threshold("nonexistent")


class TestRunEnsemble:
    def test_small_ensemble(self) -> None:
        spec = EnsembleSpec(
            n_runs=3,
            base_scenario=Scenario(
                "test", "test run", 1900, 1910,
            ),
            parameter_distributions={},
            seed=42,
            store_member_runs=True,
        )
        result = run_ensemble(
            spec, _simple_sector_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        assert result.members is not None
        assert len(result.members) == 3
        assert "R" in result.summary
        df = result.summary["R"]
        assert "mean" in df.columns
        assert "p05" in df.columns
        assert "p95" in df.columns

    def test_ensemble_without_storage(self) -> None:
        spec = EnsembleSpec(
            n_runs=2,
            base_scenario=Scenario("test", "test", 1900, 1905),
            parameter_distributions={},
            seed=42,
            store_member_runs=False,
        )
        result = run_ensemble(
            spec, _simple_sector_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        assert result.members is None

    def test_threshold_query(self) -> None:
        spec = EnsembleSpec(
            n_runs=5,
            base_scenario=Scenario("test", "test", 1900, 1920),
            parameter_distributions={},
            threshold_queries=[
                ThresholdQuery("nr_depletion", "R", "below", 5e11, 1920),
            ],
            seed=42,
        )
        result = run_ensemble(
            spec, _simple_sector_factory,
            engine_kwargs={"master_dt": 1.0},
        )
        assert "nr_depletion" in result.threshold_results
        prob = result.probability_of_threshold("nr_depletion")
        assert 0.0 <= prob <= 1.0
