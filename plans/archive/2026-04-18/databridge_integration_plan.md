# DataBridge & Empirical Validation Integration Plan (Revised)

## Goal
Connect the existing 37-connector data pipeline to the pyWorldX engine's calibration system. We will implement an immutable `DataBridge` to normalize real-world units into relative indices with zero-guarding. Additionally, we will implement a rigorous rolling holdout validation protocol (train/test splits) and decouple canonical World3-03 structural consistency checks from empirical real-world calibration.

## Proposed Changes

### `pyworldx/data/`
#### [NEW] [bridge.py](file:///Users/johnny/pyWorldX/pyworldx/data/bridge.py)
- Create `CalibrationTarget` dataclass to hold variable names, years, values, and units.
- Define a custom `DataBridgeError` to catch and gracefully report stale or missing Parquet files rather than bubbling up raw `FileNotFoundError`s.
- Implement `DataBridge` as an immutable, thread-safe class (to avoid closure capture issues during parallel Nelder-Mead restarts):
  - `load_targets()`: Maps pipeline entities to engine variables via `ENTITY_TO_ENGINE_MAP`, raising `DataBridgeError` if files are missing.
  - `_normalize_to_index()`: Normalizes both empirical data and engine output to $X(t)/X(\text{train\_start})$. **Includes an epsilon guard and fallback to the first non-zero value if $X(\text{train\_start}) == 0$ (e.g., for early USGS zero-padded series).**
  - `build_objective()`: Constructs the objective function `dict[str, float] -> float` required by the optimizer, enforcing the train window for calculation.
  - `calculate_validation_score()`: A secondary method that evaluates NRMSD exclusively on the holdout validation window.

### `pyworldx/calibration/`
#### [NEW] [empirical.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/empirical.py)
- Implement `EmpiricalCalibrationRunner`:
  - `__init__(scenario: str = "standard_run")`: Accepts a scenario argument but defaults to `Standard Run` so we can calibrate against historical policies (e.g., `Historical Emissions Policy`). **Must eagerly validate the scenario string against the registered scenario set at construction time, raising a `ValueError` immediately to prevent late-failing after expensive data loads.**
  - Invokes `run_calibration_pipeline()` from `pipeline.py` using the `train` window objective function.
  - Post-processes the `CalibrationResult` to run `bridge.calculate_validation_score()` on the optimized parameters, filling the `validation_nrmsd` and triggering the `overfit_flagged` boolean if the score degrades beyond `CrossValidationConfig.overfit_threshold`.
  - **New Method:** `validate_structural_consistency()`: A decoupled method that specifically uses the `World3ReferenceConnector` to ensure the core W3-03 trajectories are intact, keeping this strictly isolated from the main empirical NRMSD objective function.

### `data_pipeline/connectors/`
#### [NEW] [world3_reference.py](file:///Users/johnny/pyWorldX/data_pipeline/connectors/world3_reference.py)
- Implement a `World3ReferenceConnector` to generate canonical World3-03 trajectories. This will only be used by the `validate_structural_consistency()` method to avoid circular calibration loops on unobservable proxy variables.

## Verification Plan

### Automated Tests
- Create `tests/test_databridge.py` to verify:
  - `_normalize_to_index()` correctly divides vectors by their base year and handles zeros safely with epsilon logic.
  - **`load_targets()` explicitly raises `DataBridgeError`** (using `pytest.raises` and a `tmp_path` fixture) when a Parquet file is absent, rather than leaking raw `FileNotFoundError`s.
- Create `tests/test_empirical_calibration.py` to run a mock `EmpiricalCalibrationRunner` and assert that:
  - The `validation_nrmsd` is correctly computed independently from the `train_nrmsd`.
  - **`train_nrmsd < validation_nrmsd` is NOT a hard failure condition** (mild degradation is healthy), but `overfit_flagged` strictly triggers when the gap exceeds `overfit_threshold`.

### Manual Verification
- Execute the pipeline end-to-end: `python -m pyworldx.calibration.empirical`
- Inspect the output report to confirm that the `DataBridge` correctly loaded pipeline Parquet files, optimized parameters on the 1970-2010 window, and scored the holdout 2010-2023 window without crashing on unit dimensionality errors or zero-padded time series.
