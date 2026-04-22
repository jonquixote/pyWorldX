# pyWorldX Calibration — TDD Coding Plan

## The Real State of the Codebase

Before writing a single test, it helps to understand exactly what exists and what is broken.

**What works correctly:**
- `ParameterRegistry` in `parameters.py` — fully implemented with `get_sector_parameters()`, `all_entries()`, `get_defaults()`, `get_bounds()`, `validate_overrides()`, etc.
- `build_world3_parameter_registry()` — module-level function, returns a fully populated registry with 17 parameters across 5 sectors
- `DataBridge` in `bridge.py` — `load_targets()`, `load_targets_from_results()`, `compare()`, `build_objective()`, `calculate_validation_score()` all exist and are implemented
- `EmpiricalCalibrationRunner` in `empirical.py` — the **class itself** is fully implemented. `runner.run(registry, engine_factory, ...)` works correctly
- `run_calibration_pipeline()` in `pipeline.py` — fully implemented (profile likelihood → Morris → Bayesian TPE → Nelder-Mead → Sobol)

**What is broken — the CLI only:**
The `EmpiricalCalibrationRunner.run()` method takes a `registry: ParameterRegistry` argument. The CLI (lines ~300–340 of `empirical.py`, in the `if __name__ == "__main__":` block or an `argparse` entrypoint) incorrectly calls:
```python
registry = ParameterRegistry.for_sector(args.sector)   # ← method doesn't exist
registry = registry.subset(requested)                   # ← method doesn't exist
len(registry)                                           # ← no __len__
```
The class has none of these. The fix uses the actual API: `build_world3_parameter_registry()` + `registry.get_sector_parameters(sector)`.

**What is missing / stubs:**
- `build_sector_engine_factory(sector, params)` — the CLI needs this to construct an `engine_factory` callable scoped to a sector; it doesn't exist yet
- `tests/unit/test_empirical_cli.py` — no CLI tests exist
- `tests/unit/test_parameters.py` — no registry unit tests exist
- `tests/unit/test_bridge.py` — no bridge unit tests exist

***

## TDD Plan: Red → Green → Refactor

### Phase 0 — Fixtures (no tests yet, just infrastructure)

**File: `tests/conftest.py`** — extend the existing conftest with calibration fixtures.

```python
# Add to existing conftest.py

import numpy as np
import pytest
from pyworldx.calibration.parameters import build_world3_parameter_registry
from pyworldx.data.bridge import DataBridge, CalibrationTarget


@pytest.fixture
def full_registry():
    """The canonical 17-parameter World3 registry."""
    return build_world3_parameter_registry()


@pytest.fixture
def fake_engine_factory():
    """Minimal engine_factory stub: linear growth for all variables."""
    def factory(params: dict) -> tuple[dict, np.ndarray]:
        time = np.arange(1900, 2101, dtype=float)
        pop0 = params.get("population.initial_population", 1.65e9)
        trajectories = {
            "POP": pop0 * (1 + 0.015 * (time - 1900)),
            "IC":  2.1e11 * (1 + 0.02 * (time - 1900)),
            "AL":  9e8 * np.ones_like(time),
            "NR":  1e12 * np.exp(-0.005 * (time - 1900)),
            "PPOL": 2.5e7 * (1 + 0.03 * (time - 1900)),
        }
        return trajectories, time
    return factory


@pytest.fixture
def minimal_targets():
    """Two CalibrationTargets with known analytic NRMSD."""
    years = np.array([1960, 1970, 1980, 1990, 2000], dtype=int)
    return [
        CalibrationTarget(
            variable_name="POP",
            years=years,
            values=np.array([3.0e9, 3.7e9, 4.4e9, 5.3e9, 6.1e9]),
            unit="persons",
            weight=1.0,
            source="test",
            nrmsd_method="direct",
        ),
        CalibrationTarget(
            variable_name="NR",
            years=years,
            values=np.array([9.5e11, 9.0e11, 8.5e11, 8.0e11, 7.5e11]),
            unit="resource_units",
            weight=1.0,
            source="test",
            nrmsd_method="change_rate",
        ),
    ]
```

***

### Phase 1 — Unit tests for `ParameterRegistry` (parameters.py)

**File: `tests/unit/test_parameters.py`**

These tests all pass green immediately against the existing code. Write them first to lock down the contract before touching anything else — they are the regression net.

