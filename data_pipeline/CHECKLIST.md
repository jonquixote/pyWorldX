# pyWorldX Real Data — Master Checklist

Generated from `real_data_pyWorldX.md` + `real_data_pyWorldX_plan.md`.
Updated: April 8, 2026 (local work, not pushed to GitHub).

---

## API Keys & Accounts

| Source | Auth Type | URL | Status | Notes |
|---|---|---|---|---|
| FRED | API key | https://fred.stlouisfed.org/docs/api/api_key.html | ✅ In `.env` |
| EIA | API key | https://www.eia.gov/opendata/register.php | ✅ In `.env` |
| FAOSTAT | Bearer token | https://data.apps.fao.org/ | ⚠️ Token expired, OWID fallback active |
| NASA Earthdata | Registration | https://urs.earthdata.nasa.gov/ | ⚠️ Free login required |
| IHME GBD | Registration | https://healthdata.org/research-analysis/gbd | ✅ Automated via OWID |
| HMD | Registration | https://www.mortality.org | ✅ Automated via OWID |
| Footprint Network | Registration | https://footprint.info.yorku.ca/data/ | ✅ Automated via OWID |

---

## Connector Status (37 total)

### ✅ Working (29 connectors, actively fetching data)
| # | Source | Connector | Records | Notes |
|---|---|---|---|---|
| 1 | World Bank | `world_bank.py` | 34,036+ | 5 indicators (incl. services value added) |
| 2 | NOAA CO₂ | `noaa.py` | 67 | 1958-2025 |
| 3 | GCP | `gcp.py` | 23,863 | 1750-2023 fossil CO₂ |
| 4 | PRIMAP-hist | `primap.py` | 56,654 | Multi-gas GHG |
| 5 | CEDS | `ceds.py` | 15,000+ | 7 pollutants |
| 6 | FRED | `fred.py` | 2,619 | 6 series |
| 7 | EIA | `eia.py` | 5,000 | US energy |
| 8 | UNDP HDR | `undp.py` | 206 | HDI 1990-2022 |
| 9 | NASA GISS | `nasa_giss.py` | 21 | 1880-2025 |
| 10 | Carbon Atlas | `carbon_atlas.py` | 60,828 | Land-use CO₂ |
| 11 | Climate TRACE | `climate_trace.py` | 58 | 2015-2026 |
| 12 | OWID | `owid.py` | 16,000+ | 6 indicators + direct indicators |
| 13 | Nebel 2023 | `nebel_2023.py` | 1 | Metadata |
| 14 | OECD | `oecd.py` | 324 | SNA_TABLE4 |
| 15 | IMF WEO | `imf_weo.py` | 2 | Excel, Apr 2025 |
| 16 | FAOSTAT | `faostat.py` | 1,690+ | FBS World (token expired, OWID fallback) |
| 17 | PWT 11.0 | `pwt.py` | 13,690 | **Capital stock (rnna) 1950-2023** |
| 18 | HYDE 3.3 | `hyde.py` | 26,838 | OWID API |
| 19 | Maddison | `maddison.py` | 21,586 | OWID API |
| 20 | UN Population | `un_population.py` | 363,783 | HDX download |
| 21 | EI Review | `ei_review.py` | 26,838 | OWID API |
| 22 | Footprint Network | `footprint_network.py` | 26,838 | OWID API |
| 23 | Gapminder | `gapminder.py` | 4,935 | World Bank API |
| 24 | EDGAR | `edgar.py` | 32 | CO2 1970-2024 |
| 25 | IHME GBD | `ihme_gbd.py` | 6,780+ | OWID API |
| 26 | HMD | `hmd.py` | 525 | OWID API |
| 27 | USGS | `usgs.py` | 1+ | MCS PDF metadata + NR proxy |
| 28 | UNIDO | `unido.py` | 2,443 | World Bank API |
| 29 | OWID Daily Caloric | `owid.py` | 13,265 | FAO caloric supply 1274-2023 |

### ⚠️ Manual Download Helpers (3 connectors, code ready, tested)
| # | Source | Connector | Notes |
|---|---|---|---|
| 30 | UN Comtrade | `un_comtrade.py` | Auth required, tested ✅ |
| 31 | Climate Watch | `climate_watch.py` | API DNS failure, tested ✅ |
| 32 | Berkeley Earth | `berkeley_earth.py` | Servers down, NASA GISS alternative, tested ✅ |

---

## Pipeline Status

