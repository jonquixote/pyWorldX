# Calibration Uncertainties and Structural Limitations

This document records known structural limitations of the World3 engine
that affect calibration against empirical data.  These are **not bugs** —
they are intrinsic modelling choices that create measurable divergence
from observed historical trajectories.

---

## 1. `industrial_output` ≠ GDP  (Excluded from objective)

**Date:** 2026-04-25
**Affected entity:** `gdp.current_usd` → `industrial_output`
**Status:** Excluded from calibration objective via `excluded_from_objective: True`

### Background

World3's `industrial_output` variable is a **biophysical throughput metric**
measuring the flow of energy and materials through the industrial sector.
It is denominated in dimensionless "World3 units" and is driven by the
capital stock depreciation/investment feedback loop.

GDP, on the other hand, measures **market transactions** including services,
financial intermediation, government spending, and rent-seeking — none of
which exist in World3's system dynamics formulation.

### Evidence

| Metric | Engine (World3) | Empirical (OECD/WB) |
|--------|----------------|---------------------|
| Level at 2000 | 7.47 × 10¹⁰ | 1.03 × 10⁴ USD M |
| Scale ratio | — | 7.3 million : 1 |
| Annual growth 1970–2020 | **-0.03%/yr** (flat/declining) | **+3–5%/yr** (exponential) |

Even using `change_rate` NRMSD (which normalises away level differences),
the trajectory shapes are irreconcilable:  World3 IO asymptotes as capital
depreciates at the natural rate, while GDP compounds due to technological
progress, tertiary-sector expansion, and financialisation — dynamics that
World3 does not model.

### Impact on calibration

With `industrial_output` in the objective, it dominated the composite NRMSD
(8.54 out of 2.33 composite) and distorted optimizer gradients away from
the five sectors where World3's dynamics are structurally sound.  The
Optuna optimiser could not move the IO score at all (8.5418 → 8.5418
across 100 trials).

### Decision

`gdp.current_usd` and `gdp.per_capita` are marked
`excluded_from_objective: True` in `ENTITY_TO_ENGINE_MAP`.  They remain
in the map for diagnostic purposes (you can still compute their NRMSD
manually) but are not loaded as calibration targets.

### Resolution path

The planned v2.0 modernisation (see `synthesis_and_plan.md`, Phases 1–2)
contemplates:
- Endogenous total factor productivity (TFP) in the capital sector
- A financial sector with credit creation, debt dynamics, and GDP-like
  output accounting
- Service-sector value-added as a distinct stock

These structural additions would make `industrial_output` GDP-comparable.
Until then, the exclusion is the scientifically honest choice.

---

## 2. `IC` (Industrial Capital) growth trajectory mismatch

**Date:** 2026-04-25
**Affected entity:** `capital.industrial_stock` → `IC`
**Status:** Retained in objective with `change_rate` NRMSD

### Background

Empirical capital stock (PWT `rnna`, constant 2017 prices) grows at
2.4–4.9% annually.  World3's IC is approximately flat (-0.03%/yr) at
default parameters because depreciation nearly equals gross investment.

`change_rate` NRMSD partially compensates by comparing growth rates
rather than levels, yielding NRMSD ≈ 1.28 (vs. 8.54 for industrial_output).
IC is retained because the optimizer *can* improve it by adjusting
`capital.alic`, `capital.icor`, and `capital.initial_ic`.

### Resolution path

Same as §1 — endogenous TFP and capital deepening dynamics in v2.0.

---

## 3. `pollution_generation` — wrong levers for CO₂ emissions

**Date:** 2026-04-26
**Affected entity:** `emissions.co2_fossil` → `pollution_generation`
**Status:** Retained in objective; pollution params left at baseline (structurally unfittable)

### Background

World3's pollution sector has three tuneable parameters:
- `ahl70` — assimilation half-life (how fast pollution decays)
- `initial_ppol` — initial pollution stock level
- `pptd` — persistent pollution transmission delay

These control **assimilation and persistence** — how quickly pollution
dissipates once generated.  They do **not** control the generation rate
itself, which is driven by `industrial_output` (capital throughput).

### Evidence

Sequential sector calibration with population, capital, and agriculture
frozen showed the optimizer moved **zero** pollution parameters across
the full pipeline (Morris screening + 100 Optuna trials + Nelder-Mead).
All three params returned at their input values.  Train NRMSD was
identical to the agriculture pass (1.12), confirming zero gradient
from pollution params to `pollution_generation`.

### Impact

`pollution_generation` NRMSD sits at ~1.39 with the sequentially
calibrated params.  This is acceptable — the trajectory shape is
broadly correct (rising emissions track rising capital throughput)
even though the optimizer cannot fine-tune it.

### Why not unfreeze `icor`?

Unfreezing `capital.icor` (capital output ratio) would give the
optimizer an indirect lever on pollution via industrial throughput.
This was considered but rejected: re-optimizing capital and pollution
jointly risks destabilising the clean capital calibration (IC NRMSD
1.22, holdout < train).  The marginal improvement on pollution would
come at the cost of capital regression — a poor trade.

### Resolution path

Same as §1–2.  A v2.0 emissions module with explicit fossil fuel
combustion rates and carbon intensity coefficients would decouple
pollution generation from the coarse industrial throughput proxy.

---

## 4. Resources params at default — no aligned empirical data

**Date:** 2026-04-26
**Affected entities:**
- `resources.nonrenewable_stock` → `NR`
- `resources.extraction_index` → `resource_extraction_index`
- `resources.depletion_ratio` → `reserve_depletion_ratio`

**Status:** Params `initial_nr` and `policy_year` left at World3 defaults (1×10¹², 4000)

### Background

The resources sector has three engine variable mappings defined in
`ENTITY_TO_ENGINE_MAP`, but **no aligned parquet files exist** for any
of them.  The USGS mineral production pipeline (`data_pipeline/connectors/`)
successfully ingests world production data for 90+ commodities, and the
BP Statistical Review connector provides energy reserves — but neither
has been wired through the alignment layer to produce parquets that map
to `NR`, `resource_extraction_index`, or `reserve_depletion_ratio`.

### Impact

The sequential calibration CLI correctly exits with "No calibration
targets matched sector 'resources'" when run in dry-run mode.
`initial_nr` and `policy_year` remain at their World3 defaults.
This is acceptable for the Phase 2 baseline: NR depletion in the
calibrated engine shows 93.2% remaining at 2100, which is consistent
with World3's standard run behaviour.

### Resolution path

1.  **Wire USGS → aligned parquets:** Create aggregate "total world
    nonrenewable resource extraction" time series from the USGS mineral
    production data, mapping it to `resource_extraction_index`.
2.  **Wire BP → aligned parquets:** Map BP proved reserves totals to
    `NR` (stock) and compute `reserve_depletion_ratio` as extraction/stock.
3.  Re-run the resources calibration pass with the new data.

This is planned data-pipeline work, not an engine structural limitation.