**Test group 1: Registry construction**
```python
# tests/unit/test_parameters.py

def test_registry_builds_without_error():
    reg = build_world3_parameter_registry()
    assert reg is not None

def test_registry_has_17_parameters(full_registry):
    assert full_registry.size == 17

def test_all_sectors_present(full_registry):
    sectors = {e.sector_owner for e in full_registry.all_entries()}
    assert sectors == {"population", "capital", "agriculture", "resources", "pollution"}

def test_get_defaults_returns_all_names(full_registry):
    defaults = full_registry.get_defaults()
    assert len(defaults) == full_registry.size
    assert all(isinstance(v, float) for v in defaults.values())

def test_get_bounds_all_valid(full_registry):
    for name, (lo, hi) in full_registry.get_bounds().items():
        assert lo < hi, f"{name}: lo={lo} >= hi={hi}"
    assert len(full_registry.get_bounds()) == full_registry.size

def test_default_within_bounds_for_all(full_registry):
    bounds = full_registry.get_bounds()
    defaults = full_registry.get_defaults()
    for name, val in defaults.items():
        lo, hi = bounds[name]
        assert lo <= val <= hi, f"{name}: {val} outside [{lo}, {hi}]"
```

**Test group 2: `get_sector_parameters`** — this is the method the fixed CLI relies on
```python
def test_get_sector_parameters_population(full_registry):
    params = full_registry.get_sector_parameters("population")
    assert len(params) == 3
    names = {p.name for p in params}
    assert "population.cbr_base" in names
    assert "population.cdr_base" in names
    assert "population.initial_population" in names

def test_get_sector_parameters_capital(full_registry):
    params = full_registry.get_sector_parameters("capital")
    assert len(params) == 4

def test_get_sector_parameters_agriculture(full_registry):
    params = full_registry.get_sector_parameters("agriculture")
    assert len(params) == 4

def test_get_sector_parameters_resources(full_registry):
    params = full_registry.get_sector_parameters("resources")
    assert len(params) == 2

def test_get_sector_parameters_pollution(full_registry):
    params = full_registry.get_sector_parameters("pollution")
    assert len(params) == 3

def test_get_sector_parameters_unknown_sector_returns_empty(full_registry):
    result = full_registry.get_sector_parameters("nonexistent")
    assert result == []

def test_sector_parameters_sum_to_total(full_registry):
    total = sum(
        len(full_registry.get_sector_parameters(s))
        for s in ["population", "capital", "agriculture", "resources", "pollution"]
    )
    assert total == full_registry.size
```

**Test group 3: Lookup and validation**
```python
def test_lookup_known_parameter(full_registry):
    entry = full_registry.lookup("population.cbr_base")
    assert entry.default == pytest.approx(0.04)
    assert entry.bounds == (0.02, 0.06)
    assert entry.units == "1/year"

def test_lookup_unknown_raises(full_registry):
    with pytest.raises(KeyError):
        full_registry.lookup("does.not.exist")

def test_validate_overrides_out_of_bounds(full_registry):
    warnings = full_registry.validate_overrides({"population.cbr_base": 999.0})
    assert len(warnings) == 1
    assert "population.cbr_base" in warnings[0]

def test_validate_overrides_unknown_param(full_registry):
    warnings = full_registry.validate_overrides({"fake.param": 1.0})
    assert any("Unknown" in w for w in warnings)

def test_apply_overrides_produces_correct_value(full_registry):
    result = full_registry.apply_overrides({"population.cbr_base": 0.05})
    assert result["population.cbr_base"] == pytest.approx(0.05)
    # all other params unchanged
    assert result["population.cdr_base"] == pytest.approx(0.028)

def test_duplicate_registration_raises():
    from pyworldx.calibration.parameters import (
        ParameterRegistry, ParameterEntry, DuplicateParameterError
    )
    reg = ParameterRegistry()
    entry = ParameterEntry(
        name="test.param", default=1.0, bounds=(0.0, 2.0),
        units="dimensionless", sector_owner="test"
    )
    reg.register(entry)
    with pytest.raises(DuplicateParameterError):
        reg.register(entry)

def test_all_entries_returns_list(full_registry):
    entries = full_registry.all_entries()
    assert isinstance(entries, list)
    assert len(entries) == full_registry.size
```

