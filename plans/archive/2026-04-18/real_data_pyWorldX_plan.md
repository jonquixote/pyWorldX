# pyWorldX Data Pipeline — Build Plan

**Goal:** A mini-app that collects, organizes, and prepares all 37 data sources
documented in `real_data_pyWorldX.md` into calibration-ready, ontology-aligned
time series for pyWorldX's World3-03 calibration.

**Location:** `data_pipeline/` at project root.
**Git status:** Ignored from pyWorldX (listed in `.gitignore`). Can be extracted
to a separate repo later.
**Dependencies:** `pandas`, `duckdb`, `requests`, `typer`, `pydantic` — all
lightweight, no heavy frameworks.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLI (Typer)                          │
│   collect → validate → transform → align → quality → export  │
└──────────────┬──────────────────────────────┬──────────┘
               │                              │
        ┌──────▼──────┐               ┌───────▼───────┐
        │   Connectors │               │   Transformers │
        │  (37 sources)│               │  (8 transforms)│
        └──────┬──────┘               └───────┬───────┘
               │                              │
        ┌──────▼──────┐               ┌───────▼───────┐
        │  Raw Store   │               │  Aligned Store │
        │  (Parquet)   │               │   (Parquet)    │
        └──────┬──────┘               └───────┬───────┘
               │                              │
        ┌──────▼──────────────────────────────▼───────┐
        │           Metadata Database (SQLite)         │
        │   source_versions, fetch_log, quality_report  │
        └──────────────────────────────────────────────┘
