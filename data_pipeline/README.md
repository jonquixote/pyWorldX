# pyWorldX Data Pipeline

> **This is a reference implementation.** pyWorldX is designed to work with any data source. This pipeline demonstrates how to collect, transform, and align real-world data to the pyWorldX ontology. You can use it as-is, extend it with your own connectors, or replace it entirely — the core engine only requires `ConnectorResult` objects (see `pyworldx/data/connectors/base.py`).

> Production-grade data pipeline for World3-03 systems modeling. Collects, transforms, aligns, and validates 37 calibration data sources into NRMSD-ready entity series for pyWorldX.

---

## Quick Start

```bash
# Collect all available data
poetry run python -m data_pipeline collect

# Run the full pipeline (collect → transform → align → export → report)
poetry run python -m data_pipeline run

# Check status
poetry run python -m data_pipeline status

# View raw sources
poetry run python -m data_pipeline ls-raw

# View aligned entities
poetry run python -m data_pipeline ls-aligned
```

---

## Overview

The pyWorldX data pipeline is a **modular, unit-safe, auditable** ETL system that:

1. **Collects** data from 37 sources (World Bank, NOAA, GCP, PRIMAP, CEDS, FRED, EIA, NASA GISS, EDGAR, OWID, and more)
2. **Transforms** raw data through a 9-step chain (interpolation, aggregation, deflation, per-capita, unit conversion, outlier detection, gap detection)
3. **Aligns** source data to 36 pyWorldX ontology entities using configurable mappings
4. **Validates** data quality through coverage, freshness, and cross-source consistency checks
5. **Exports** NRMSD-ready calibration CSVs with provenance metadata

### Architecture

```
Sources (37) → Connectors → Raw Parquet → Transforms (9) → Aligned Parquet → Calibration CSVs
                    ↓              ↓              ↓               ↓
                Metadata DB   Quality Report   Ontology Map   Manifest JSON
```

---

## Pipeline Status

| Metric | Value |
|---|---|
| **Connectors** | 37 (29 active, 3 manual helpers, 5 alternatives) |
| **Aligned entities** | 40 from 34 sources |
| **Transforms** | 10/10 complete (+ derive_per_capita) |
| **Normalizers** | 31 |
| **Ontology mappings** | 51 |
| **Unit bridge** | 34 pipeline→World3 unit mappings |
| **Tests** | 285+ passing |
| **CLI commands** | 13 |

---

## CLI Commands

| Command | Description |
|---|---|
| `collect` | Fetch data from connectors (default: all) |
| `collect --source <id>` | Fetch a specific source |
| `collect --all` | Fetch all 37 connectors |
| `status` | Show collection status |
| `clear` | Clear cached/collected data |
| `ls-raw` | List raw Parquet sources |
| `ls-aligned` | List aligned Parquet entities |
| `run` | Full pipeline (collect → transform → align → export → report) |
| `run --skip-collect` | Transform/align existing raw data |
| `transform <source>` | Transform a specific source |
| `validate` | Run quality validation checks |
| `cross-check` | Cross-source consistency analysis |
| `diff <entity_a> <entity_b>` | Compare two aligned entities |
| `init-conditions --year <Y>` | Extract initial conditions for target year |
| `nrmsd` | Compute NRMSD scores |
| `fetch-owid` | Fetch OWID indicators |

---

## Connectors

### Actively Fetchable (28)