**Test group 4: `ParameterRegistry` has NO `for_sector`, NO `subset`, NO `__len__`** — regression guard
```python
def test_registry_has_no_for_sector_classmethod(full_registry):
    assert not hasattr(full_registry, "for_sector")

def test_registry_has_no_subset_method(full_registry):
    assert not hasattr(full_registry, "subset")

def test_registry_has_no_len():
    """len(registry) must raise TypeError — use .size instead."""
    from pyworldx.calibration.parameters import ParameterRegistry
    reg = ParameterRegistry()
    with pytest.raises(TypeError):
        len(reg)
```

> **Why these negative tests?** They prevent future contributors from accidentally adding these methods thinking they're needed, which would re-introduce ambiguity.

***

### Phase 2 — Unit tests for `DataBridge` (bridge.py)

**File: `tests/unit/test_bridge.py`**

Again, these should all pass green on the existing code. Run them first, fix any surprises, then use them as the regression harness.

**Test group 1: `DataBridge` construction**
```python
# tests/unit/test_bridge.py
from pyworldx.data.bridge import DataBridge, BridgeResult, CalibrationTarget

def test_databridge_default_reference_year():
    bridge = DataBridge()
    assert bridge.reference_year == 1970

def test_databridge_normalize_flag():
    bridge = DataBridge(normalize=False)
    assert bridge.normalize is False

def test_databridge_custom_entity_map():
    custom = {"population.total": "POP"}
    bridge = DataBridge(entity_map=custom)
    assert bridge.entity_map == custom
```

**Test group 2: `compare()` with synthetic targets**
```python
def test_compare_perfect_match_returns_zero_nrmsd(fake_engine_factory, minimal_targets):
    """If engine exactly matches targets, composite NRMSD == 0."""
    bridge = DataBridge(normalize=False)
    # Build targets from the factory's own output
    time = np.arange(1900, 2101, dtype=float)
    traj, t_idx = fake_engine_factory({"population.initial_population": 1.65e9})
    
    perfect_targets = [
        CalibrationTarget(
            variable_name="POP",
            years=np.array([1960, 1970, 1980], dtype=int),
            values=np.interp([1960, 1970, 1980], t_idx, traj["POP"]),
            unit="persons", weight=1.0, source="test", nrmsd_method="direct",
        )
    ]
    result = bridge.compare(perfect_targets, traj, t_idx)
    assert result.composite_nrmsd == pytest.approx(0.0, abs=1e-10)

def test_compare_returns_bridge_result(fake_engine_factory, minimal_targets):
    bridge = DataBridge(normalize=True)
    traj, t_idx = fake_engine_factory({})
    result = bridge.compare(minimal_targets, traj, t_idx)
    assert isinstance(result, BridgeResult)
    assert result.n_targets >= 1
    assert np.isfinite(result.composite_nrmsd)

def test_compare_skips_variables_not_in_trajectories(minimal_targets):
    bridge = DataBridge(normalize=False)
    empty_traj = {}
    result = bridge.compare(minimal_targets, empty_traj, np.arange(1900, 2101))
    assert result.n_targets == 0
    assert np.isnan(result.composite_nrmsd)

def test_compare_weights_applied_correctly():
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
```

**Test group 3: `build_objective()`**
```python
def test_build_objective_returns_callable(fake_engine_factory, minimal_targets):
    bridge = DataBridge()
    obj = bridge.build_objective(minimal_targets, fake_engine_factory)
    assert callable(obj)

def test_build_objective_callable_returns_finite_scalar(
    fake_engine_factory, minimal_targets, full_registry
):
    bridge = DataBridge()
    obj = bridge.build_objective(minimal_targets, fake_engine_factory)
    score = obj(full_registry.get_defaults())
    assert isinstance(score, float)
    assert np.isfinite(score)

def test_build_objective_train_window_clip(fake_engine_factory, minimal_targets):
    """Clipping to a narrow window should still return a finite score."""
    bridge = DataBridge()
    obj = bridge.build_objective(
        minimal_targets, fake_engine_factory,
        train_start=1965, train_end=1985,
    )
    # minimal_targets have years [1960..2000]; clipped to [1965..1985] → 3 points
    score = obj({})
    assert np.isfinite(score) or np.isnan(score)  # nan OK if < 3 pts survive clip

def test_build_objective_bad_factory_returns_inf(minimal_targets):
    """If engine_factory raises, objective should return inf not propagate exception."""
    bridge = DataBridge()
    def bad_factory(params):
        raise RuntimeError("engine exploded")
    obj = bridge.build_objective(minimal_targets, bad_factory)
    score = obj({"population.cbr_base": 0.04})
    assert score == float("inf")
```