```

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Orchestration** | Simple Python + `concurrent.futures` | 37 fetches, not a complex DAG. No need for Dagster/Prefect/Luigi. |
| **Raw storage** | Parquet (one file per source) | Columnar, fast, self-describing, works with DuckDB/Pandas. |
| **Metadata store** | SQLite | Embedded, zero-config, ACID, tracks versions/checksums/fetch times. |
| **Query engine** | DuckDB | Blazing-fast SQL over Parquet files. Zero setup — just `duckdb.connect()`. |
| **CLI** | `typer` | Modern Python CLI, auto-generates `--help`, type-safe. |
| **Config** | `pydantic` settings | Type-validated config for API keys, date ranges, cache TTLs. |
| **No server** | All local, no web UI | This is a data prep tool, not a service. Runs on demand. |

---

## Directory Structure

```
data_pipeline/
├── __init__.py
├── __main__.py              # CLI entry: python -m data_pipeline collect
├── config.py                # Settings: date ranges, API keys, cache TTL
├── schema.py                # Pydantic models: SourceDef, FetchResult, QualityReport
│
├── connectors/              # One module per source group
│   ├── __init__.py
│   ├── world_bank.py        # World Bank indicators + GDP deflator
│   ├── un_population.py     # UN WPP 2024 CSV downloads
│   ├── faostat.py           # FAO API + FBS bulk CSV
│   ├── noaa.py              # NOAA CO₂ text files
│   ├── owid.py              # Our World in Data catalog
│   ├── usgs.py              # USGS Mineral Commodity Summaries
│   ├── unido.py             # UNIDO INDSTAT (manual download helper)
│   ├── undp.py              # UNDP HDR (manual download helper)
│   ├── fred.py              # FRED API (requires key)
│   ├── maddison.py          # Maddison Project via OWID or Excel
│   ├── pwt.py               # Penn World Table 11.0 Excel
│   ├── eia.py               # EIA API (requires key)
│   ├── edgar.py             # EDGAR emissions portal
│   ├── hyde.py              # HYDE database CSV
│   ├── gcp.py               # Global Carbon Budget XLSX
│   ├── primap.py            # PRIMAP-hist Zenodo CSV
│   ├── ceds.py              # CEDS Zenodo CSV (7 pollutants)
│   ├── ei_review.py         # Energy Institute Statistical Review
│   ├── ihme_gbd.py          # IHME GBD (manual download helper)
│   ├── hmd.py               # Human Mortality Database (manual)
│   ├── nasa_giss.py         # NASA GISS temperature text files
│   ├── berkeley_earth.py    # Berkeley Earth text files
│   ├── footprint_network.py # NFA 2025 CSV
│   ├── imf_weo.py           # IMF WEO via `weo` package
│   ├── oecd.py              # OECD via SDMX
│   ├── gapminder.py         # Gapminder CSV per indicator
│   ├── nasa_earthdata.py    # NASA Earthdata (login required)
│   ├── climate_trace.py     # Climate TRACE asset-level data
│   ├── climate_watch.py     # Climate Watch / WRI GHG
│   ├── carbon_atlas.py      # Global Carbon Atlas land-use flux
│   ├── un_comtrade.py       # UN Comtrade commodity API
│   └── nebel_2023.py        # Nebel et al. 2023 PLOS ONE supplement
│
├── transforms/              # Data cleaning / reshaping
│   ├── __init__.py
│   ├── reshape.py           # Wide→long, melt, pivot, rename
│   ├── interpolation.py     # 5-year→annual, fill gaps
│   ├── aggregation.py       # Country→world aggregate
│   ├── deflation.py         # Nominal→constant prices (requires world_bank deflator)
│   ├── per_capita.py        # Total→per-capita conversions
│   ├── unit_conversion.py   # Unit harmonization (kcal↔tonnes↔USD)
│   ├── gap_detection.py     # Find missing years, flag them
│   ├── outlier_detection.py # Z-score / IQR anomaly flags
│   └── nebcal_transform.py  # Reconstruct Nebel 2023 proxy series from supplement
│
├── alignment/               # Map to pyWorldX ontology
│   ├── __init__.py
│   ├── ontology_map.py      # Source variable → pyWorldX entity mapping
│   └── country_map.py       # ISO3 ↔ pyWorldX country codes
│
├── storage/                 # Raw + aligned data persistence
│   ├── __init__.py
│   ├── parquet_store.py     # Read/write Parquet with metadata
│   ├── metadata_db.py       # SQLite: source_versions, fetch_log, checksums
│   └── cache.py             # HTTP response cache with TTL + content-hash
│
├── quality/                 # Data quality assessment
│   ├── __init__.py
│   ├── coverage.py          # Year coverage % per source/variable
│   ├── freshness.py         # Days since source last updated
│   ├── consistency.py       # Cross-source correlation checks
│   └── report.py            # Generate HTML/Markdown quality report
│
├── export/                  # Output for pyWorldX calibration
│   ├── __init__.py
│   ├── connector_result.py  # Generate pyworldx.data.connectors.base.ConnectorResult
│   ├── calibration_csv.py   # NRMSD-ready CSVs aligned to spec targets
│   └── manifest.py          # Data manifest: what was collected, when, from where
│
├── cli.py                   # Typer CLI: collect, validate, transform, export
├── pipeline.py              # Master pipeline: orchestrate all stages
└── tests/                   # Unit tests for connectors + transforms
    ├── __init__.py
    ├── fixtures/            # Synthetic CSVs for manual-download connectors
    │   ├── unido_indstat4_sample.csv   # 5 countries, 3 years, correct schema
    │   ├── undp_hdr_sample.csv         # 5 countries, 5 years, correct schema
    │   ├── ihme_gbd_sample.csv         # 3 countries, 3 years, correct schema
    │   └── hmd_life_table_sample.txt   # 1 country, correct column format
    ├── test_connectors.py
    ├── test_transforms.py
    └── test_alignment.py
```

---

## Unified Data Schema

Every source, after fetching and initial cleaning, gets written to a standard
Parquet schema. This is the **raw store contract**:

```python
# Raw store schema (one .parquet per source)
{
    "source_id": str,          # e.g. "world_bank", "gcp", "pwt"
    "source_variable": str,    # Original variable name (e.g. "SP.POP.TOTL")
    "country_code": str,       # ISO 3166-1 alpha-3
    "country_name": str,       # Human-readable
    "year": int,               # Calendar year
    "value": float,            # Numeric value (always float)
    "unit": str,               # Source unit (e.g. "persons", "current USD")
    "original_value": float,   # Value before any cleaning (for audit)
    "fetch_timestamp": str,    # ISO 8601 UTC
    "source_version": str,     # e.g. "WPP2024", "PWT11.0", "NFA_2025"
    "checksum": str,           # SHA-256 of source file at fetch time
}
```

After transformation and ontology alignment, data gets written to the **aligned store**:

```python
# Aligned store schema (one .parquet per pyWorldX ontology entity)
{
    "entity": str,             # pyWorldX ontology name (e.g. "population.total")
    "country_code": str,
    "country_name": str,
    "year": int,
    "value": float,            # Value in canonical units
    "unit": str,               # Canonical unit (e.g. "persons")
    "source_id": str,          # Which source provided this
    "proxy_method": str,       # If derived, how (spec §8.1 requirement)
    "quality_flag": str,       # "OK", "INTERPOLATED", "GAP_FILLED", "OUTLIER"
    "transform_log": str,      # JSON array of transforms applied
    "generated_at": str,       # ISO 8601 UTC
}
```

---

## CLI Interface

```bash
# Fetch all sources (parallel where possible)
python -m data_pipeline collect

