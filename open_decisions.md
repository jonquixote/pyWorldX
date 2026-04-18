# Open Decisions

**Date:** 2026-04-13

## 1. Data Connector Architecture

**Question:** Why does `pyworldx/data/connectors/` have 10 stubs while `data_pipeline/` has 27 working connectors?

**Status:** ✅ **RESOLVED** (Phase 0, v0.2.9)

**Decision:** Option C — `pyworldx/data/` delegates to `data_pipeline/` via the DataBridge. The 9 dead stub connectors were removed. Only `base.py` (DataConnector protocol) and `csv_connector.py` (local file loader) remain in `pyworldx/data/connectors/`. Architecture documented in `pyworldx/data/__init__.py`.

---

## 2. Policy Event Integration

**Question:** Scenarios define `PolicyEvent` records (STEP/RAMP/PULSE/CUSTOM) but the engine never invokes `apply()` during simulation. Was this deliberate ("callers handle it via `sector_factory`") or unfinished?

**Status:** ✅ **RESOLVED** (Phase 0, v0.2.9)

**Decision:** Option C — Engine accepts optional `policy_applier` and `exogenous_injector` callables. Applied at start of master loop before any sector compute. `run_scenarios()` builds these from Scenario objects automatically. `None` produces identical output to previous behavior. Built-in scenario targets fixed to use flat engine variable names.

---

## 3. Capital Stock Collateralization

**Question:** How should initial Capital stocks (IC, SC, AL) be collateralized mathematically in the debt pool creation equation?

**Status:** ❓ **UNRESOLVED** — New decision added from Q10

**Context from Q10:** The FinanceSector requires monetized capital stocks for debt collateral:
- `V_c,i = Stock_i × Price_market,i`
- Industrial Capital (IC): market value of manufacturing capacity, sensitive to innovation rates and work efficiency
- Social Service Capital (SC): value of public infrastructure (hospitals, schools)
- Agricultural Capital (AL): proxied through phosphorus supply or soil stability; value = food production income minus input/land maintenance costs

The 150% Debt-to-GDP limit gates loan availability. When `Total Debt > Σ V_c,i`, the system loses "financial resilience" and Investment Rate must be zeroed, triggering Tainter-style collapse.

**Options:**
- **A)** Endogenous price mechanism: compute market prices from profit margins and ore grade curves within the model
- **B)** Exogenous price inputs: feed historical price data from the data pipeline (FRED, World Bank)
- **C)** Hybrid: default to exogenous prices with endogenous override when market conditions deviate from historical ranges

**Decision:** Pending.

---

## 4. Integration Timestep for Finance/Stiff Equations

**Question:** Should master_dt be reduced from 1.0 year to support FinanceSector and stiff interlinked equations?

**Status:** ❓ **UNRESOLVED** — New decision added from Q05, Q09

**Context from Q&A:**
- Q05: "To avoid stiff equations when financial flows move faster than physical flows, use high-frequency internal timestep (literature recommends at least **1/512 of a year**) to ensure RK4 stability during rapid economic fluctuations"
- Q09: WORLD7 explicitly requires **1/512 year** (~17 hours) for "fully stable simulation for all interlinked modules"
- Current spec: master_dt = 1.0 year with 4:1 sub-stepping (0.25 year) for fast sectors

**Options:**
- **A)** Lower master_dt to 1/64 or 1/256 for runs with FinanceSector active; keep 1.0 year for standard World3 runs
- **B)** Keep master_dt = 1.0; use sub-stepping at much higher ratios (e.g., 64:1 or 256:1) for FinanceSector
- **C)** Variable master_dt: engine auto-detects stiff sectors and adjusts internally; exposes a `precision_mode` flag to callers

**Decision:** Pending. This affects performance, CI run times, and calibration pipeline design.