**Test group 4: `_clip_targets_to_window()` and `calculate_validation_score()`**
```python
def test_clip_targets_drops_short_series():
    """Targets with < 3 points after clip must be dropped."""
    bridge = DataBridge()
    targets = [
        CalibrationTarget("POP",
            years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
            values=np.ones(5) * 3e9,
            unit="persons", weight=1.0, source="t", nrmsd_method="direct",
        )
    ]
    clipped = bridge._clip_targets_to_window(targets, start_year=1998, end_year=2010)
    # Only 2000 survives — fewer than 3 — so target is dropped
    assert len(clipped) == 0

def test_clip_targets_keeps_adequate_series():
    bridge = DataBridge()
    targets = [
        CalibrationTarget("POP",
            years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
            values=np.ones(5) * 3e9,
            unit="persons", weight=1.0, source="t", nrmsd_method="direct",
        )
    ]
    clipped = bridge._clip_targets_to_window(targets, start_year=1965, end_year=2000)
    assert len(clipped) == 1
    assert list(clipped[0].years) == [1970, 1980, 1990, 2000]

def test_calculate_validation_score_returns_bridge_result(
    fake_engine_factory, minimal_targets, full_registry
):
    bridge = DataBridge()
    result = bridge.calculate_validation_score(
        minimal_targets, fake_engine_factory,
        params=full_registry.get_defaults(),
        validate_start=1985,
        validate_end=2000,
    )
    assert isinstance(result, BridgeResult)
```

**Test group 5: NRMSD methods (direct vs change\_rate)**
```python
def test_nrmsd_direct_identical_returns_zero():
    arr = np.array([1.0, 2.0, 3.0, 4.0])
    result = DataBridge._compute_nrmsd(arr, arr, "direct")
    assert result == pytest.approx(0.0)

def test_nrmsd_direct_known_value():
    model = np.array([1.0, 1.0, 1.0])
    ref   = np.array([1.0, 2.0, 3.0])   # mean_abs_ref = 2.0
    # residuals: [0, 1, 2] → RMSD = sqrt(5/3), NRMSD = sqrt(5/3)/2
    expected = np.sqrt(5/3) / 2.0
    result = DataBridge._compute_nrmsd(model, ref, "direct")
    assert result == pytest.approx(expected, rel=1e-6)

def test_nrmsd_change_rate_identical_returns_zero():
    arr = np.array([100.0, 110.0, 121.0, 133.1])
    result = DataBridge._compute_nrmsd(arr, arr, "change_rate")
    assert result == pytest.approx(0.0, abs=1e-10)

def test_nrmsd_empty_arrays_return_nan():
    result = DataBridge._compute_nrmsd(np.array([]), np.array([]), "direct")
    assert np.isnan(result)
```

***

### Phase 3 — Unit tests for the broken CLI block (empirical.py)

This is where the **red** tests live. These will **fail** on the current code. Writing them first locks down the exact behavior expected before patching.

**File: `tests/unit/test_empirical_cli.py`**

The strategy is to extract the broken block into a testable helper function `_resolve_registry(args)` rather than testing `argparse` CLI directly, which is fragile and slow.

**Step 3a — Write the failing tests (RED)**