# Fetch specific sources
python -m data_pipeline collect --source world_bank --source gcp --source pwt

# Fetch spec-critical sources only (the 11 needed for NRMSD gates)
python -m data_pipeline collect --tier S --tier A

# Validate raw data (gap detection, outlier flags, checksum verification)
python -m data_pipeline validate

# Transform: reshape, interpolate, deflate, per-capita
python -m data_pipeline transform

# Align to pyWorldX ontology entities
python -m data_pipeline align

# Generate quality report
python -m data_pipeline quality --format markdown

# Export calibration-ready CSVs for pyWorldX
python -m data_pipeline export --target nrmsd
python -m data_pipeline export --target connectors

# Full pipeline (collect → validate → transform → align → quality → export)
python -m data_pipeline run

# Check what's already cached vs what needs refreshing
python -m data_pipeline status

# Clear cache
python -m data_pipeline clear-cache --source all
```

---

## Source Priority Phases

Sources are grouped by dependency and effort. The pipeline can be run incrementally.

### Phase 1: Spec-Critical Quick Wins (No Auth)
These are the **8 sources** that block the NRMSD validation gate. All are
zero-auth direct downloads.

| # | Source | Connector Module | Output Entity | Effort |
|---|---|---|---|---|
| 1 | Nebel 2023 supplement | `nebel_2023.py` | Industrial output, food, services, pollution proxy | Small |
| 2 | GCP Fossil CO₂ | `gcp.py` | `emissions.co2_fossil` | Small |
| 3 | NOAA CO₂ | `noaa.py` | `pollution.atmospheric_co2` | Trivial |
| 4 | World Bank | `world_bank.py` | `population.total`, `gdp.current_usd` | Small |
| 5 | OWID | `owid.py` | Multiple (Maddison GDP, energy, CO₂) | Small |
| 6 | USGS | `usgs.py` | `resources.nonrenewable_stock` | Small |
| 7 | PRIMAP-hist | `primap.py` | `emissions.ghg_multi_gas` | Small |
| 8 | CEDS | `ceds.py` | `emissions.so2`, `emissions.nox`, `emissions.bc` | Small |

### Phase 2: Portal Downloads (2-3 days)
| # | Source | Connector Module | Notes |
|---|---|---|---|
| 9 | UN Population | `un_population.py` | CSV download, 5-year periods → annual via interpolation |
| 10 | UNIDO | `unido.py` | Manual download helper (no API) |
| 11 | UNDP HDR | `undp.py` | Manual download helper |
| 12 | FAOSTAT + FBS | `faostat.py` | SDMX API + bulk CSV |
| 13 | Footprint Network | `footprint_network.py` | Registration required, CSV download |
| 14 | Energy Inst. Review | `ei_review.py` | Single Excel workbook |
| 15 | PWT 11.0 | `pwt.py` | Excel download, capital detail file |

### Phase 3: Registration Required (1-2 days)
| # | Source | Connector Module | Auth |
|---|---|---|---|
| 16 | EIA | `eia.py` | Free API key |
| 17 | FRED | `fred.py` | Free API key |
| 18 | IHME GBD | `ihme_gbd.py` | Free registration |
| 19 | HMD | `hmd.py` | Free registration (1-2 day approval) |

### Phase 4: SDMX + Complex APIs
| # | Source | Connector Module | Notes |
|---|---|---|---|
| 21 | OECD | `oecd.py` | SDMX protocol via `sdmx1` library |
| 22 | IMF WEO | `imf_weo.py` | SDMX or `weo` package |
| 23 | UN Comtrade | `un_comtrade.py` | Commodity API v2 |
| 24 | HYDE | `hyde.py` | NetCDF or CSV from Kaggle |

### Phase 5: Validation Anchors (Optional)
| # | Source | Connector Module | Notes |
|---|---|---|---|
| 25 | NASA GISS | `nasa_giss.py` | Text file parsing |
| 26 | Berkeley Earth | `berkeley_earth.py` | Text file parsing |
| 27 | Gapminder | `gapminder.py` | CSV per indicator |
| 28 | NASA Earthdata | `nasa_earthdata.py` | Login required, NetCDF |
| 29 | Climate TRACE | `climate_trace.py` | GeoJSON/CSV download |
| 30 | Climate Watch | `climate_watch.py` | CSV download |
| 31 | Global Carbon Atlas | `carbon_atlas.py` | NetCDF/GeoTIFF |
| 32 | Maddison (direct) | `maddison.py` | Excel download (alternative to OWID) |

---

## Transform Pipeline

Each transform is idempotent and logged in the `transform_log` field.

| Step | Module | What It Does | Input | Output |
|---|---|---|---|---|
| **1. Reshape** | `transforms/reshape.py` | Wide→long format, melt period columns, standardize names | Raw Parquet | Long-format Parquet |
| **2. Interpolate** | `transforms/interpolation.py` | 5-year→annual (UN WPP), fill gaps ≤3 years | Long Parquet | Annualized Parquet |
| **3. Aggregate** | `transforms/aggregation.py` | Country-level→world aggregate (population-weighted or sum) | Long Parquet | World-aggregate series |
| **4. Deflate** | `transforms/deflation.py` | Nominal USD→constant 2017 USD using World Bank GDP deflator | Long Parquet | Real-value series |
| **5. Per-capita** | `transforms/per_capita.py` | Total→per-capita using population series | Long Parquet | Per-capita series |
| **6. Unit convert** | `transforms/unit_conversion.py` | kcal↔tonnes, current↔constant prices, etc. | Long Parquet | Canonical-unit series |
| **7. Gap detect** | `transforms/gap_detection.py` | Flag years with missing data, mark `quality_flag` | Long Parquet | Flagged series |
| **8. Outlier** | `transforms/outlier_detection.py` | Z-score >3 or IQR-based anomaly flags | Flagged series | Final clean series |
| **9. Nebel reconstruct** | `transforms/nebcal_transform.py` | Reconstruct GDP-deflated industrial output, food, services, pollution from Nebel 2023 supplement | Raw Parquet + World Bank deflator | Nebel-aligned series |

### Transform Dependency Graph

Transforms are **not independent**. `pipeline.py` enforces this DAG:

```python
TRANSFORM_DEPENDENCIES: dict[str, list[str]] = {
    "reshape": [],                    # No deps — always runs first
    "interpolation": ["reshape"],     # Needs long format
    "aggregation": ["reshape"],       # Can run in parallel with interpolation
    "deflation": ["reshape"],         # BUT requires world_bank raw data (validated at runtime)
    "per_capita": ["reshape"],        # Runtime check: population series must be in raw store
    "unit_conversion": ["deflation"], # Constant prices before unit harmonization
    "gap_detection": [                # Runs on final clean data
        "interpolation", "aggregation",
        "per_capita", "unit_conversion",
    ],
    "outlier_detection": ["gap_detection"],  # Last — runs on flagged data
    "nebcal_transform": [             # Needs raw supplement + deflator
        "reshape",
    ],  # Runtime check: world_bank deflator must be in raw store
}
```

**Runtime validation:** Before executing any transform, `pipeline.py` checks:
1. All dependency transforms completed successfully
2. Required source data exists in the raw store (e.g., deflation → checks for World Bank GDP deflator)
3. If a dependency is missing, the transform is **skipped with a warning**, not silently failed.

---

## Ontology Alignment

Maps cleaned source variables to pyWorldX ontology entities.

| pyWorldX Entity | Sources (priority order) | NRMSD Bound | Notes |
|---|---|---|---|
| `population.total` | UN WPP (1950+), Maddison (1820-1949), HYDE (pre-1820) | — | Blend with overlap detection |
| `capital.industrial_stock` | PWT 11.0 `cn` | — | Split industrial vs service using capital detail |
| `agriculture.food` | FAOSTAT FBS, Nebel 2023 food series | 0.292 change-rate | Caloric conversion |
| `agriculture.food_per_capita` | Derived from food ÷ population | 1.108 change-rate | Spec §8.2 unit chain |
| `resources.nonrenewable_stock` | USGS reserves - UN Comtrade cumulative extraction | 0.757 change-rate | Stock(t) = initial - cumulative |
| `pollution.persistent_load` | GCP + EDGAR + PRIMAP + Nebel 2023 pollution | 0.337 change-rate | Blend CO₂ + reactive pollutants |
| `welfare.hdi` | UNDP HDR (1990+), Gapminder proxy (pre-1990) | 0.178 direct | Proxy from life expectancy + literacy |
| `emissions.co2_fossil` | GCP (1750+), EDGAR (1970+), NOAA (1958+) | — | Cross-validate overlap period |
| `emissions.so2` | CEDS (1750+) | — | Reactive pollutant |
| `ecological_footprint.total` | NFA 2025 | 0.343 direct | Consumption-based |

---

## Quality Assessment

After all transforms and alignment, generate a quality report:

```markdown
# Data Quality Report — pyWorldX Calibration Dataset