| # | Source | Records | Notes |
|---|---|---|---|
| 1 | World Bank | 34,036 | Population, GDP, GNI, GDP deflator |
| 2 | NOAA CO₂ | 67 | Mauna Loa annual mean, 1958-2025 |
| 3 | GCP | 23,863 | Country-level fossil CO₂, 1750-2023 |
| 4 | PRIMAP-hist | 56,654 | Multi-gas GHG, 1750-2022 |
| 5 | CEDS | 15,000+ | 7 pollutants: SO₂, NOx, BC, OC, CO, NH₃, NMVOC |
| 6 | FRED | 2,619 | 6 economic series, 1947-2025 |
| 7 | EIA | 5,000 | US energy consumption, 1960-2024 |
| 8 | UNDP HDR | 206 | HDI indices, 1990-2022 |
| 9 | NASA GISS | 21 | Global temperature anomaly, 1880-2025 |
| 10 | Carbon Atlas | 60,828 | Land-use CO₂ fluxes |
| 11 | Climate TRACE | 58 | Country-level emissions, 2015-2026 |
| 12 | OWID | 16,000+ | 6 indicators, 1800-2024 |
| 13 | Nebel 2023 | 1 | Calibration metadata |
| 14 | OECD | 324 | SNA_TABLE4 GDP, 1960-2024 |
| 15 | IMF WEO | 2 | WEO Excel, 1980-2029 |
| 16 | FAOSTAT | 1,690 | Food Balance Sheets, 2010-2023 |
| 17 | PWT 11.0 | 13,690 | Penn World Table Stata, 1950-2019 |
| 18 | HYDE 3.3 | 26,838 | History Database of the Global Environment |
| 19 | Maddison | 21,586 | Historical GDP, 1900-2023 |
| 20 | UN Population | 363,783 | Population prospects, 1950-2100 |
| 21 | EI Review | 26,838 | Primary energy consumption |
| 22 | Footprint Network | 26,838 | Ecological footprint, 1961-2022 |
| 23 | Gapminder | 4,935 | Development indicators |
| 24 | EDGAR | 32 | JRC GHG CO₂, 1970-2024 |
| 25 | IHME GBD | 6,780+ | DALYs, child mortality, life expectancy |
| 26 | HMD | 525 | Life expectancy, 1751-2023 |
| 27 | USGS | 1 | Mineral Commodity Summaries PDF |
| 28 | UNIDO | 2,443 | Manufacturing value added, 1960-2024 |

### Manual Helpers (3)

| Source | Notes |
|---|---|
| UN Comtrade | Auth required for API |
| Climate Watch | API DNS failure (covered by other sources) |
| Berkeley Earth | Servers down (NASA GISS is alternative) |

---

## Aligned Entities

| Entity | Sources | Year Range |
|---|---|---|
| `emissions.co2_fossil` | GCP + PRIMAP + OWID + EDGAR | 1750-2024 |
| `emissions.so2` | CEDS | 1750-2022 |
| `emissions.nox` | CEDS | 1750-2022 |
| `emissions.ghg_total` | Climate TRACE | 2022-2026 |
| `emissions.land_use_co2` | Carbon Atlas | 1750-2023 |
| `emissions.co2_per_capita` | OWID | 1965-2024 |
| `energy.consumption` | EIA | 2020-2024 |
| `energy.primary_consumption` | OWID | 1965-2024 |
| `atmospheric.co2` | NOAA | 1959-2025 |
| `temperature.anomaly` | NASA GISS | 1880-2025 |
| `demographics.life_expectancy` | OWID + HMD | Varies |
| `population.total` | FAOSTAT + OWID + UN Pop + Gapminder | 2010-2023 |
| `food.supply.kcal_per_capita` | FAOSTAT | 2010-2023 |
| `welfare.hdi` | UNDP HDR | 1990-2022 |
| `gdp.deflator` | FRED | 1947-2025 |
| `cpi` | FRED | 1947-2026 |
| `gdp.current_usd` | FRED + OECD | 1947-2025 |
| `gdp.real` | FRED | 1947-2025 |
| `gdp.maddison` | OWID | Varies |
| `gdp.per_capita` | Gapminder | Varies |
| `gni.per_capita` | World Bank | — |
| `financial.fed_funds_rate` | FRED | 1954-2026 |
| `economic.consumer_sentiment` | FRED | 1978-2026 |
| `imf.weo_raw` | IMF | 1980-2029 |
| `capital.industrial_stock` | PWT | 1950-2019 |
| `health.dalys` | IHME GBD | Varies |
| `health.child_mortality` | IHME GBD | Varies |
| `health.life_expectancy` | IHME GBD | Varies |
| `industry.manufacturing_value_added` | UNIDO | 1960-2024 |
| `industry.value_added` | UNIDO | 1960-2024 |
| `welfare.ecological_footprint` | Footprint Network | 1961-2022 |
| `resources.nonrenewable_stock` | USGS | — |

---

## Configuration

Set API keys in `data_pipeline/.env`:

```env
FRED_API_KEY=your_key
EIA_API_KEY=your_key
FAOSTAT_TOKEN=your_token
```

Environment variables:

