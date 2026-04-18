# tests/unit/test_sobol_decomposition.py
"""Tests for Task 4: SALib Sobol ensemble decomposition."""
from __future__ import annotations

from typing import Any

import pytest

from pyworldx.forecasting.ensemble import (
    DistributionType,
    EnsembleSpec,
    ParameterDistribution,
    UncertaintyType,
    run_ensemble,
)
from pyworldx.scenarios.scenario import Scenario

SALib = pytest.importorskip("SALib", reason="SALib required for Sobol decomposition tests")


def _make_spec(
    run_sobol: bool = False,
    sobol_n: int = 8,
    force_sobol: bool = False,
    n_runs: int = 3,
    dists: dict | None = None,
) -> EnsembleSpec:
    if dists is None:
        dists = {
            "r0_base": ParameterDistribution(
                DistributionType.UNIFORM,
                {"low": 1.0, "high": 5.0},
                "s1",
                UncertaintyType.PARAMETER,
            )
        }
    return EnsembleSpec(
        n_runs=n_runs,
        base_scenario=Scenario("sobol_test", "test", 1900, 1905),
        parameter_distributions=dists,
        run_sobol=run_sobol,
        sobol_n=sobol_n,
        force_sobol=force_sobol,
        seed=42,
    )


def _simple_factory(overrides: dict[str, float]) -> list[Any]:
    from pyworldx.sectors.rip_sectors import IndustrySector, PollutionSector, ResourceSector
    return [ResourceSector(), IndustrySector(), PollutionSector()]


def test_ensemble_spec_has_sobol_fields() -> None:
    """EnsembleSpec must accept run_sobol, sobol_n, force_sobol."""
    spec = _make_spec(run_sobol=True, sobol_n=16, force_sobol=True)
    assert spec.run_sobol is True
    assert spec.sobol_n == 16
    assert spec.force_sobol is True


def test_run_sobol_false_uses_monte_carlo() -> None:
    """Without run_sobol, decomposition uses the simplified MC attribution."""
    spec = _make_spec(run_sobol=False, n_runs=3)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    # Simplified decomposition: scenario, exogenous_input, initial_condition = 0.0
    for var, dec in result.uncertainty_decomposition.items():
        assert dec["scenario"] == pytest.approx(0.0)
        assert dec["exogenous_input"] == pytest.approx(0.0)
        assert dec["initial_condition"] == pytest.approx(0.0)


def test_run_sobol_true_produces_s1_decomposition() -> None:
    """With run_sobol=True, decomposition values come from SALib Sobol analysis."""
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    for var, dec in result.uncertainty_decomposition.items():
        assert "parameter" in dec
        assert "exogenous_input" in dec
        assert "initial_condition" in dec
        assert "scenario" in dec
        # parameter S1 must be non-negative
        assert dec["parameter"] >= 0.0


def test_s1_sum_at_most_one() -> None:
    """Sum of all S1 contributions must not exceed 1.0 (SALib sanity check)."""
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    for var, dec in result.uncertainty_decomposition.items():
        total_s1 = dec["parameter"] + dec["exogenous_input"] + dec["initial_condition"]
        assert total_s1 <= 1.0 + 1e-6, (
            f"S1 sum {total_s1:.4f} > 1.0 for variable {var}"
        )


def test_sample_size_guard_raises_without_force() -> None:
    """N*(2D+2) > 10000 without force_sobol=True must raise ValueError."""
    # Use sobol_n=700 and 8 params → 700*(2*8+2) = 12600 > 10000
    dists = {
        f"p{i}": ParameterDistribution(
            DistributionType.UNIFORM, {"low": 0.0, "high": 1.0}, f"s{i}",
            UncertaintyType.PARAMETER,
        )
        for i in range(8)
    }
    spec = _make_spec(run_sobol=True, sobol_n=700, force_sobol=False, dists=dists)
    with pytest.raises(ValueError, match="force_sobol"):
        run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})


def test_sample_size_guard_bypassed_with_force(monkeypatch: pytest.MonkeyPatch) -> None:
    """force_sobol=True must bypass the 10000-run cap."""
    import pyworldx.forecasting.ensemble as ens_module
    called: list[bool] = []

    def mock_decompose(*args, **kwargs):
        called.append(True)
        return {}
    monkeypatch.setattr(ens_module, "_sobol_decompose", mock_decompose)

    dists = {
        f"p{i}": ParameterDistribution(
            DistributionType.UNIFORM, {"low": 0.0, "high": 1.0}, f"s{i}",
            UncertaintyType.PARAMETER,
        )
        for i in range(8)
    }
    spec = _make_spec(run_sobol=True, sobol_n=700, force_sobol=True, dists=dists)
    run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    assert called  # _sobol_decompose was invoked (guard bypassed)


def test_non_uniform_distribution_raises() -> None:
    """NORMAL distribution with run_sobol=True must raise ValueError."""
    dists = {
        "x": ParameterDistribution(
            DistributionType.NORMAL, {"mean": 0.0, "std": 1.0}, "s1",
            UncertaintyType.PARAMETER,
        )
    }
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True, dists=dists)
    with pytest.raises(ValueError, match="UNIFORM"):
        run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})


def test_ic_group_attributed_to_initial_condition() -> None:
    """Parameters with UncertaintyType.INITIAL_CONDITION aggregate into initial_condition."""
    dists = {
        "ic_p": ParameterDistribution(
            DistributionType.UNIFORM, {"low": 0.0, "high": 1.0}, "s1",
            UncertaintyType.INITIAL_CONDITION,
        )
    }
    spec = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True, dists=dists)
    result = run_ensemble(spec, _simple_factory, engine_kwargs={"master_dt": 1.0})
    for dec in result.uncertainty_decomposition.values():
        # initial_condition group should be non-negative (there's a parameter in it)
        assert dec["initial_condition"] >= 0.0
        assert dec["parameter"] == pytest.approx(0.0)  # no PARAMETER dists


def test_sobol_s1_differs_from_mc_raw_variance() -> None:
    """SALib S1 index (dimensionless, bounded 0-1) must differ from MC raw variance (unbounded).

    The MC fallback stores raw output variance; Sobol stores sensitivity indices.
    For any output with non-zero spread they measure different things and cannot be equal.
    """
    # MC fallback: 10 runs with r0_base ∈ [1.0, 5.0]
    spec_mc = _make_spec(run_sobol=False, n_runs=10)
    result_mc = run_ensemble(spec_mc, _simple_factory, engine_kwargs={"master_dt": 1.0})

    # Sobol: SALib Saltelli with 8 base samples (32 total runs)
    spec_sobol = _make_spec(run_sobol=True, sobol_n=8, force_sobol=True)
    result_sobol = run_ensemble(spec_sobol, _simple_factory, engine_kwargs={"master_dt": 1.0})

    # Find any variable where MC variance is meaningfully nonzero
    for var in result_sobol.uncertainty_decomposition:
        s1 = result_sobol.uncertainty_decomposition[var]["parameter"]
        mc_var = result_mc.uncertainty_decomposition.get(var, {}).get("parameter", 0.0)
        if mc_var > 1e-6:
            # S1 ∈ [0,1]; raw variance is population-scale (likely >> 1 for any model output)
            assert s1 != pytest.approx(mc_var, rel=0.01), (
                f"S1 ({s1:.6f}) should not equal raw MC variance ({mc_var:.6f}) for {var}: "
                "these measure different quantities"
            )
            return  # one confirmed difference is sufficient
    pytest.skip("No variable showed non-zero MC variance — model may have no spread with this seed")