### Aligned Entities (40 entities from 34 sources)
| # | Entity | Source(s) | Year Range | Records | Notes |
|---|---|---|---|---|---|
| 1 | `emissions.co2_fossil` | GCP+PRIMAP+OWID+EDGAR | 1750-2024 | 273+ | |
| 2 | `emissions.land_use_co2` | Carbon Atlas | 1750-2023 | 274 | |
| 3 | `emissions.ghg_total` | Climate TRACE | 2022-2026 | 5 | |
| 4-10 | `emissions.so2/nox/bc/oc/co/nh3/nmvoc` | CEDS | 1750-2022 | 15,000+ | 7 pollutants |
| 11 | `emissions.co2_per_capita` | OWID | 1965-2024 | Varies | |
| 12 | `energy.consumption` | EIA | 2020-2024 | 5 | |
| 13 | `energy.primary_consumption` | OWID | 1965-2024 | 60 | |
| 14 | `atmospheric.co2` | NOAA | 1959-2025 | 67 | |
| 15 | `temperature.anomaly` | NASA GISS | 1880-1900 | 21 | |
| 16 | `demographics.life_expectancy` | OWID+HMD | Varies | Varies | |
| 17 | `food.supply.kcal_per_capita` | FAOSTAT+OWID | 1274-2023 | 159 | ✅ Covers Nebel window |
| 18 | `population.total` | FAOSTAT+OWID+UN Pop+Gapminder | 2010-2023 | 14+ | |
| 19 | `welfare.hdi` | UNDP HDR | 1990-2022 | 33 | |
| 20 | `gdp.deflator` | FRED | 1947-2025 | 79 | |
| 21 | `cpi` | FRED | 1947-2026 | 80 | |
| 22 | `gdp.current_usd` | FRED+OECD | 1947-2025 | 403+ | |
| 23 | `gdp.real` | FRED | 1947-2025 | 79 | |
| 24 | `gdp.maddison` | OWID | Varies | Varies | |
| 25 | `gdp.per_capita` | Gapminder | Varies | Varies | |
| 26 | `gni.per_capita` | World Bank | — | (mapped) | |
| 27 | `financial.fed_funds_rate` | FRED | 1954-2026 | 73 | |
| 28 | `economic.consumer_sentiment` | FRED | 1978-2026 | 49 | |
| 29 | `imf.weo_raw` | IMF | 1980-2029 | Excel | |
| 30 | `resources.nonrenewable_stock` | USGS | — | (mapped) | |
| 31 | **`capital.industrial_stock`** | **PWT 11.0** | **1950-2023** | **74** | **✅ NEW: rnna aggregated** |
| 32 | `health.dalys` | IHME GBD | Varies | 6,780 | |
| 33 | `health.child_mortality` | IHME GBD | Varies | 1,145 | |
| 34 | `health.life_expectancy` | IHME GBD | Varies | 525 | |
| 35 | `industry.manufacturing_value_added` | UNIDO | 1960-2024 | 2,443 | |
| 36 | `industry.value_added` | UNIDO | 1960-2024 | 2,443 | |
| 37 | `welfare.ecological_footprint` | Footprint Network | 1961-2022 | 26,838 | |
| 38 | `output.service_per_capita` | World Bank (pending) | — | — | Mapping ready, API timeout |
| 39 | `output.service_per_capita` (proxy) | GDP proxy | Varies | Varies | Deprecated, replaced |
| 40 | `land.cropland_hectares` | HYDE/OWID | Varies | Varies | |

### Normalizers (31)
All 42 raw sources have normalizers. No gaps.

### Ontology Mappings (51)
All 42 raw sources have ontology mappings. No gaps. Zero duplicate keys.

### Unit Bridge (34 mappings)
All pipeline units convert to World3 abstract units.

### Initial Conditions (10 sector stocks)
| Stock | Sector | Entity | Default Value |
|---|---|---|---|
| POP | population | population.total | 1.65e9 persons |
| PPOL | pollution | emissions.co2_fossil | 25,000 kt_CO2 |
| PPOL_land_use | pollution | emissions.land_use_co2 | 1,500 Mt_CO2 |
| PPOL_atmospheric | pollution | atmospheric.co2 | 295 ppm |
| food_supply_per_capita | agriculture | food.supply.kcal_per_capita | 2,400 kcal/day |
| temp_anomaly | pollution | temperature.anomaly | 0 degC |
| IC | industry | capital.industrial_stock | PWT rnna (1950-2023) |
| SC | service | output.service_per_capita | 500 USD/capita |
| NR | resources | resources.nonrenewable_stock | 1.0e12 resource_units |
| AL | agriculture | land.cropland_hectares | 1.0e9 hectares |

### CLI Commands (13 total)
| Command | Status |
|---|---|
| `collect` | ✅ |
| `status` | ✅ |
| `clear` | ✅ |
| `ls-raw` | ✅ |
| `ls-aligned` | ✅ |
| `run` | ✅ |
| `init-conditions` | ✅ |
| `nrmsd` | ✅ |
| `transform` | ✅ |
| `validate` | ✅ |
| `cross-check` | ✅ |
| `diff` | ✅ |
| `fetch-owid` | ✅ |

---

## Stats

- **Total Python files:** 97
- **Total lines of code:** 14,369+
- **Data pipeline tests:** 285+ ✅ (26 test files)
- **pyWorldX tests:** 353 ✅ (unaffected)
- **Connectors built:** 32/37
- **Actively fetching data:** 29 ✅
- **Manual download helpers:** 3 (all tested ✅)
- **Raw sources with normalizer:** 42/42 ✅
- **Raw sources with ontology mapping:** 42/42 ✅
- **Duplicate keys in ONTOLOGY_MAP:** 0 ✅
- **Aligned entities:** 40
- **Calibration CSVs exported:** 30
- **Normalizers:** 31
- **Ontology mappings:** 51
- **Unit bridge entries:** 34
- **Initial condition stocks:** 10 ✅
- **ConnectorResult type:** PipelineConnectorResult dataclass ✅
- **NRMSD formula:** Matches spec §9.1 (no abs in denominator) ✅
- **Transforms:** 9/9 ✅ (+ derive_per_capita)
- **Quality modules:** 4/4 ✅
- **Export modules:** 3/3 ✅
- **Aligned data merge:** ✅ merge with deduplication