## Coverage
| Entity | Years Available | Coverage % | Primary Source | Gaps |
|--------|---------------|-----------|---------------|------|
| population.total | 1820-2024 | 98.5% | UN WPP + Maddison | 1820-1849 (HYDE proxy) |
| capital.industrial_stock | 1950-2023 | 100% | PWT 11.0 | Pre-1950: estimated |
| agriculture.food | 1961-2024 | 95.2% | FAOSTAT | 1900-1960: HYDE proxy |
| ... | ... | ... | ... | ... |

## Cross-Source Consistency

**Flow variables** (emissions, population, GDP) — Pearson correlation:
| Variable | Source A | Source B | Overlap Period | Correlation | Max Divergence |
|----------|----------|----------|---------------|------------|---------------|
| CO₂ emissions | GCP | EDGAR | 1970-2023 | r=0.998 | 2.1% (2020) |
| Population | UN WPP | World Bank | 1960-2024 | r=1.000 | 0.01% |
| GDP | World Bank | OWID/Maddison | 1960-2008 | r=0.997 | 3.2% |

**Stock variables** (capital, resources) — Level agreement (spec NRMSD bounds):
| Variable | Source A | Independent Estimate | Year | Level Error | Spec Bound |
|----------|----------|---------------------|------|------------|-----------|
| Nonrenewable stock | USGS reserves | UN Comtrade cumulative extraction | 2020 | <10% | 0.757 NRMSD |
| Industrial capital | PWT 11.0 `cn` | EI Stat. Review energy-capital proxy | 2023 | <15% | — |
| Arable land | FAOSTAT | HYDE cropland (1961 anchor) | 1961 | <5% | — |