```python
# tests/unit/test_empirical_cli.py
"""Tests for the CLI registry-resolution helper in empirical.py.

These tests document the CORRECT behavior and will be RED until
_resolve_registry() is implemented to replace the broken for_sector/subset
calls in the CLI block.
"""
import pytest
from types import SimpleNamespace
from pyworldx.calibration.empirical import _resolve_registry  # ← doesn't exist yet → ImportError


class TestResolveRegistryAllSectors:
    """No --params flag: return all parameters for the given sector."""

    def test_population_sector_returns_3_names(self):
        args = SimpleNamespace(sector="population", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 3

    def test_capital_sector_returns_4_names(self):
        args = SimpleNamespace(sector="capital", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 4

    def test_agriculture_sector_returns_4_names(self):
        args = SimpleNamespace(sector="agriculture", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 4

    def test_resources_sector_returns_2_names(self):
        args = SimpleNamespace(sector="resources", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 2

    def test_pollution_sector_returns_3_names(self):
        args = SimpleNamespace(sector="pollution", params=None)
        reg, names = _resolve_registry(args)
        assert len(names) == 3

    def test_returns_full_registry_not_subset(self):
        """Registry must be the full 17-param registry, not a sector slice."""
        args = SimpleNamespace(sector="population", params=None)
        reg, names = _resolve_registry(args)
        assert reg.size == 17

    def test_name_strings_exist_in_registry(self):
        args = SimpleNamespace(sector="capital", params=None)
        reg, names = _resolve_registry(args)
        for name in names:
            entry = reg.lookup(name)  # must not raise
            assert entry.sector_owner == "capital"


class TestResolveRegistryWithParamsFlag:
    """--params flag: return only the explicitly requested names."""

    def test_single_valid_param(self):
        args = SimpleNamespace(sector="population", params="population.cbr_base")
        reg, names = _resolve_registry(args)
        assert names == ["population.cbr_base"]

    def test_multiple_valid_params(self):
        args = SimpleNamespace(
            sector="capital",
            params="capital.icor, capital.alic"
        )
        reg, names = _resolve_registry(args)
        assert set(names) == {"capital.icor", "capital.alic"}

    def test_params_stripped_of_whitespace(self):
        args = SimpleNamespace(sector="capital", params="  capital.icor , capital.alic  ")
        reg, names = _resolve_registry(args)
        assert "capital.icor" in names
        assert "capital.alic" in names

    def test_unknown_param_raises_value_error(self):
        args = SimpleNamespace(sector="population", params="does.not.exist")
        with pytest.raises(ValueError, match="Unknown parameter"):
            _resolve_registry(args)

    def test_cross_sector_param_allowed(self):
        """--params can reference a param from a different sector (power-user mode)."""
        args = SimpleNamespace(sector="population", params="capital.icor")
        reg, names = _resolve_registry(args)
        assert names == ["capital.icor"]


class TestResolveRegistryEdgeCases:

    def test_unknown_sector_with_no_params_raises_value_error(self):
        args = SimpleNamespace(sector="nonexistent_sector", params=None)
        with pytest.raises(ValueError, match="No parameters found"):
            _resolve_registry(args)

    def test_empty_params_string_falls_back_to_sector(self):
        """Empty --params string should behave like --params not provided."""
        args = SimpleNamespace(sector="resources", params="")
        reg, names = _resolve_registry(args)
        assert len(names) == 2

    def test_params_with_only_whitespace_falls_back_to_sector(self):
        args = SimpleNamespace(sector="resources", params="   ")
        reg, names = _resolve_registry(args)
        assert len(names) == 2
```

**Step 3b — Implement `_resolve_registry()` to make tests GREEN**

Add this function to `pyworldx/calibration/empirical.py`, above the `if __name__ == "__main__":` block:

```python
# pyworldx/calibration/empirical.py  (new function — add before CLI block)

from types import SimpleNamespace
from typing import Union

def _resolve_registry(
    args: Union[SimpleNamespace, "argparse.Namespace"],
) -> tuple["ParameterRegistry", list[str]]:
    """Resolve a ParameterRegistry and parameter name list from CLI args.

    This is the canonical, testable replacement for the broken
    ParameterRegistry.for_sector() / registry.subset() calls.

    Args:
        args: Namespace with .sector (str) and .params (str | None)

    Returns:
        (full_registry, requested_names)
            full_registry — the complete 17-parameter registry
            requested_names — list of parameter names to calibrate

    Raises:
        ValueError: if sector has no parameters or a requested name is unknown
    """
    from pyworldx.calibration.parameters import build_world3_parameter_registry

    full_registry = build_world3_parameter_registry()

    if args.params and args.params.strip():
        requested = [p.strip() for p in args.params.split(",") if p.strip()]
    else:
        requested = [
            e.name for e in full_registry.get_sector_parameters(args.sector)
        ]

    if not requested:
        raise ValueError(
            f"No parameters found for sector {args.sector!r}. "
            "Check that sector name matches 'sector_owner' in parameters.py. "
            "Valid sectors: population, capital, agriculture, resources, pollution"
        )

    missing = [n for n in requested if n not in full_registry._entries]
    if missing:
        raise ValueError(
            f"Unknown parameter(s): {missing}. "
            "Run: python -c \"from pyworldx.calibration.parameters import "
            "build_world3_parameter_registry; "
            "[print(e.name) for e in build_world3_parameter_registry().all_entries()]\""
        )

    return full_registry, requested
```

**Step 3c — Patch the CLI block to use `_resolve_registry()`**

Replace the broken ~25-line block in the `__main__` / CLI section of `empirical.py`:

```python
# REMOVE this entire block:
try:
    from pyworldx.calibration.parameters import ParameterRegistry
    registry = ParameterRegistry.for_sector(args.sector)
except Exception as exc:
    _log.error("Could not build ParameterRegistry for sector %r: %s", args.sector, exc)
    sys.exit(1)

if args.params:
    requested = [p.strip() for p in args.params.split(",") if p.strip()]
    try:
        registry = registry.subset(requested)
    except Exception as exc:
        _log.error("Could not subset registry to params %s: %s", requested, exc)
        sys.exit(1)

_log.info(
    "Calibrating %d parameter(s) in sector %r over train window %d-%d …",
    len(registry),        # ← also broken: no __len__
    ...
)


# REPLACE WITH:
try:
    registry, requested = _resolve_registry(args)
except ValueError as exc:
    _log.error("%s", exc)
    sys.exit(1)

_log.info(
    "Calibrating %d parameter(s) in sector %r over train window %d-%d …",
    len(requested),
    args.sector,
    train_start,
    train_end,
)
```

***

### Phase 4 — `build_sector_engine_factory()` (the next thing that will break)

After the registry fix, the CLI will crash on the `engine_factory` construction. The function `build_sector_engine_factory` is called but doesn't exist anywhere in the codebase.

**Step 4a — Write the failing tests (RED)**

```python
# tests/unit/test_engine_factory.py
"""Tests for build_sector_engine_factory.

Will be RED until the function is implemented.
"""
import numpy as np
import pytest
from pyworldx.calibration.empirical import build_sector_engine_factory  # ← doesn't exist yet


class TestBuildSectorEngineFactory:

    def test_returns_callable(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        assert callable(factory)

    def test_factory_returns_tuple(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        result = factory(full_registry.get_defaults())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_factory_trajectories_is_dict(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        trajectories, time_index = factory(full_registry.get_defaults())
        assert isinstance(trajectories, dict)

    def test_factory_time_index_is_array(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        trajectories, time_index = factory(full_registry.get_defaults())
        assert isinstance(time_index, np.ndarray)
        assert len(time_index) > 0

    def test_factory_time_index_starts_at_1900(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        _, time_index = factory(full_registry.get_defaults())
        assert time_index[0] == pytest.approx(1900.0, abs=1.0)

    def test_factory_pop_variable_present(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        trajectories, _ = factory(full_registry.get_defaults())
        assert "POP" in trajectories

    def test_factory_pop_trajectory_length_matches_time(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        trajectories, time_index = factory(full_registry.get_defaults())
        assert len(trajectories["POP"]) == len(time_index)

    def test_factory_all_5_sectors_produce_output(self, full_registry):
        """All 5 World3 sectors must be constructable."""
        for sector in ["population", "capital", "agriculture", "resources", "pollution"]:
            factory = build_sector_engine_factory(sector=sector)
            trajectories, time_index = factory(full_registry.get_defaults())
            assert isinstance(trajectories, dict), f"sector {sector} returned no dict"
            assert len(time_index) > 10, f"sector {sector} time index too short"

    def test_different_params_produce_different_trajectories(self, full_registry):
        factory = build_sector_engine_factory(sector="population")
        defaults = full_registry.get_defaults()
        modified = dict(defaults)
        modified["population.cbr_base"] = 0.055  # near upper bound

        traj_default, time = factory(defaults)
        traj_modified, _ = factory(modified)

        # Higher CBR should produce higher population at some point
        assert not np.allclose(traj_default["POP"], traj_modified["POP"])

    def test_unknown_sector_raises_value_error(self, full_registry):
        with pytest.raises(ValueError, match="Unknown sector"):
            build_sector_engine_factory(sector="nonexistent")
```

**Step 4b — Implement `build_sector_engine_factory()`**

Add to `pyworldx/calibration/empirical.py`:

