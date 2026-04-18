# Ensemble Parquet Exporter Plan

## Goal
Stop throwing away 99% of our Monte Carlo ensemble data. We will refactor the observability suite to export the full 1900-2100 time-series tensor (including all percentiles) into a high-performance, columnar Parquet file. To prevent file bloat for massive ensembles, we will introduce a configurable temporal resolution parameter.

## Proposed Changes

### `pyworldx/observability/`
#### [MODIFY] `reports.py`
- Update `build_ensemble_report()` to generate two artifacts instead of one:
  1. The existing lightweight JSON summary (for peak values and threshold queries). **Ensure peak detection and threshold queries continue to run on the full-resolution data.**
  2. A new `ensemble_trajectories.parquet` file containing the full percentile bands across time steps.
- **Parquet Schema Specification:** The exporter must write a "long format" schema to maximize downstream usability in Pandas/Polars: `(year, variable, p05, median, p95, min, max)`.
- Apply decimation (e.g., `traj[::temporal_resolution]`) **internally within `build_ensemble_report()` only to the Parquet write path**, ensuring the JSON peak detection is not compromised by downsampled data.

### `pyworldx/forecasting/`
#### [MODIFY] `ensemble.py`
- Add `temporal_resolution: int = 1` to `EnsembleSpec`.
- Pass the **full** `all_trajectories` DataFrame to the reporter, passing along the `temporal_resolution` parameter for the reporter to handle.

## Verification Plan
### Automated Tests
- Create tests asserting that `build_ensemble_report()` successfully writes a `.parquet` file to the output directory.
- Test the `temporal_resolution` decimation:
  - Verify that a 200-year simulation with `resolution=5` yields exactly 41 rows per variable in the output DataFrame.
  - **Verify that with `temporal_resolution=1` (the default), the row count equals the full simulation length (200 rows), serving as a boundary test.**

### Manual Verification
- Run a 1,000-member ensemble and load the resulting `ensemble_trajectories.parquet` in a Jupyter notebook using Pandas to verify the long-format schema and file size.