**Spec §13.1 NRMSD validation** (after alignment):
| Entity | NRMSD Target | Method | Status |
|--------|-------------|--------|--------|
| Industrial output | ≤ 0.321 direct | vs Nebel 2023 supplement | — |
| Food production | ≤ 0.292 change-rate | vs Nebel 2023 supplement | — |
| Service output | ≤ 0.354 direct | vs Nebel 2023 supplement | — |
| Pollution index | ≤ 0.337 change-rate | vs Nebel 2023 supplement | — |
| Ecological footprint | ≤ 0.343 direct | vs NFA 2025 | — |
| Human welfare (HDI) | ≤ 0.178 direct | vs IHME GBD + HMD | — |
| Nonrenewable stock | ≤ 0.757 change-rate | vs USGS + UN Comtrade | — |

## Freshness
| Source | Last Updated | Days Ago | Status |
|--------|-------------|----------|--------|
| World Bank | 2025-07-01 | 280 | ✅ Current |
| UN WPP | 2024-07-11 | 635 | ✅ Current (WPP 2024) |
| ... | ... | ... | ... |
```

---

## Export Formats

### NRMSD Calibration CSV
One CSV per spec §13.1 variable, ready for `nrmsd_direct` computation:

```
# pyWorldX NRMSD Calibration Series
# Entity: industrial_output (GDP-deflated)
# Sources: Nebel_2023, World_Bank, OWID_Maddison
# Generated: 2026-04-07T12:00:00Z
# Unit: constant_2017_USD_billions
year,value,source,quality_flag,proxy_method
1900,1234.5,nebel_2023,OK,GDP_deflated_industrial_output
1901,1245.6,nebel_2023,OK,
...
```

### ConnectorResult Generator
Python code that generates `ConnectorResult` objects (spec §8.1) for wiring
into pyWorldX's data connector infrastructure:

```python
from pyworldx.data.connectors.base import ConnectorResult