```python
# pyworldx/calibration/empirical.py  (new function)

from pyworldx.core.engine import Engine
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector

_SECTOR_CLASS_MAP = {
    "population": PopulationSector,
    "capital": CapitalSector,
    "agriculture": AgricultureSector,
    "resources": ResourcesSector,
    "pollution": PollutionSector,
}


def build_sector_engine_factory(
    sector: str,
    t_start: float = 1900.0,
    t_end: float = 2100.0,
    master_dt: float = 1.0,
) -> Callable[[dict[str, float]], tuple[dict[str, np.ndarray], np.ndarray]]:
    """Build an engine_factory callable for calibration.

    Always runs all 5 World3 sectors (parameter coupling requires it),
    but the `sector` argument is validated to catch typos early.

    Returns:
        Callable: params -> (trajectories_dict, time_index_array)

    Raises:
        ValueError: if sector is not one of the 5 known World3 sectors
    """
    if sector not in _SECTOR_CLASS_MAP:
        raise ValueError(
            f"Unknown sector {sector!r}. "
            f"Valid sectors: {sorted(_SECTOR_CLASS_MAP.keys())}"
        )

    def factory(params: dict[str, float]) -> tuple[dict[str, np.ndarray], np.ndarray]:
        engine = Engine(
            sectors=[
                PopulationSector(),
                CapitalSector(),
                AgricultureSector(),
                ResourcesSector(),
                PollutionSector(),
            ],
            master_dt=master_dt,
            t_start=t_start,
            t_end=t_end,
            parameter_overrides=params,
        )
        result = engine.run()
        # Convert RunResult.trajectories to the (dict, time_array) shape
        # expected by DataBridge.compare()
        time_index = np.asarray(result.time_index, dtype=float) + t_start
        return result.trajectories, time_index

    return factory
```

> **Note:** If `Engine.__init__` doesn't accept `parameter_overrides`, the tests in 4b will catch that immediately. The fix would be to pass params through sector constructors or a `central_registrar` — the test failures will point you at the exact interface.

***

### Phase 5 — Integration tests

Once Phases 1–4 are all green, these integration tests validate the full end-to-end path without requiring real Parquet data.

**File: `tests/integration/test_empirical_runner.py`**

```python
# tests/integration/test_empirical_runner.py
"""Integration tests: EmpiricalCalibrationRunner with synthetic targets."""
import pytest
import numpy as np
from pyworldx.calibration.empirical import EmpiricalCalibrationRunner
from pyworldx.data.bridge import CalibrationTarget


@pytest.fixture
def runner_no_parquet(tmp_path):
    """Runner pointing at an empty (but existing) aligned dir."""
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    return EmpiricalCalibrationRunner(aligned_dir=aligned)


def test_runner_load_targets_empty_dir_returns_empty_list(runner_no_parquet):
    targets = runner_no_parquet.load_targets()
    # data_pipeline not installed → graceful empty list
    assert isinstance(targets, list)


def test_runner_quick_evaluate_with_synthetic_targets(
    runner_no_parquet, full_registry, fake_engine_factory
):
    """quick_evaluate should work even without Parquet data if targets injected."""
    targets = [
        CalibrationTarget(
            variable_name="POP",
            years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
            values=np.array([3.0e9, 3.7e9, 4.4e9, 5.3e9, 6.1e9]),
            unit="persons", weight=1.0, source="synthetic", nrmsd_method="direct",
        )
    ]
    # Inject targets directly via bridge.compare
    traj, t_idx = fake_engine_factory(full_registry.get_defaults())
    result = runner_no_parquet.bridge.compare(targets, traj, t_idx)
    assert np.isfinite(result.composite_nrmsd)
    assert result.n_targets == 1


def test_runner_run_with_no_targets_returns_empty_report(
    runner_no_parquet, full_registry, fake_engine_factory
):
    """If load_targets returns [], run() returns an EmpiricalCalibrationReport
    with empirical_targets_loaded == 0 and calibrated_parameters == {}."""
    report = runner_no_parquet.run(
        registry=full_registry,
        engine_factory=fake_engine_factory,
    )
    assert report.empirical_targets_loaded == 0
    assert report.calibrated_parameters == {}
    assert report.converged is False


def test_full_population_calibration_smoke(full_registry):
    """Smoke test: single-sector calibration with synthetic targets.

    Uses a 2-trajectory Morris + 32-sample Sobol to keep wall time < 60s.
    This is the key end-to-end test for the whole fixed CLI path.
    """
    from pyworldx.calibration.empirical import (
        _resolve_registry,
        build_sector_engine_factory,
    )
    from pyworldx.data.bridge import DataBridge, CalibrationTarget
    from pyworldx.calibration.metrics import CrossValidationConfig
    from types import SimpleNamespace
    import tempfile
    from pathlib import Path

    # Step 1: resolve registry via the fixed function
    args = SimpleNamespace(sector="population", params=None)
    registry, requested = _resolve_registry(args)
    assert len(requested) == 3

    # Step 2: build engine factory
    engine_factory = build_sector_engine_factory("population")

    # Step 3: build synthetic targets
    defaults = registry.get_defaults()
    traj, time = engine_factory(defaults)
    synthetic_targets = [
        CalibrationTarget(
            variable_name="POP",
            years=np.array([1960, 1970, 1980, 1990, 2000], dtype=int),
            values=np.interp([1960, 1970, 1980, 1990, 2000], time, traj["POP"])
                   * np.array([0.98, 1.0, 1.02, 0.99, 1.01]),  # 1-2% noise
            unit="persons", weight=1.0, source="synthetic", nrmsd_method="direct",
        )
    ]

    # Step 4: build objective and run (tiny budget for speed)
    bridge = DataBridge()
    objective = bridge.build_objective(
        synthetic_targets, engine_factory,
        train_start=1960, train_end=1990,
    )

    from pyworldx.calibration.pipeline import run_calibration_pipeline
    from pyworldx.calibration.metrics import CrossValidationConfig

    cv = CrossValidationConfig(
        train_start=1960, train_end=1990,
        validate_start=1991, validate_end=2000,
    )
    report = run_calibration_pipeline(
        objective_fn=objective,
        registry=registry,
        cross_val_config=cv,
        morris_trajectories=2,
        sobol_samples=32,
        bayesian_n_trials=0,   # skip Bayesian for speed
    )

    assert report.calibration is not None
    assert report.calibration.total_nrmsd < 1.0   # should be close to 0 on synthetic data
```