```bash
export DATA_PIPELINE_RAW_DIR=data_pipeline/data/raw
export DATA_PIPELINE_ALIGNED_DIR=data_pipeline/data/aligned
export DATA_PIPELINE_CACHE_DIR=data_pipeline/.cache
export DATA_PIPELINE_METADATA_DB=data_pipeline/data/metadata.db
```

---

## Project Structure

```
data_pipeline/
├── __init__.py, __main__.py
├── config.py          # Pydantic config, .env loading
├── schema.py          # FetchResult, ConnectorResult types
├── pipeline.py        # DAG pipeline orchestrator
├── cli.py             # 13 Typer CLI commands
├── connectors/        # 32 connector modules
│   ├── world_bank.py, noaa.py, gcp.py, primap.py, ceds.py
│   ├── fred.py, eia.py, undp.py, nasa_giss.py
│   ├── carbon_atlas.py, climate_trace.py, owid.py, nebel_2023.py
│   ├── oecd.py, imf_weo.py, faostat.py, berkeley_earth.py
│   ├── un_population.py, unido.py, footprint_network.py
│   ├── ei_review.py, pwt.py, ihme_gbd.py, hmd.py
│   ├── hyde.py, maddison.py, gapminder.py, climate_watch.py
│   ├── un_comtrade.py, usgs.py, nasa_earthdata.py, edgar.py
├── transforms/        # 11 transform modules
│   ├── chain.py       # Transform chain executor
│   ├── normalize.py   # 26 normalizers
│   ├── reshape.py, interpolation.py, aggregation.py
│   ├── deflation.py, per_capita.py, unit_conversion.py
│   ├── gap_detection.py, outlier_detection.py, nebcal_transform.py
├── alignment/         # Entity alignment
│   ├── map.py         # 46 ontology mappings
│   └── initial_conditions.py
├── quality/           # Quality checks
│   ├── coverage.py, freshness.py, consistency.py, report.py
├── export/            # Export modules
│   ├── calibration_csv.py, manifest.py, connector_result.py
│   └── manifest_validation.py
├── calibration/       # NRMSD
│   └── nrmsd.py
├── storage/           # Storage layer
│   ├── parquet_store.py, metadata_db.py, cache.py
└── tests/             # 285+ tests (26 files)
```

---

## Tests

```bash
# Run all data pipeline tests
poetry run pytest data_pipeline/tests/ -v

# Run specific test file
poetry run pytest data_pipeline/tests/test_connectors.py -v

# Run pyWorldX core tests (unaffected by pipeline)
poetry run pytest tests/ -v

# Run all tests
poetry run pytest --ignore=tests/ data_pipeline/tests/ && pytest tests/
```

---

## Adding a New Connector

1. Create `connectors/my_source.py` with a `fetch_<name>(config)` function returning `FetchResult`
2. Add normalizer to `transforms/normalize.py` with `@register_normalizer("my_source_")`
3. Add ontology mapping to `alignment/map.py` in `ONTOLOGY_MAP`
4. Add CLI dispatch to `cli.py` `_fetch_source()` function
5. Add tests to `tests/test_<name>.py`

---

## Building Your Own Source

You don't need to use this pipeline at all. The pyWorldX engine consumes `ConnectorResult` objects via the `DataConnector` protocol defined in `pyworldx/data/connectors/base.py`:

```python
from dataclasses import dataclass, field
import pandas as pd

@dataclass
class ConnectorResult:
    series: pd.Series        # Time series indexed by year
    unit: str                # e.g. "Mt_CO2", "people", "constant_2015_USD"
    source: str              # Human-readable source name
    source_series_id: str    # Machine-readable identifier
    retrieved_at: str        # ISO timestamp
    vintage: str | None = None
    proxy_method: str | None = None
    transform_log: list[str] = field(default_factory=list)
```

A minimal custom connector that reads a local CSV:

```python
from datetime import datetime, timezone
import pandas as pd
from pyworldx.data.connectors.base import ConnectorResult

def fetch_my_data() -> ConnectorResult:
    df = pd.read_csv("my_data.csv")  # columns: year, value
    series = df.set_index("year")["value"].sort_index()
    return ConnectorResult(
        series=series,
        unit="Mt_CO2",
        source="My Local Dataset",
        source_series_id="my_data_co2",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
```

If you use this pipeline and want to bridge its output to the engine, `data_pipeline/export/connector_result.py` provides `PipelineConnectorResult` which mirrors the same interface.

---

## License

Part of pyWorldX. See parent project for license details.