def get_world_population(country: str = "WLD") -> ConnectorResult:
    """World population from blended UN WPP + Maddison + HYDE."""
    # Loads from aligned store, returns ConnectorResult
    ...
```

### Data Manifest
JSON file recording exactly what was collected, when, from which source version:

```json
{
  "generated_at": "2026-04-07T12:00:00Z",
  "pipeline_version": "0.1.0",
  "sources": {
    "world_bank": {
      "version": "API_v2_2025-07",
      "fetched_at": "2026-04-07T10:00:00Z",
      "checksum_sha256": "abc123...",
      "indicators": ["SP.POP.TOTL", "NY.GDP.MKTP.CD", "NY.GDP.DEFL.KD.ZG"],
      "records_fetched": 12456
    },
    ...
  },
  "aligned_entities": {
    "population.total": {
      "sources_used": ["un_population", "maddison", "hyde"],
      "year_range": [1820, 2024],
      "blend_method": "priority_overlap",
      "gap_years": [1848, 1849],
      "proxy_methods": {"1820-1849": "HYDE_spatial_interpolation"}
    }
  }
}
```

---

## Configuration

```python
# data_pipeline/config.py
from pydantic import BaseModel
from typing import Optional

class PipelineConfig(BaseModel):
    """Settings for the data pipeline."""

    # Date ranges
    calibration_start: int = 1900
    calibration_end: int = 2020

    # API keys (set via env vars or .env file)
    fred_api_key: Optional[str] = None
    eia_api_key: Optional[str] = None

    # Cache settings
    cache_dir: str = "data_pipeline/.cache"
    cache_ttl_days: int = 7  # Re-fetch if source is older than this

    # Storage paths
    raw_dir: str = "data_pipeline/data/raw"
    aligned_dir: str = "data_pipeline/data/aligned"
    metadata_db: str = "data_pipeline/data/metadata.sqlite"

    # Parallel fetch settings
    max_workers: int = 8
    request_timeout_seconds: int = 30
    retry_attempts: int = 3

    # Quality thresholds
    max_gap_years: int = 3  # Flag gaps longer than this
    outlier_z_threshold: float = 3.0
```

---

## Implementation Sequence

### Week 1–2: Skeleton + First 3 Connectors
- [ ] Set up `data_pipeline/` directory structure
- [ ] Add data/cache dirs to `.gitignore` (track all code)
- [ ] Implement `config.py`, `schema.py`, `storage/` modules
- [ ] Implement `cli.py` with `collect`, `status` commands
- [ ] Build 3 well-understood connectors: World Bank, NOAA, GCP
- [ ] Write `parquet_store.py` and `metadata_db.py`
- [ ] Create `tests/fixtures/` synthetic CSVs for 4 manual-download connectors
- [ ] Test: `python -m data_pipeline collect --source world_bank --source noaa --source gcp`

### Week 3–4: Remaining Phase 1 Sources + Transform Foundation
- [ ] Build remaining Phase 1 connectors: OWID, USGS, PRIMAP, CEDS, Nebel 2023
- [ ] Test: `python -m data_pipeline collect --tier S` fetches all 8 sources
- [ ] Implement reshape + interpolation transforms
- [ ] Implement transform dependency graph in `pipeline.py`
- [ ] Test: dependency validation catches missing deflator before deflation runs

### Week 5–6: Remaining Transforms + Phase 2 Sources
- [ ] Implement aggregation, deflation, per-capita, unit conversion transforms
- [ ] Implement gap detection + outlier detection transforms
- [ ] Implement `nebcal_transform.py` (Nebel 2023 series reconstruction)
- [ ] Build Phase 2 connectors: UN Population, UNIDO, UNDP, FAOSTAT, Footprint Network, EI Review, PWT
- [ ] Test: `python -m data_pipeline transform` runs all transforms with correct ordering
- [ ] Test: Raw → transformed → aligned pipeline produces valid output

### Week 7: Ontology Alignment + Quality
- [ ] Implement `ontology_map.py` with full source→entity mapping
- [ ] Implement `country_map.py` ISO code standardization
- [ ] Implement all 4 quality modules (coverage, freshness, consistency, report)
- [ ] Implement stock-variable level agreement checks (NRMSD-based, not correlation)
- [ ] Test: `python -m data_pipeline quality` generates valid report with NRMSD validation table
- [ ] Test: Cross-source checks pass for both flows (r > 0.95) and stocks (level within spec bounds)

### Week 8: Export + Integration
- [ ] Implement `connector_result.py` generator (spec §8.1 compliant)
- [ ] Implement `calibration_csv.py` exporter
- [ ] Implement `manifest.py` for data provenance tracking
- [ ] Wire export outputs into pyWorldX's `data/connectors/` (copy or symlink)
- [ ] Test: `python -m data_pipeline export --target nrmsd` produces valid CSVs
- [ ] Test: End-to-end `python -m data_pipeline run` completes without errors
- [ ] Test: All 32 connectors pass unit tests (manual-download via fixtures)
- [ ] Documentation: Update `real_data_pyWorldX.md` with pipeline usage instructions

---

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| Source URL changes (common with gov portals) | Content-hash-based cache invalidation; graceful degradation with cached data |
| API rate limits | Exponential backoff, configurable `max_workers`, local HTTP cache |
| Manual download sources (UNIDO, UNDP, HMD, IHME) | `--check-files` flag verifies local copies exist; clear instructions in connector docstrings |
| Large files (PWT 11.0 capital detail ~50MB) | Streaming download, checksum verification, incremental Parquet writes |
| Nebel 2023 supplement file names unknown | `--list-supplements` command lists all available files; user verifies before fetch |
| Schema changes in source data | Pydantic validation on ingest; clear error messages on schema mismatch |
| Pre-1961 food data gap | Explicit `proxy_method` tagging; wider NRMSD tolerance for proxy years |

---

## Dependencies

```toml
# data_pipeline/pyproject.toml (standalone, can be merged into parent)
[project]
name = "pyworldx-data-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.1",
    "duckdb>=1.0",
    "requests>=2.31",
    "typer>=0.9",
    "pydantic>=2.0",
    "rich>=13.0",        # Progress bars, tables in CLI
    "openpyxl>=3.1",     # Excel file reading (PWT, EI Review, Maddison)
]