***

### Phase 6 — CLI smoke test (end-to-end)

**File: `tests/integration/test_empirical_cli_smoke.py`**

```python
# tests/integration/test_empirical_cli_smoke.py
"""Verifies the CLI --sector flag wires through _resolve_registry correctly."""
import sys
import subprocess
import pytest


def test_cli_help_exits_cleanly():
    result = subprocess.run(
        [sys.executable, "-m", "pyworldx.calibration.empirical", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--sector" in result.stdout


def test_cli_unknown_sector_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "pyworldx.calibration.empirical",
         "--sector", "bogus_sector",
         "--dry-run"],   # assumes --dry-run flag exists to avoid full calibration
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "No parameters found" in result.stderr or "Unknown" in result.stderr


def test_cli_unknown_param_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "pyworldx.calibration.empirical",
         "--sector", "population",
         "--params", "does.not.exist",
         "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Unknown parameter" in result.stderr
```

***

## Execution Order and File Map

| Order | File | Status | Purpose |
|---|---|---|---|
| 1 | `tests/conftest.py` | Extend existing | Add `full_registry`, `fake_engine_factory`, `minimal_targets` fixtures |
| 2 | `tests/unit/test_parameters.py` | New — all GREEN | Lock down `ParameterRegistry` contract; catch regressions |
| 3 | `tests/unit/test_bridge.py` | New — all GREEN | Lock down `DataBridge` contract; NRMSD math correctness |
| 4 | `tests/unit/test_empirical_cli.py` | New — **RED** until step 5 | Specify `_resolve_registry()` behavior |
| 5 | `pyworldx/calibration/empirical.py` | Patch — add `_resolve_registry()` | Turn step 4 GREEN |
| 6 | `pyworldx/calibration/empirical.py` | Patch — replace broken CLI block | Use `_resolve_registry()` in the entrypoint |
| 7 | `tests/unit/test_engine_factory.py` | New — **RED** until step 8 | Specify `build_sector_engine_factory()` |
| 8 | `pyworldx/calibration/empirical.py` | Add `build_sector_engine_factory()` | Turn step 7 GREEN |
| 9 | `tests/integration/test_empirical_runner.py` | New — GREEN after 1–8 | Full path with synthetic data |
| 10 | `tests/integration/test_empirical_cli_smoke.py` | New — GREEN after 1–8 | CLI subprocess smoke test |

***

## Running the Tests

```bash
# Phase 1–2 only (fast, no engine needed)
pytest tests/unit/test_parameters.py tests/unit/test_bridge.py -v

# Phase 3–4 (will be RED until patches applied)
pytest tests/unit/test_empirical_cli.py tests/unit/test_engine_factory.py -v

# After patching
pytest tests/unit/ -v

# Full suite including integration (slow — smoke test runs 2-trajectory Morris)
pytest tests/ -v --timeout=120

# Just the end-to-end smoke test
pytest tests/integration/test_empirical_runner.py::test_full_population_calibration_smoke -v -s