[project.optional-dependencies]
sdmx = ["sdmx1>=2.16"]          # For OECD, IMF WEO
fred = ["fredapi>=0.5"]         # For FRED connector
eia = ["eia-python"]            # For EIA connector (or use requests directly)
owid = ["owid-catalog"]         # For OWID connector
dev = ["pytest>=8.0", "ruff", "mypy"]
```

---

## Git Strategy

```bash
# Add to pyWorldX .gitignore — track ALL code, ignore only data and caches
echo "data_pipeline/data/" >> .gitignore         # Raw + aligned Parquet files
echo "data_pipeline/.cache/" >> .gitignore        # HTTP response cache
echo "data_pipeline/__pycache__/" >> .gitignore   # Python bytecode

# Everything else is version-controlled normally:
# ✅ data_pipeline/__init__.py
# ✅ data_pipeline/config.py, schema.py, cli.py, pipeline.py
# ✅ data_pipeline/connectors/*.py (all 32 connectors)
# ✅ data_pipeline/transforms/*.py (all 9 transforms)
# ✅ data_pipeline/alignment/*.py
# ✅ data_pipeline/storage/*.py
# ✅ data_pipeline/quality/*.py
# ✅ data_pipeline/export/*.py
# ✅ data_pipeline/tests/ (including fixtures/)
# ✅ data_pipeline/pyproject.toml

# Later: decide whether to extract to separate repo
# Option A: Keep in pyWorldX repo (simpler, coupled)
# Option B: Extract to pyworldx-data-pipeline repo (cleaner, reusable)
# Option C: Keep in pyWorldX but as a git submodule (hybrid)
```

---

## Success Criteria

The pipeline is "done" when:

1. `python -m data_pipeline run` completes without errors
2. All 11 spec-critical calibration variables (§13.1) have data from 1900-2020
3. Cross-source checks pass:
   - **Flow variables**: Pearson r > 0.95 for overlapping periods
   - **Stock variables**: Level agreement within spec NRMSD bounds (e.g., nonrenewable stock ≤ 0.757 change-rate vs independent estimate)
4. Quality report shows ≤5% gap years for all calibration variables
5. Export generates NRMSD-ready CSVs that pyWorldX's `nrmsd_direct` can consume
6. Data manifest is complete with source versions, checksums, and provenance
7. Running `run` a second time uses cached data (no re-fetches) unless TTL expired
8. All 32 connectors pass unit tests (including 4 manual-download connectors using synthetic fixtures)
