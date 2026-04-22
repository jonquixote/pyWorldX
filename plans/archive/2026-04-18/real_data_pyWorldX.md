# pyWorldX — Real Data Source Reference

**Purpose:** Exact instructions for wiring all 8 mandatory + 1 optional data connectors
with free, no-cost sources. Every URL, parameter, and authentication requirement
is documented here.

**Last verified:** April 2026

---

## 1. World Bank — GDP, Population, GNI

| Detail | Value |
|---|---|
| **Base URL** | `https://api.worldbank.org/v2/` |
| **Authentication** | None. No API key required. |
| **Rate limits** | None documented. |
| **Python library** | `requests` (no extra dependency) or `wbdata` (PyPI) |

### 1.1 Population — Total (`SP.POP.TOTL`)

```
GET https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL
    ?date=1900:2024
    &format=json
    &per_page=10000
```

**Response:** JSON array of `[pagination_meta, data_array]`.
Each data item: `{"indicator": {"id": "SP.POP.TOTL", "value": "Population, total"}, "country": {"id": "WLD", "value": "World"}, "countryiso3code": "", "date": "2023", "value": 8009000000.0, "unit": "", "obs_status": "", "decimal": 0}`

**Key country codes:**
- `"all"` — all countries
- `"WLD"` — world aggregate
- `"USA"` — United States
- `"CHN"` — China
- `"IND"` — India

### 1.2 GDP — Current USD (`NY.GDP.MKTP.CD`)

```
GET https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD
    ?date=1900:2024
    &format=json
    &per_page=10000
```

### 1.3 GNI Per Capita — Atlas Method (`NY.GNP.PCAP.CD`)

```
GET https://api.worldbank.org/v2/country/all/indicator/NY.GNP.PCAP.CD
    ?date=1900:2024
    &format=json
    &per_page=10000
```

### 1.4 Python Implementation

```python
import requests
import pandas as pd

def fetch_world_bank_indicator(
    indicator: str,
    country: str = "all",
    start_year: int = 1900,
    end_year: int = 2024,
) -> pd.DataFrame:
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
    params = {
        "date": f"{start_year}:{end_year}",
        "format": "json",
        "per_page": 10000,
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    meta, data = response.json()
    df = pd.DataFrame(data)
    df["date"] = pd.to_numeric(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values(["countryiso3code", "date"])
    return df
```

---

## 2. UN Population — WPP 2024

| Detail | Value |
|---|---|
| **Source** | UN Population Division, World Population Prospects 2024 |
| **Authentication** | None. Direct CSV download. |
| **Format** | CSV files. |
| **Portal** | `https://population.un.org/wpp/Download/Standard/` |

### 2.1 Available CSV Files

All files available at:
`https://population.un.org/wpp/Download/Files/1_Indicators%20(Standard)/CSV_FILES/`

| File | URL Slug |
|---|---|
| **Total Population** | `WPP2024_POP_F0_1_TOTAL_POPULATION_BOTH_SEXES.csv` |
| **Total Fertility Rate** | `WPP2024_POP_F0_2_TOTAL_FERTILITY_RATE_BOTH_SEXES.csv` |
| **Life Expectancy at Birth** | `WPP2024_POP_F0_3_LIFE_EXPECTANCY_AT_BIRTH_BOTH_SEXES.csv` |
| **Crude Birth Rate** | `WPP2024_POP_F0_4_CRUDE_BIRTH_RATE_BOTH_SEXES.csv` |
| **Crude Death Rate** | `WPP2024_POP_F0_5_CRUDE_DEATH_RATE_BOTH_SEXES.csv` |
| **Infant Mortality Rate** | `WPP2024_POP_F0_6_INFANT_MORTALITY_RATE_BOTH_SEXES.csv` |
| **Net Reproduction Rate** | `WPP2024_POP_F0_11_NET_REPRODUCTION_RATE_BOTH_SEXES.csv` |
| **Sex Ratio at Birth** | `WPP2024_POP_F0_7_SEX_RATIO_AT_BIRTH_BOTH_SEXES.csv` |

### 2.2 Python Implementation

```python
import pandas as pd

def fetch_un_population(variable: str, start_year: int = 1950, end_year: int = 2024) -> pd.DataFrame:
    base = "https://population.un.org/wpp/Download/Files/1_Indicators%20(Standard)/CSV_FILES/"
    files = {
        "population": "WPP2024_POP_F0_1_TOTAL_POPULATION_BOTH_SEXES.csv",
        "fertility": "WPP2024_POP_F0_2_TOTAL_FERTILITY_RATE_BOTH_SEXES.csv",
        "life_expectancy": "WPP2024_POP_F0_3_LIFE_EXPECTANCY_AT_BIRTH_BOTH_SEXES.csv",
        "birth_rate": "WPP2024_POP_F0_4_CRUDE_BIRTH_RATE_BOTH_SEXES.csv",
        "death_rate": "WPP2024_POP_F0_5_CRUDE_DEATH_RATE_BOTH_SEXES.csv",
    }
    url = base + files[variable]
    df = pd.read_csv(url)
    # Standard column names across all WPP files:
    # Index, Variant, Region, Subregion, Country, Country code,
    # 1950-1955, 1955-1960, ..., 2020-2025, 2025-2030, ...
    # Melt to long format
    df = df.melt(
        id_vars=["Region, subregion, country or area *", "Country code"],
        var_name="period",
        value_name="value",
    )
    # Parse mid-year from "YYYY-YYYY" format
    df["year"] = df["period"].str.split("-").str[0].astype(int)
    df = df.drop(columns=["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    return df
```

**Note:** WPP 2024 provides data in 5-year periods from 1950 onward, with projections to 2100.
For annual resolution, the data can be interpolated (see `data/transforms/interpolation.py`).

---

## 3. FAOSTAT — Food Supply, Arable Land, Crop Yield

| Detail | Value |
|---|---|
| **Base URL** | `https://fenixservices.fao.org/faostat/api/v1/data/{domain}` |
| **Authentication** | None for basic SDMX queries. Free account needed for developer portal access. |
| **Format** | SDMX or direct CSV download |
| **Developer Portal** | `https://data.apps.fao.org/` |

### 3.1 Available Domains

| Domain | Code | Contains |
|---|---|---|
| Food Balance Sheets | `fb` | Food supply (kcal/capita/day), production quantities |
| Production | `q` | Crop and livestock production by country |
| Land Use | `el` | Arable land, permanent crops, pasture area |
| Trade | `t` | Import/export quantities and values |
| Prices | `p` | Producer prices, food prices |

### 3.2 SDMX API Endpoint

```
GET https://fenixservices.fao.org/faostat/api/v1/data/{domainCode}/{domainCode}
    ?itemCode={item}
    &elementCode={element}
    &areaCode={area}
    &Years={year}
    &format=JSON
```

**Key item codes:**
- Food supply (kcal/capita/day): `itemCode=2003` (elementCode=12061)
- Arable land (hectares): `itemCode=4035` (elementCode=5111)
- Crop production index: `itemCode=436` (elementCode=5510)

### 3.3 Direct CSV Download

```
GET https://fenixservices.fao.org/faostat/api/v1/data/{domainCode}/bulk/
```

Download full domain as ZIP containing CSV.

### 3.4 Python Implementation

```python
import requests
import pandas as pd

def fetch_faostat(
    domain: str,
    item_code: int,
    element_code: int,
    start_year: int = 1961,
    end_year: int = 2024,
) -> pd.DataFrame:
    url = f"https://fenixservices.fao.org/faostat/api/v1/data/{domain}/{domain}"
    params = {
        "itemCode": item_code,
        "elementCode": element_code,
        "Years": f"{start_year}:{end_year}",
        "format": "JSON",
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    df["Year"] = pd.to_numeric(df.get("Year", df.get("Year")), errors="coerce")
    df["Value"] = pd.to_numeric(df.get("Value", df.get("Value")), errors="coerce")
    return df.dropna(subset=["Value"])
```

**Example — Food Supply (kcal):**
```python
df = fetch_faostat("fb", item_code=2003, element_code=12061, start_year=1961)
```

---

## 4. NOAA — Atmospheric CO₂ (Mauna Loa)

| Detail | Value |
|---|---|
| **Source** | NOAA Global Monitoring Laboratory, Mauna Loa Observatory |
| **Authentication** | None. Direct file download. |
| **Format** | Plain text, space-delimited. |
| **Coverage** | 1958–present (Keeling Curve). |

### 4.1 Data Files

| File | URL | Columns |
|---|---|---|
| Annual Mean | `https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt` | `year`, `mean`, `unc` |
| Monthly Mean | `https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt` | `year`, `month`, `decimal`, `average`, `interpolated`, `trend`, `days` |
| Daily Average | `https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_daily_mlo.txt` | `year`, `month`, `day`, `decimal`, `co2_ppm` |

### 4.2 Python Implementation

```python
import pandas as pd

def fetch_noaa_co2(freq: str = "annual") -> pd.DataFrame:
    urls = {
        "annual": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt",
        "monthly": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt",
    }
    url = urls[freq]
    if freq == "annual":
        df = pd.read_csv(
            url,
            comment="#",
            sep=r"\s+",
            names=["year", "co2_ppm", "uncertainty"],
        )
    else:
        df = pd.read_csv(
            url,
            comment="#",
            sep=r"\s+",
            names=["year", "month", "decimal", "monthly_mean", "interpolated", "trend", "n_days"],
        )
    return df
```

**Note:** Monthly data starts March 1958. Annual data starts 1959.
For pre-1958 values, use ice core proxy data from separate sources
(e.g., EPICA Dome C data via NOAA Paleoclimatology).

---

## 5. Our World in Data — Energy, CO₂, GDP

| Detail | Value |
|---|---|
| **Catalog Base** | `https://catalog.ourworldindata.org/` |
| **Search** | `https://search.owid.io/indicators` |
| **Authentication** | None. |
| **Python library** | `owid-catalog` (PyPI) |

### 5.1 Python Implementation

```python
from owid.catalog import search, fetch

# Search for an indicator
results = search("CO2 emissions", kind="table", namespace="gcp")
co2_data = results[0].fetch()  # Returns DataFrame

# Direct chart fetch
energy_data = fetch("primary-energy-consumption")

# Search charts
results = search("gdp per capita")
gdp_data = results[0].fetch()
```

### 5.2 Direct URL Access (no library)

```
GET https://nodeload.ourworldindata.org/
```

Individual chart data can be downloaded as CSV from:
```
https://nodeload.ourworldindata.org/grapher/{chart-slug}
```

### 5.3 Key Datasets for pyWorldX

| Topic | OWID Path / Search Term |
|---|---|
| Primary energy | `"primary-energy-consumption"` |
| Fossil CO₂ emissions | Search: `"CO2 emissions"`, namespace: `"gcp"` (Global Carbon Project) |
| CO₂ per capita | `"per-capita-co2-emissions"` |
| Cumulative CO₂ | `"cumulative-co2-emissions"` |
| GDP per capita (Maddison) | `"gdp-per-capita-maddison"` |
| Population | Search: `"population"`, namespace: `"un"` |
| Life expectancy | `"life-expectancy"` |

### 5.4 Manual CSV Download (fallback)

Each chart page on `https://ourworldindata.org/grapher/{slug}` has a "Download" button
with direct CSV link at `https://nodeload.ourworldindata.org/grapher/{slug}`.

---

## 6. USGS — Mineral Commodity Summaries

| Detail | Value |
|---|---|
| **Source** | USGS Mineral Resources Program |
| **Authentication** | None. Direct file download. |
| **Format** | CSV and JSON data releases. |
| **Coverage** | 88+ nonfuel mineral commodities, 1900–present. |

### 6.1 Data Release URLs

| Resource | URL |
|---|---|
| MCS 2024 Data Release | `https://www.usgs.gov/data/us-geological-survey-mineral-commodity-summaries-2024-data-release-ver-20-march-2024` |
| Historical MCS Archive | `https://pubs.usgs.gov/periodicals/mcs/` |
| National Minerals Information Center | `https://www.usgs.gov/centers/national-minerals-information-center` |

### 6.2 Data Release Structure

The data release provides:
- `mcs2024.csv` — All commodity summaries for 2024
- Historical series available at: `https://www.usgs.gov/centers/nmic/mineral-commodity-summaries-publications`

Each commodity has:
- World mine production (tonnes)
- US production (tonnes)
- World reserves (tonnes)
- US reserves (tonnes)
- Apparent consumption (tonnes)
- Recycling rates

### 6.3 Python Implementation

```python
import pandas as pd

def fetch_usgs_mineral(year: int = 2024) -> pd.DataFrame:
    """Download USGS Mineral Commodity Summaries for given year."""
    # The exact URL format changes annually; check the NMIC page for current year
    url = f"https://pubs.usgs.gov/periodicals/mcs2024/mcs2024.pdf"
    # For CSV access, use the data release:
    csv_url = "https://pubs.usgs.gov/data/mcs-2024/mcs2024.csv"
    df = pd.read_csv(csv_url)
    return df
```

**Note:** USGS publishes annual Mineral Commodity Summaries each January.
The CSV/JSON data release URLs change annually. Check
`https://www.usgs.gov/centers/nmic/mineral-commodity-summaries-publications`
for the latest data release link.

---

## 7. UNIDO — Industrial Statistics (INDSTAT)

| Detail | Value |
|---|---|
| **Source** | UNIDO Statistics Portal |
| **Authentication** | None. Direct CSV download. |
| **Format** | CSV. |
| **Coverage** | 1990–2022, ISIC Rev 4. |

### 7.1 Data Download Portal

| Resource | URL |
|---|---|
| Data Download Page | `https://stat.unido.org/data/download` |
| INDSTAT 4 (current) | `https://stat.unido.org/portal/data/release/1` |
| Quarterly IIP | `https://stat.unido.org/` |

### 7.2 Available Datasets

| Dataset | Description | Period |
|---|---|---|
| INDSTAT 4 | Industrial statistics, ISIC Rev 4 | 1990–2022 |
| IDSB 4 | Industrial demand-supply balances, ISIC Rev 4 | 1990–2022 |
| National Accounts | Manufacturing value added, GDP shares | 1970–2022 |

### 7.3 Python Implementation

```python
import pandas as pd

def fetch_unido_indstat() -> pd.DataFrame:
    """Download UNIDO INDSTAT 4 data.

    The CSV file must be manually downloaded from the portal first,
    as UNIDO does not provide a programmatic API endpoint.
    """
    # After downloading from https://stat.unido.org/data/download
    df = pd.read_csv("data/raw/unido_indstat4.csv")
    return df
```

**Note:** UNIDO does not offer a REST API. Data must be downloaded as CSV
from the portal. The file is large (~50MB). Once downloaded, it can be
cached locally and loaded via `pandas.read_csv()`.

---

## 8. UNDP — Human Development Index (HDR)

| Detail | Value |
|---|---|
| **Source** | UNDP Human Development Report Office |
| **Authentication** | None. Direct CSV download. |
| **Format** | CSV. |
| **Coverage** | 1990–2023. |

### 8.1 Data Download Portal

| Resource | URL |
|---|---|
| Data Portal | `https://data.undp.org/access-all-data/` |
| HDR 2023/2024 | `https://hdr.undp.org/data-center/documentation-and-downloads` |
| Technical Notes | `https://hdr.undp.org/sites/default/files/2023-24_HDR/hdr2023-24_technical_notes.pdf` |

### 8.2 Available Indicators

| Indicator | Description |
|---|---|
| HDI | Human Development Index (0–1 scale) |
| Life Expectancy Index | Component of HDI (0–1) |
| Education Index | Component of HDI (0–1) |
| GNI Index | Component of HDI (0–1) |
| IHDI | Inequality-adjusted HDI |
| GDI | Gender Development Index |
| MPI | Multidimensional Poverty Index |

### 8.3 Python Implementation

```python
import pandas as pd

def fetch_undp_hdi() -> pd.DataFrame:
    """Download UNDP Human Development Index data.

    The CSV file must be manually downloaded from the portal first.
    """
    # After downloading from https://data.undp.org/access-all-data/
    df = pd.read_csv("data/raw/undp_hdr.csv")
    return df
```

**Note:** UNDP shut down their previous REST API. Data is now available
only via direct CSV download from the Data Futures portal.
The file covers 193 countries, 1990–2023.

---

## 9. FRED — GDP Deflator, CPI (Optional Macro Connector)

| Detail | Value |
|---|---|
| **Base URL** | `https://api.stlouisfed.org/fred/` |
| **Authentication** | Free API key. Register at `https://fred.stlouisfed.org/docs/api/api_key.html` |
| **Format** | JSON, XML, CSV, XLSX. |
| **Coverage** | 816,000+ time series, 1776–present. |
| **Python library** | `fredapi` (PyPI) or `requests` |

### 9.1 API Endpoint

```
GET https://api.stlouisfed.org/fred/series/observations
    ?series_id={series_id}
    &api_key={your_api_key}
    &file_type=json
    &sort_order=asc
    &limit=100000
```

### 9.2 Key Series IDs for pyWorldX

| Series ID | Description |
|---|---|
| `GDPDEF` | GDP Deflator (base year varies) |
| `CPIAUCSL` | Consumer Price Index, All Urban |
| `FEDFUNDS` | Federal Funds Rate |
| `GDP` | Gross Domestic Product (current USD, quarterly) |
| `GDPC1` | Real Gross Domestic Product (chained 2017 USD) |
| `MICH` | University of Michigan Inflation Expectations |

### 9.3 Python Implementation (with `fredapi`)

```python
from fredapi import Fred
import pandas as pd

fred = Fred(api_key="your_api_key_here")

# GDP Deflator
gdpdef = fred.get_series("GDPDEF")

# CPI
cpi = fred.get_series("CPIAUCSL")

# Federal Funds Rate
ffr = fred.get_series("FEDFUNDS")
```

### 9.4 Python Implementation (raw requests)

```python
import requests
import pandas as pd

def fetch_fred(series_id: str, api_key: str) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
        "limit": 100000,
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data["observations"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[df["value"].notna()]
    return df
```

---

## Summary Table

| Connector | Access Method | Auth Required | Annual Data From | Key Variable |
|---|---|---|---|---|
| **World Bank** | REST JSON | None | ~1960 | `SP.POP.TOTL`, `NY.GDP.MKTP.CD` |
| **UN Population** | Direct CSV | None | 1950 | Total population, fertility, life expectancy |
| **FAOSTAT** | SDMX API / CSV | None (free acct for portal) | 1961 | Food supply (kcal), arable land |
| **NOAA CO₂** | Direct TXT | None | 1958 | Atmospheric CO₂ (ppm) |
| **OWID** | REST JSON / catalog | None | ~1800 (Maddison GDP) | Energy, CO₂, GDP |
| **USGS** | Direct CSV | None | ~1900 | Mineral production & reserves |
| **UNIDO** | Direct CSV | None | 1990 | Manufacturing value added |
| **UNDP HDR** | Direct CSV | None | 1990 | HDI, life expectancy, education |
| **FRED** (optional) | REST JSON | Free API key | 1929+ | GDP deflator, CPI |

---

## Data Coverage Gaps for World3-03

The spec requires data from **1900–2020** for calibration. Here's the actual coverage:

| Variable | Required Period | Data Available From | Gap |
|---|---|---|---|
| Population | 1900–2020 | 1950 (UN WPP) / ~1960 (World Bank) | **50–60 years missing** — use Maddison/OWID historical estimates |
| Industrial Output / GDP | 1900–2020 | ~1820 (Maddison via OWID) | ✅ Covered |
| Food Production | 1900–2020 | 1961 (FAOSTAT) | **~60 years missing** — use FAO historical archives |
| CO₂ / Pollution | 1900–2020 | 1751 (GCP via OWID), 1958 (NOAA Mauna Loa) | ✅ Covered |
| Nonrenewable Resources | 1900–2020 | ~1900 (USGS archives) | ✅ Covered but sparse |
| Industrial Production | 1900–2020 | 1990 (UNIDO) | **~70 years missing** — use Maddison industrial output estimates |
| HDI | 1900–2020 | 1990 (UNDP) | **~90 years missing** — proxy with life expectancy + literacy |

**Key insight:** The 1900–1950 period relies on historical reconstructions (Maddison Project,
historical UN demographic estimates, USGS mineral archives). The World3-03 original model
was calibrated on reconstructed historical series, not modern API data. The calibration
workflow should use OWID's Maddison data for the early period (1900–1950) and World Bank /
UN data for the modern period (1950–2020).

---

## Additional Free Data Sources — Calibration Multipliers

These sources are **not** in the spec's mandatory 8 connectors but would dramatically
improve calibration quality by filling historical gaps, adding validation anchors,
and providing cross-source redundancy.

---

### A. Maddison Project Database — Historical GDP & Population (1820–2008)

| Detail | Value |
|---|---|
| **What** | Reconstructed GDP per capita and population for 169 countries, some back to year 1 CE |
| **Why it matters** | Fills the **1900–1950 gap** for industrial output and population that World Bank/UN can't cover |
| **Source** | `https://www.rug.nl/ggdc/historicaldevelopment/maddison/` |
| **Download** | `https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023` |
| **Auth** | None. Direct Excel/CSV download |
| **Format** | Excel (.xlsx) |
| **Python library** | `pandas.read_excel()` or `maddison` (R package, no Python equivalent) |
| **Access via OWID** | `https://ourworldindata.org/grapher/gdp-per-capita-maddison-project-database` |

**Key variables:**
- GDP per capita (1990 international Geary-Khamis dollars)
- Population (thousands)
- Total GDP (derived)

**Python implementation via OWID:**
```python
from owid.catalog import search, fetch
results = search("gdp per capita maddison")
gdp = results[0].fetch()  # 1820–2023, 169 countries
```

**Python implementation via direct download:**
```python
import pandas as pd
# Download the Maddison 2023 Excel file from rug.nl
df = pd.read_excel("mpd2023.xlsx")
df = df[["country", "year", "pop", "cgdppc"]]  # population, GDP per capita
```

---

### B. Penn World Table — Productivity, Capital, Labor (1950–2023)

| Detail | Value |
|---|---|
| **What** | 47 variables for 185 countries: capital stock, labor, TFP, consumption, government spending |
| **Why it matters** | Provides **capital stock** data (PWT's `cn` variable) — the single most important missing empirical anchor for World3-03's industrial capital sector |
| **Source** | `https://www.rug.nl/ggdc/productivity/pwt/` |
| **Download** | `https://www.rug.nl/ggdc/productivity/pwt/pwt-11.0` |
| **Auth** | None. Direct Excel download |
| **Format** | Excel (.xlsx) |
| **Key variables** | `cn` (capital stock), `rgdpe` (expenditure-side real GDP), `emp` (employment), `hc` (human capital), `tfpna` (TFP) |

**Python implementation:**
```python
import pandas as pd
df = pd.read_excel("pwt110.xlsx")
# Capital stock at constant national prices
capital = df[["countrycode", "country", "year", "cn"]]
# Real GDP expenditure-side
gdp = df[["countrycode", "country", "year", "rgdpe"]]
```

**Available via FRED** (no separate download needed):
- PWT data is now mirrored in FRED as series `PWT*` — access via the FRED connector

---

### C. EIA — US Energy Information Administration (1900–2024)

| Detail | Value |
|---|---|
| **What** | Comprehensive US energy data: production, consumption, imports, exports by fuel type |
| **Why it matters** | Highest-quality historical energy data available for the US (largest historical energy consumer). Fills the fossil fuel consumption gap for pollution calibration |
| **Base URL** | `https://api.eia.gov/v2/` |
| **Auth** | **Free API key**. Register at `https://www.eia.gov/opendata/register.php` |
| **Format** | JSON, XML, CSV |
| **Python library** | `eia` (PyPI) or `requests` |

**Key series for pyWorldX:**
- Total energy consumption by source (coal, petroleum, natural gas, nuclear, renewables)
- CO₂ emissions by sector
- Petroleum consumption (1900–present)
- Coal consumption (1900–present)

**Python implementation:**
```python
import requests

API_KEY = "your_free_key"
# Total energy consumption
url = f"https://api.eia.gov/v2/total-energy/data/"
params = {
    "api_key": API_KEY,
    "frequency": "annual",
    "data": ["value"],
    "facets": {"sourceTypeId": ["Fossil Fuel", "Renewable", "Nuclear"]},
    "start": "1900",
    "end": "2024",
}
response = requests.get(url, params=params)
data = response.json()["response"]["data"]
```

---

### D. EDGAR — Emissions Database for Global Atmospheric Research (1970–2024)

| Detail | Value |
|---|---|
| **What** | Global greenhouse gas and air pollutant emissions by country and sector |
| **Why it matters** | More granular than NOAA Mauna Loa — provides **country-level** CO₂, CH₄, N₂O, SO₂, NOₓ, PM2.5 from 1970. Covers anthropogenic sources by economic sector |
| **Source** | `https://edgar.jrc.ec.europa.eu/` |
| **Download** | Direct CSV/NetCDF from the EDGAR portal |
| **Auth** | None |
| **Format** | CSV, NetCDF |
| **Coverage** | 1970–2024, all countries, 30+ pollutants |

**Python implementation:**
```python
import pandas as pd
# Download CO2 emissions by country
url = "https://edgar.jrc.ec.europa.eu/dataset_ghg2024/data/CO2_excl_short-cycle_C"
# Download the CSV from the portal
df = pd.read_csv("edgar_co2.csv")
```

---

### E. HYDE — History Database of the Global Environment (10,000 BC–2020)

| Detail | Value |
|---|---|
| **What** | Spatially explicit database of population and land use over the past 12,000 years |
| **Why it matters** | Fills the **pre-1900 population and arable land gap**. HYDE 3.3 provides gridded population and cropland/pasture data back to 10,000 BC. For pyWorldX, the 1800–1950 period is critical |
| **Source** | `https://hyde.pbl.nl/` |
| **Download** | `https://www.kaggle.com/datasets/ilyenkov/hyde-3-3` or `https://dataverse.nl/dataset.xhtml?persistentId=doi:10.17026/dans-xbp-6klp` |
| **Auth** | None |
| **Format** | NetCDF, CSV, R data files |
| **Key variables** | Population (gridded), cropland area, pasture area, built-up area |

**Python implementation:**
```python
import pandas as pd
# HYDE 3.3 on Kaggle (CSV format)
df = pd.read_csv("hyde33_population.csv")
# Filter to 1800-1950 for World3 pre-period
hist_pop = df[(df["year"] >= 1800) & (df["year"] <= 1950)]
```

---

### F. IMF World Economic Outlook — Macroeconomic Data (1980–2029)

| Detail | Value |
|---|---|
| **What** | GDP, inflation, unemployment, debt, trade for 190+ countries |
| **Why it matters** | Cross-validation anchor for World Bank GDP data. Provides forward-looking projections to 2029 |
| **Auth** | None (SDMX protocol) |
| **Format** | SDMX (XML/JSON), CSV |
| **Python library** | `sdmx1` (PyPI), `weo` (PyPI), or `pandasdmx` |

**Python implementation:**
```python
import sdmx

# IMF SDMX API (no key required)
imf = sdmx.Client("IMF")
# WEO database
key = dict(CL_AREA="W", CL_FREQ="A")
data = imf.data("WEO", key=key, params={"startPeriod": "1980", "endPeriod": "2024"})
```

**Or with `weo` package:**
```python
import weo
df = weo.download(release="Oct2024")  # Full WEO dataset
```

---

### G. OECD Data — Economic Indicators (1960–2024)

| Detail | Value |
|---|---|
| **What** | 30,000+ indicators for 38 OECD countries + key partners: GDP, trade, employment, environment |
| **Why it matters** | High-quality data for developed nations. Provides environmental indicators (CO₂ emissions, energy use, waste) that cross-validate World Bank data |
| **Base URL** | `https://data.oecd.org/api/sdmx.ashx/GetData/` |
| **Auth** | None. No API key required |
| **Format** | SDMX, CSV, JSON |
| **Python library** | `sdmx1` (PyPI), `pandasdmx` |

**Python implementation:**
```python
import pandas as pd
# Direct CSV download from OECD API
url = "https://data.oecd.org/api/sdmx.ashx/GetData/CO2_EMISSIONS?startTime=1960"
df = pd.read_csv(url)

# Or via SDMX
import sdmx
oecd = sdmx.Client("OECD")
data = oecd.data("CO2_EMISSIONS", startPeriod="1960")
```

---

### H. Gapminder — Systema Globalis (1800–2024)

| Detail | Value |
|---|---|
| **What** | 500+ indicators for 200+ countries, compiled from UN, World Bank, historical sources |
| **Why it matters** | Aggregates and harmonizes the best historical data sources. Provides 1800–1950 data that fills gaps before modern surveys |
| **Source** | `https://www.gapminder.org/data/` |
| **Download** | `https://www.gapminder.org/data/` (individual CSV per indicator) |
| **Auth** | None |
| **Format** | CSV |
| **Key variables** | Population, income, life expectancy, children per woman, CO₂ emissions, energy use |

**Python implementation:**
```python
import pandas as pd
# Each indicator is a separate CSV at gapminder.org
url = "https://www.gapminder.org/api/v1/indicators/{indicator_id}/data.csv"
df = pd.read_csv(url.format(indicator_id="life_expectancy_years"))
```

---

### I. NASA GISS — Global Surface Temperature (1880–present)

| Detail | Value |
|---|---|
| **What** | Global mean surface temperature anomalies, monthly and annual |
| **Why it matters** | Independent pollution-climate validation anchor. World3-03's pollution sector should correlate with observed temperature trends |
| **Source** | `https://data.giss.nasa.gov/gistemp/` |
| **Download** | Direct text/CSV files |
| **Auth** | None |
| **Format** | Plain text, CSV |

**Python implementation:**
```python
import pandas as pd
# Global annual mean temperature anomalies
url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.txt"
df = pd.read_csv(url, comment="%", sep=r"\s+",
                  names=["year", "jan", "feb", "mar", "apr", "may", "jun",
                         "jul", "aug", "sep", "oct", "nov", "dec", "annual", "unc"])
```

---

### J. Berkeley Earth — Surface Temperature (1750–present)

| Detail | Value |
|---|---|
| **What** | 1.6 billion temperature reports from 16 archives, merged into a single global analysis |
| **Why it matters** | Longer record than NASA GISS (back to 1750). Independent cross-validation |
| **Source** | `http://berkeleyearth.org/data/` |
| **Download** | Direct text/CSV files |
| **Auth** | None |

**Python implementation:**
```python
import pandas as pd
# Global land-ocean temperature anomaly
url = "http://berkeleyearth.lbl.gov/auto/Global/Global_complete.txt"
df = pd.read_csv(url, comment="%", sep=r"\s+",
                  names=["year", "month", "anomaly", "uncertainty"])
```

---

### K. Global Footprint Network — NFA 2025 Ecological Footprint (1961–present)

| Detail | Value |
|---|---|
| **What** | National Footprint and Biocapacity Accounts: ecological footprint and biocapacity for 200+ countries with 6 sub-components (cropland, grazing, forest, fishing, built-up, carbon) |
| **Why it matters** | **Spec §13.1 requires NRMSD ≤ 0.343 for ecological footprint.** The sub-components directly map to `pollution.persistent_load` and `resources.nonrenewable_stock` ontology entities for disaggregated calibration. Direct measurement of the "overshoot" concept that World3-03 models. |
| **Source** | `https://footprint.info.yorku.ca/data/` or `https://data.footprintnetwork.org` |
| **Auth** | Free registration. |
| **Format** | CSV (primary), Excel (.xlsx) |
| **Coverage** | 1961–present, 200+ countries |

**Python implementation (ConnectorResult-compatible):**
```python
import pandas as pd
from datetime import datetime, timezone
from pyworldx.data.connectors.base import ConnectorResult
from pyworldx.data.connectors.footprint_network import FootprintNetworkConnector

def fetch_footprint_network(
    variable: str = "EFConsPerCap",
    country: str = "WLD",
    start_year: int = 1961,
) -> ConnectorResult:
    """Download NFA 2025 Public Data Package and return ConnectorResult.

    Args:
        variable: one of EFConsPerCap, BiocapPerCap, or component names
        country: country code or 'WLD' for world aggregate
        start_year: first year to include

    Returns:
        ConnectorResult with proxy_method populated (spec §8.1 requirement)
    """
    # After free registration, download the CSV:
    df = pd.read_csv("NFA_2025_Public_Data_Package.csv")

    # Filter to requested variable and country
    mask = (df["record"] == variable) & (df["country"] == country)
    subset = df.loc[mask, ["year", "value"]].copy()
    subset.columns = ["date", variable]
    subset["date"] = subset["date"].astype(int)
    subset = subset[subset["date"] >= start_year]
    series = subset.set_index("date")[variable].sort_index()

    return ConnectorResult(
        series=series,
        unit="global_hectares_per_capita",
        source="Global Footprint Network",
        source_series_id=f"NFA_2025_{variable}_{country}",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        vintage="2025",
        proxy_method=(
            "Ecological footprint accounting: combines consumption-based "
            "carbon, cropland, grazing, forest, fishing, and built-up land "
            "demand, converted to global hectares (gha) using equivalence "
            "factors and yield factors per country/year."
        ),
        transform_log=["filtered_by_variable", "filtered_by_country", "year_filter"],
    )
```

**Key variables in the NFA 2025 dataset:**
- `EFConsPerCap` — Ecological footprint (consumption-based), gha/capita
- `BiocapPerCap` — Biocapacity, gha/capita
- `EFConsTot` — Total ecological footprint, global hectares (gha)
- `EFConsCarbon` — Carbon footprint component, gha
- `EFConsCropland`, `EFConsGrazing`, `EFConsForest`, `EFConsFishing`, `EFConsBuiltUp` — sub-components

**Spec mapping (§8.1 requirement):** The `proxy_method` field above is mandatory
per the spec: ecological footprint is a derived proxy, not a direct measurement.

---

### L. Global Carbon Budget (GCP) — Fossil CO₂ Emissions (1750–2023)

| Detail | Value |
|---|---|
| **What** | Annual national and global fossil CO₂ emissions (CO₂ only, excluding land-use change) |
| **Why it matters** | **Fills the single biggest calibration gap: 1750–1970.** EDGAR only goes to 1970. GCP covers the full industrial era from the first steam engines to today. No auth required. |
| **Source** | `https://globalcarbonbudget.org/the-latest-gcb-data/` |
| **Auth** | None. Direct XLSX download. |
| **Format** | XLSX (multiple sheets), NetCDF for spatial data |
| **Coverage** | 1750–2023, 200+ countries, territorial and consumption-based accounting |
| **Citation** | Friedlingstein et al. 2024, *Earth System Science Data* |

**Python implementation:**
```python
import pandas as pd

def fetch_gcp_national_emissions() -> pd.DataFrame:
    """Download GCP 2024 national fossil CO2 emissions (1750–2023)."""
    url = (
        "https://globalcarbonbudget.org/wp-content/uploads/"
        "National_Fossil_Carbon_Emissions_2024v1.0.xlsx"
    )
    # Territorial emissions: production-based accounting
    df = pd.read_excel(url, sheet_name="Territorial Emissions")
    # Columns: Country, ISO3, 1750, 1751, ..., 2023
    # Melt to long format
    df = df.melt(
        id_vars=["Country", "ISO3"],
        var_name="year",
        value_name="co2_mt",  # million tonnes CO2
    )
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["co2_mt"] = pd.to_numeric(df["co2_mt"], errors="coerce")
    return df.dropna(subset=["co2_mt"])
```

**Key sheets in the workbook:**
- `Territorial Emissions` — production-based national totals
- `Consumption Emissions` — consumption-based (trade-adjusted)
- `Global Budget` — global totals with uncertainty ranges
- `Per Capita` — per-capita emissions by country

---

### M. PRIMAP-hist — National GHG Emissions (1750–2023)

| Detail | Value |
|---|---|
| **What** | Country-resolved CO₂, CH₄, N₂O, and F-gases back to 1750, combining EDGAR, UNFCCC, CDIAC, and other inventories |
| **Why it matters** | **Multi-gas, multi-sector, pre-1970.** Fills the gap where EDGAR has no data. Covers all Kyoto gases by IPCC sector (energy, industry, agriculture, waste, LULUCF). |
| **Source** | `https://zenodo.org/record/10705513` |
| **Auth** | None. Direct CSV download from Zenodo. |
| **Format** | CSV (long format), NetCDF |
| **Coverage** | 1750–2022, 200+ countries, 42 IPCC categories |

**Python implementation:**
```python
import pandas as pd

def fetch_primap_hist() -> pd.DataFrame:
    """Download PRIMAP-hist national GHG emissions (1750–2022)."""
    # Zenodo record 10705513 — PRIMAP-hist v2.5.1 final release
    url = (
        "https://zenodo.org/record/10705513/files/"
        "PRIMAP-hist_v2.5.1_final_no_rounding_1750-2022.csv"
    )
    df = pd.read_csv(url)
    # Standard PRIMAP columns:
    # country, year, gas, category, emissions_kt_CO2eq
    return df
```

**Key use for pyWorldX:** Use PRIMAP-hist CO₂ for the pre-1970 calibration period,
then switch to EDGAR v8 for post-1970 with sector-level detail. The overlap period
(1970–2023) provides cross-validation.

---

### N. CEDS — Community Emissions Data System (1750–2019)

| Detail | Value |
|---|---|
| **What** | Global anthropogenic emissions of SO₂, NOₓ, CO, BC (black carbon), OC (organic carbon), NH₃, and NMVOC by country and sector |
| **Why it matters** | **The only source with 1750–2019 reactive gas and aerosol emissions.** SO₂ and aerosols are critical for World3's persistent pollution index — they drive atmospheric residence time, acid rain, and health impacts that affect mortality. CO₂ alone is insufficient. |
| **Source** | `https://github.com/JGCRI/CEDS` |
| **Download** | `https://doi.org/10.5281/zenodo.7346806` (Zenodo) |
| **Auth** | None. Open-source on GitHub + Zenodo. |
| **Format** | CSV, NetCDF |
| **Coverage** | 1750–2019, all countries, 7 pollutants × 12 sectors |

**Python implementation:**
```python
import pandas as pd

def fetch_ceds(pollutant: str = "SO2") -> pd.DataFrame:
    """Download CEDS emissions for a specific pollutant from Zenodo.

    Each pollutant is a separate CSV file on Zenodo at
    DOI 10.5281/zenodo.7346806. The CEDS GitHub repo
    (github.com/JGCRI/CEDS) has code but NOT the data files.
    """
    # Zenodo direct download — each pollutant is a separate file
    # Replace pollutant code as needed: SO2, NOx, BC, OC, CO, NH3, NMVOC
    url = (
        f"https://zenodo.org/record/7346806/files/"
        f"CEDS_v_2021_04_21_{pollutant}.csv"
    )
    df = pd.read_csv(url)
    # Columns: country, iso3, year, sector, emissions_kt
    return df
```

**Key pollutants for pyWorldX:**
- **SO₂** — Acid rain, aerosol formation, stratospheric residence time
- **NOₓ** — Ozone formation, nitrogen deposition, ecosystem stress
- **BC (black carbon)** — Direct warming agent, health impact proxy
- **CO** — Incomplete combustion indicator, atmospheric chemistry

---

### O. Energy Institute — Statistical Review of World Energy (1965–2024)

| Detail | Value |
|---|---|
| **What** | Primary energy consumption by fuel type (oil, coal, gas, nuclear, hydro, renewables) for all major countries |
| **Why it matters** | **The single most comprehensive energy dataset available.** Formerly the BP Statistical Review (published annually since 1965). One Excel file with all fuels, all countries, all years. Superior granularity for fossil fuel calibration vs. OWID's chart-based approach. |
| **Source** | `https://www.energyinst.org/statistical-review` |
| **Auth** | None. Direct download. |
| **Format** | Excel (.xlsx) |
| **Coverage** | 1965–2024, 65+ countries, 8 fuel types |

**Python implementation:**
```python
import pandas as pd

def fetch_ei_stat_review() -> dict[str, pd.DataFrame]:
    """Download Energy Institute Statistical Review workbook."""
    # Download the "Statistical Review of World Energy Data" workbook from
    # https://www.energyinst.org/statistical-review/resources-and-data/downloads
    workbook = "Statistical Review of World Energy Data.xlsx"
    sheets = pd.read_excel(workbook, sheet_name=None)
    # Available sheets:
    # 'Primary Energy', 'Oil', 'Natural Gas', 'Coal', 'Nuclear',
    # 'Hydropower', 'Renewables', 'Capacity', 'Prices'
    return sheets
```

**Key sheets for pyWorldX:**
- `Primary Energy` — Total consumption by fuel type (exajoules)
- `Oil` — Production, consumption, reserves by country
- `Coal` — Production, consumption, reserves by country
- `Natural Gas` — Production, consumption, trade, reserves

---

### P. IHME Global Burden of Disease (GBD) — Mortality & Morbidity (1990–2021)

| Detail | Value |
|---|---|
| **What** | Age-specific mortality, cause-of-death, and DALYs (disability-adjusted life years) for 204 countries |
| **Why it matters** | **Superior mortality calibration anchor vs. UNDP HDI alone.** Provides cause-of-death decomposition (cardiovascular, respiratory, infectious, injury) that directly validates World3's life expectancy table functions. |
| **Source** | `https://www.healthdata.org/research-analysis/gbd` |
| **Download** | `https://vizhub.healthdata.org/gbd-results/` (interactive download) |
| **Auth** | Free registration required. |
| **Format** | CSV, interactive data explorer |
| **Coverage** | 1990–2021, 204 countries, 370+ diseases/injuries |

**Python implementation:**
```python
import pandas as pd

def fetch_ihme_gbd_causes() -> pd.DataFrame:
    """Load IHME GBD cause-of-death data (manual download required)."""
    # Download from https://vizhub.healthdata.org/gbd-results/
    # Select: Measure = "Deaths", Location = "Global" or specific countries
    # Metric = "Number" or "Rate", Cause = "All causes"
    df = pd.read_csv("gbd_cause_of_death.csv")
    # Key columns: location, year, age, sex, cause, deaths, death_rate
    return df
```

**Key use for pyWorldX:** Calibrate the `LMPP` (pollution mortality), `LMFT` (food mortality),
and `LMHS` (health services mortality) table functions in the Population sector against
observed cause-specific mortality rates.

---

### Q. Human Mortality Database (HMD) — Age-Specific Death Rates (1750–present)

| Detail | Value |
|---|---|
| **What** | High-quality life tables with age- and sex-specific mortality rates for 40+ countries |
| **Why it matters** | **The gold standard for historical mortality data.** Goes back to 1751 for Sweden, 1800s for most European countries. Essential for calibrating cohort-based mortality dynamics — not just aggregate death rates. |
| **Source** | `https://www.mortality.org` |
| **Auth** | Free registration (takes 1–2 days for approval). |
| **Format** | Text files (standardized format) |
| **Coverage** | 1751–present (varies by country), 40+ countries |

**Python implementation:**
```python
import pandas as pd

def fetch_hmd_mortality(country_code: str = "USA") -> pd.DataFrame:
    """Load HMD life table data for a specific country."""
    # After downloading from mortality.org:
    # Files: 1x1 (single-year age groups), 5x1 (five-year age groups)
    df = pd.read_csv(
        f"HMD_{country_code}/FLTper_1x1.txt",
        comment="#",
        sep=r"\s+",
    )
    # Columns: Year, Age, mx (mortality rate), qx (death probability),
    #          lx (survivors), dx (deaths), ex (life expectancy)
    return df
```

**Key use for pyWorldX:** The `mx` (mortality rate by age) columns directly validate
the crude death rate calculations in the Population sector. Historical HMD data
(1750–1950) fills the pre-UN mortality gap.

---

### R. Climate TRACE — Asset-Level Emissions (2015–2025)

| Detail | Value |
|---|---|
| **What** | 744 million individual emitting assets across 67 sub-sectors with monthly granularity |
| **Why it matters** | Modern high-resolution validation anchor for the pollution sector. Not for calibration (too short a record) — but useful for verifying that modelled sector-level emissions match observed facility-level data. |
| **Source** | `https://climatetrace.org` |
| **Auth** | None. Open data download. |
| **Format** | GeoJSON, CSV |
| **Coverage** | 2015–2025, global, 67 sub-sectors |

---

### S. NASA Earthdata — Satellite-Derived Emissions (2014–present)

| Detail | Value |
|---|---|
| **What** | Satellite-derived emission estimates from OCO-2 (CO₂), TROPOMI (NO₂, CH₄, SO₂), and other instruments |
| **Why it matters** | Independent top-down validation of ground-based pollution data. Useful for cross-validating the pollution sector against space-based observations. |
| **Source** | `https://www.earthdata.nasa.gov/topics/human-dimensions/industrial-emissions` |
| **Auth** | Free Earthdata Login (instant, no-cost). |
| **Format** | NetCDF, HDF, GeoTIFF |
| **Coverage** | 2014–present, global |

---

### T. Climate Watch / WRI — Sector GHG Emissions (1990–present)

| Detail | Value |
|---|---|
| **What** | UNFCCC-submitted national GHG inventories with sector breakdowns (energy, industry, agriculture, waste, LULUCF) |
| **Why it matters** | Official national reporting data. Cross-validates EDGAR/PRIMAP for the modern period. Free API and CSV download. |
| **Source** | `https://www.climatewatchdata.org/ghg-emissions` |
| **Auth** | None. |
| **Format** | CSV, API |
| **Coverage** | 1990–present, all Annex I countries |

---

### U. Global Carbon Atlas — Land-Use CO₂ Fluxes (1959–present)

| Detail | Value |
|---|---|
| **What** | Land-use change CO₂ fluxes derived from Dynamic Global Vegetation Models (DGVMs) |
| **Why it matters** | Complements FAOSTAT arable land data with a carbon-flux perspective. Useful for calibrating World3's land-fertility-erosion feedback loop. |
| **Source** | `https://globalcarbonatlas.org` |
| **Auth** | None. |
| **Format** | NetCDF, GeoTIFF |
| **Coverage** | 1959–present, global grid |

---

---

## Spec-Critical Sources — Mapped to Calibration Targets

These sources are explicitly required by the spec's Section 13.1 NRMSD bounds
and Section 8 data pipeline requirements. Without them, the release gate
checklist cannot be completed.

### Nebel et al. (2023) Proxy Series — **HIGHEST PRIORITY**

| Detail | Value |
|---|---|
| **What** | The exact GDP-deflated industrial output, food, service, and pollution proxy CSVs used in Nebel et al. (2023) to derive the Section 13.1 NRMSD bounds |
| **Why it matters** | **Without this, NRMSD validation is non-reproducible.** The spec requires `validate_end=2023` with total NRMSD ≤ 0.2719. You cannot compute NRMSD without the exact reference series that the bounds were calculated from. |
| **Source** | `https://doi.org/10.1371/journal.pone.0275865` |
| **Auth** | None. Open access PLOS ONE article with data supplement. |
| **Format** | CSV files in supplementary materials |
| **Contains** | World industrial output (GDP-deflated), world food production, world services, world pollution proxy series — all aligned to the World3-03 variable ontology |

**Python implementation:**
```python
import pandas as pd

# Download supplementary data from the PLOS ONE article at:
# https://doi.org/10.1371/journal.pone.0275865
# Go to the "Supporting Information" section and download the CSV files.
# File names will follow the pattern S1_File.csv, S2_File.csv, etc.
# Verify exact names on the article page before running.

# TODO: Verify exact supplementary file names from the article
# The example below uses placeholder names — replace with actual names.
industrial_output = pd.read_csv("S1_Industrial_Output.csv")
food_production = pd.read_csv("S2_Food_Production.csv")
services = pd.read_csv("S3_Service_Output.csv")
pollution_proxy = pd.read_csv("S4_Pollution_Proxy.csv")

# If the supplement files don't match World3-03 variable names directly,
# a mapping step will be needed. Check column headers against:
# - industrial_output (GDP-deflated, constant prices)
# - food_production (caloric or mass equivalent)
# - service_output (GDP-deflated)
# - pollution_proxy (persistent pollution index or equivalent)
```

**⚠️ Action needed:** Visit `https://doi.org/10.1371/journal.pone.0275865` and check
the "Supporting Information" section to confirm the exact file names and column
headers. If the variables don't map 1:1 to World3-03 ontology names, a bridging
step will be needed in `data/transforms/` to align them.

**This is the single most important missing source.** Every other calibration
source is supplementary; this one is mandatory for spec compliance.

---

### V. National Footprint and Biocapacity Accounts (NFA 2025)

→ See **Section K** above for the canonical implementation, including the
`ConnectorResult`-compatible function with `proxy_method` populated per
spec §8.1. This section is retained here in the "Spec-Critical" grouping
because NFA 2025 is the required source for the §13.1 NRMSD ≤ 0.343
ecological footprint validation gate.

---

### W. Penn World Table 11.0 — With Capital Detail by Asset Type

| Detail | Value |
|---|---|
| **What** | Updated October 2025: 185 countries through 2023, plus new capital detail file breaking down investment by asset type (machinery, equipment, structures, R&D, etc.) |
| **Why it matters** | **Spec Section 15.1–15.3 requires empirical capital stock data for the WILIAM adapter's `capital.industrial_stock` mapping.** The `cn` variable is the total capital stock at constant national prices. The new capital detail file enables disaggregation of industrial vs. service capital. |
| **Source** | `https://www.rug.nl/ggdc/productivity/pwt/?lang=en` |
| **Download** | Dataverse DOI: `10.34894/FABVLR` |
| **Auth** | None. |
| **Format** | Excel (.xlsx) — two files: `pwt110.xlsx` and `pwt110_capital_detail.xlsx` |

**Python implementation:**
```python
import pandas as pd

def fetch_pwt_11() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download PWT 11.0 with capital detail (October 2025 release)."""
    # Main file
    df = pd.read_excel("pwt110.xlsx", sheet_name="Data")
    # Capital detail by asset type (machinery, equipment, structures, R&D)
    capital_detail = pd.read_excel("pwt110_capital_detail.xlsx")

    # Key variables in main file:
    # cn = capital stock at constant national prices
    # rnna = capital stock at current national prices
    # emp = employment (number of persons)
    # hc = human capital index
    # tfpna = TFP at constant national prices
    return df, capital_detail
```

---

### X. UN Comtrade — Trade + Production Flows for Resource Proxy

| Detail | Value |
|---|---|
| **What** | International trade and production flows for all commodities by country |
| **Why it matters** | **Spec Section 8.3 requires reconstruction of non-renewable stock from cumulative extraction plus reserve estimates.** USGS gives reserves; UN Comtrade gives extraction/production flows by commodity going back to 1900. Combined, they enable `stock(t) = initial_stock - cumulative_extraction(t)`. |
| **Base URL** | `https://comtradeapi.un.org/data/v1/get/` |
| **Auth** | None for bulk annual data (500 calls/hour). Free registration for higher limits. |
| **Format** | JSON, CSV |
| **Coverage** | 1962–present (some commodities back to 1900 via historical supplements) |

**Python implementation:**
```python
import requests
import pandas as pd

def fetch_comtrade_commodity(commodity_code: str, year_start: int = 1962) -> pd.DataFrame:
    """Fetch UN Comtrade production/trade data for a specific commodity.

    Commodity codes:
    - 2701: Coal
    - 2709: Petroleum oils, crude
    - 2710: Petroleum oils, refined
    - 2601-2899: Various minerals and ores
    """
    url = f"https://comtradeapi.un.org/data/v1/get/C/A/{commodity_code}"
    params = {
        "period": f"{year_start}:2024",
        "reporterCode": "all",  # or specific country codes
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data.get("results", []))
    return df
```

---

### Y. World Bank GDP Deflator — For Unit-Safe Food Per Capita Chain

| Detail | Value |
|---|---|
| **What** | GDP deflator growth rate (`NY.GDP.DEFL.KD.ZG`) — converts nominal to constant-price values |
| **Why it matters** | **Spec Section 8.2 requires explicit unit chain for food per capita: step 2 requires converting to calories using declared factors.** To do this unit-safely with `ConnectorResult.proxy_method` populated, you need the deflator series to normalize nominal GDP to constant prices before dividing by population. |
| **Endpoint** | Same World Bank API, zero extra auth needed |
| **Coverage** | ~1960–2024, all countries |

**Python implementation:**
```python
# Same function as existing World Bank connector
deflator_df = fetch_world_bank_indicator("NY.GDP.DEFL.KD.ZG", country="WLD")
```

---

### Z. FAO Food Balance Sheets — Bulk CSV

| Detail | Value |
|---|---|
| **What** | Food supply quantities (production + imports - exports - feed - seed - waste) by commodity and country |
| **Why it matters** | **Spec Section 8.2 requires the explicit food per capita unit chain.** FAOSTAT's individual item codes are complex. The bulk Food Balance Sheets CSV provides the entire dataset in one file, simplifying the `food.per_capita` ontology entity calibration. |
| **Source** | `https://www.fao.org/faostat/en/#data/FBS` |
| **Auth** | None. Direct CSV download. |
| **Format** | CSV (bulk download) |
| **Coverage** | 1961–2021, 200+ countries, 100+ commodities |

**Python implementation:**
```python
import pandas as pd

def fetch_fao_food_balance_sheets() -> pd.DataFrame:
    """Download FAO Food Balance Sheets bulk CSV."""
    # Download from https://www.fao.org/faostat/en/#data/FBS → Download data
    df = pd.read_csv("FoodBalanceSheets_E_All_Data.csv", encoding="latin-1")
    # Key columns: Area, Item, Element, Year, Value, Unit
    # Filter: Element = "Food supply (kcal/capita/day)" or "Food supply quantity"
    return df
```

---

## Updated Source Summary

### All Free Sources (Tiered by Value)

| Tier | Source | Variables | Period | Auth | Gap Filled |
|---|---|---|---|---|---|
| **S** | **Nebel 2023 Proxy CSVs** | Industrial output, food, services, pollution | ~1900–2020 | None | **MANDATORY for NRMSD validation** |
| **S** | Maddison Project | GDPpc, Population | 1820–2023 | None | ✅ 1900–1950 GDP/population |
| **S** | Penn World Table 11.0 | Capital stock, TFP, labor + asset detail | 1950–2023 | None | ✅ Industrial capital anchor |
| **S** | GCP Fossil CO₂ | Fossil CO₂ emissions | 1750–2023 | None | ✅ **1750–1970 CO₂ gap** |
| **S** | PRIMAP-hist | All GHGs, multi-sector | 1750–2023 | None | ✅ **Multi-gas pre-1970** |
| **S** | CEDS | SO₂, NOₓ, BC, OC, CO | 1750–2019 | None | ✅ **Reactive pollutants** |
| **A** | World Bank + Deflator | GDP, Population, GNI, deflator | ~1960–2024 | None | Core connector |
| **A** | UN Population | Population, fertility, life exp | 1950–2100 | None | Core connector |
| **A** | FAOSTAT + FBS Bulk | Food supply, arable land | 1961–2024 | None | Core connector |
| **A** | EIA | Energy production/consumption | 1900–2024 | Free key | ✅ Fossil fuel history |
| **A** | EDGAR | CO₂, CH₄, N₂O, pollutants | 1970–2024 | None | ✅ Country-level emissions |
| **A** | EI Stat. Review | Energy by fuel type, reserves | 1965–2024 | None | ✅ Granular energy data |
| **A** | IHME GBD | Mortality, DALYs, causes | 1990–2021 | Free reg. | ✅ Cause-of-death depth |
| **A** | NFA 2025 | Ecological footprint, biocapacity | 1961–present | Free reg. | ✅ **NRMSD ≤ 0.343 target** |
| **A** | UN Comtrade | Trade/production flows by commodity | 1962–2024 | None | ✅ **Resource stock reconstruction** |
| **B** | NOAA CO₂ | Atmospheric CO₂ (Mauna Loa) | 1958–2024 | None | Core connector |
| **B** | OWID | Energy, CO₂, GDP, mortality | 1800–2024 | None | Aggregator of many sources |
| **B** | HYDE | Population, cropland, pasture | 10,000BC–2020 | None | ✅ Pre-1900 land use |
| **B** | HMD | Age-specific death rates | 1750–present | Free reg. | ✅ Historical mortality |
| **B** | IMF WEO | GDP, inflation, debt | 1980–2029 | None | Cross-validation |
| **B** | Gapminder | 500+ indicators | 1800–2024 | None | Historical harmonization |
| **B** | NASA GISS | Temperature anomalies | 1880–present | None | Pollution-climate link |
| **B** | Berkeley Earth | Temperature anomalies | 1750–present | None | Long temperature record |
| **B** | OECD | GDP, CO₂, energy, trade | 1960–2024 | None | Developed nations |
| **B** | NASA Earthdata | Satellite emissions | 2014–present | Free login | Modern validation |
| **B** | Climate TRACE | Asset-level emissions | 2015–2025 | None | Facility-level check |
| **B** | Climate Watch | UNFCCC sector GHGs | 1990–present | None | Official reporting |
| **B** | Global Carbon Atlas | Land-use CO₂ flux | 1959–present | None | Carbon-flux perspective |
| **C** | USGS | Mineral production/reserves | ~1900–2024 | None | Core connector |
| **C** | UNIDO | Manufacturing value added | 1990–2022 | None | Core connector |
| **C** | UNDP HDR | HDI, education, income | 1990–2023 | None | Core connector |
| **C** | FRED | GDP deflator, CPI, PWT | 1929–present | Free key | Optional macro |

### Spec Calibration Targets → Source Mapping

| Spec Section | Calibration Variable | NRMSD Bound | Required Source | Status |
|---|---|---|---|---|
| §13.1 | Industrial output (GDP-deflated) | 0.321 direct | **Nebel 2023 supplement** | ✅ Added |
| §13.1 | Food production | 0.292 change-rate | **Nebel 2023 supplement** + FAO FBS bulk | ✅ Added |
| §13.1 | Service output | 0.354 direct | **Nebel 2023 supplement** | ✅ Added |
| §13.1 | Pollution index | 0.337 change-rate | **Nebel 2023 supplement** + GCP + CEDS | ✅ Added |
| §13.1 | Ecological footprint | 0.343 direct | **NFA 2025** | ✅ Added |
| §13.1 | Human welfare (HDI) | 0.178 direct | **IHME GBD** + HMD | ✅ Added |
| §8.3 | Non-renewable stock proxy | 0.757 change-rate | **USGS** + UN Comtrade | ✅ Added |
| §8.2 | Food per capita unit chain | 1.108 change-rate | **FAO FBS bulk** + WB deflator | ✅ Added |
| §15.3 | Industrial capital stock | — | **PWT 11.0** (`cn` + asset detail) | ✅ Added |
| §16.1 (v2.0) | EROI / energy-capital | reserved | **EI Stat. Review** primary energy | ✅ Added |
| §16.2 (v2.0) | Distinct mineral stocks | reserved | **USGS** + UN Comtrade | ✅ Added |

### What Each New Source Adds to Calibration

| Calibration Need | Current Coverage | What New Sources Add |
|---|---|---|
| **Population 1900–1950** | Gap (UN starts 1950) | Maddison + HYDE → ~1900 data |
| **Industrial capital stock** | Model only (no empirical anchor) | Penn World Table `cn` → real capital stock 1950–2023 |
| **TFP / productivity** | Not modeled | Penn World Table `tfpna` → validates capital-output dynamics |
| **Fossil fuel history** | Model only | EIA (US 1900+) + EI Stat. Review (global 1965+) |
| **CO₂ pre-1970** | Gap (EDGAR starts 1970) | **GCP** (1750+) + **PRIMAP-hist** (1750+) |
| **SO₂, NOₓ, aerosols** | Not covered at all | **CEDS** (1750–2019) — only source with pre-industrial reactive gases |
| **Country-level emissions** | Global CO₂ only (NOAA) | GCP + EDGAR + PRIMAP → 30+ pollutants × 200+ countries |
| **Pre-industrial baseline** | None | HYDE (land use) + CEDS (emissions) + GCP (CO₂) |
| **Temperature correlation** | None | NASA GISS + Berkeley Earth → pollution→temperature validation |
| **Mortality calibration** | UNDP HDI only (1990+) | **IHME GBD** (370+ causes) + **HMD** (age-specific, 1750+) |
| **Ecological overshoot** | None | Footprint Network → direct comparison to model carrying capacity |
| **Cross-source GDP validation** | World Bank only | Maddison (historical) + IMF + OECD (modern) → triple check |
| **Capital depreciation rates** | Assumed (5%) | PWT capital stock → empirical depreciation rates |
| **Agriculture yields** | Model only | HYDE cropland + FAOSTAT → real yield trajectories |
| **Welfare/HDI** | Not in base model | UNDP HDR + Gapminder → welfare sector validation |
| **Modern emissions validation** | None | Climate TRACE (asset-level) + NASA Earthdata (satellite) |

### Coverage After Adding All 31 Sources

| Variable | Required Period | Coverage | Sources |
|---|---|---|---|
| Population | 1900–2020 | ✅ **1820–2024** | Maddison (1820+), UN WPP (1950+), HYDE (pre-1900), Gapminder |
| Industrial Output / GDP | 1900–2020 | ✅ **1820–2024** | Maddison + World Bank + OWID + PWT |
| Capital Stock | 1900–2020 | ⚠️ **1950–2023** | Penn World Table — pre-1950 estimated |
| Food Production | 1900–2020 | ⚠️ **1961–2024** | FAOSTAT — pre-1961 via HYDE cropland proxy |
| CO₂ Emissions | 1900–2020 | ✅ **1750–2024** | GCP (1750+), EDGAR (1970+), NOAA (1958+), CEDS |
| Reactive Pollutants | 1900–2020 | ✅ **1750–2019** | CEDS (SO₂, NOₓ, BC, OC) |
| Multi-gas GHGs | 1900–2020 | ✅ **1750–2023** | PRIMAP-hist (CO₂, CH₄, N₂O, F-gases) |
| Energy by Fuel | 1900–2020 | ⚠️ **1965–2024** | EI Stat. Review + EIA (US 1900+) |
| Nonrenewable Resources | 1900–2020 | ⚠️ **~1900–2024** | USGS — sparse pre-1950 |
| Industrial Production | 1900–2020 | ✅ **1950–2023** | PWT, UNIDO, OECD |
| Mortality | 1900–2020 | ✅ **1750–2021** | HMD (1750+), IHME GBD (1990+), UN WPP |
| HDI / Welfare | 1900–2020 | ⚠️ **1990–2023** | UNDP — pre-1990 via Gapminder proxies |
| Temperature | 1900–2020 | ✅ **1750–present** | Berkeley Earth + NASA GISS |
| Ecological Footprint | 1900–2020 | ⚠️ **1961–2024** | Footprint Network |

**Remaining genuine gaps:**
- Capital stock pre-1950 (reconstructable from GDP + assumed investment rates)
- Food production pre-1961 (HYDE cropland area available, yield per hectare not).
  **This is a legitimate hard gap.** The spec's §8.4 "missing observation windows"
  failure mode should handle this explicitly — the calibration workflow should
  mark the 1900–1960 period as `proxy_method: "HYDE_cropland_proxy_with_assumed_yields"`
  and apply wider NRMSD tolerances for that window. FAO historical yearbooks exist
  but are not machine-readable at global scale.
- HDI pre-1990 (proxy-able via life expectancy + literacy from Gapminder/HMD)
- Mineral reserves pre-1900 (no systematic global data exists — this is a hard gap)

---

## Implementation Strategy

### Phase 1: Quick Wins (1-2 days, no auth)
1. **Maddison via OWID** — `owid-catalog` library, one-liner for 1820–2023 GDP/population
2. **Penn World Table** — Single Excel download, 47 variables, immediate capital stock anchor
3. **NASA GISS** — One-line `pd.read_csv()` from fixed URL
4. **Gapminder** — CSV per indicator, no auth

### Phase 2: Free API Keys (1 day)
5. **EIA** — Register for free key, access 100+ years of US energy data
6. **FRED** — Already registered if you have it; PWT data now mirrored

### Phase 3: Portal Downloads (2-3 days)
7. **EDGAR** — Download CO₂ and pollutant CSVs from the JRC portal
8. **HYDE** — Download from Kaggle or Dataverse.nl
9. **Footprint Network** — Register for free Public Data Package
10. **IMF WEO** — `weo` package (PyPI) handles everything

### Phase 4: SDMX Integration (1-2 days)
11. **OECD** — `sdmx1` library handles the protocol
12. **Berkeley Earth** — Direct text download (trivial)

---

## Data Coverage Gaps for World3-03 (Updated)

| Variable | Required Period | Coverage After Adding All Sources |
|---|---|---|
| Population | 1900–2020 | ✅ **1820–2023** (Maddison 1820–2008, UN WPP 1950–2024, Gapminder 1800–2024) |
| Industrial Output / GDP | 1900–2020 | ✅ **1820–2024** (Maddison + World Bank + OWID) |
| Capital Stock | 1900–2020 | ✅ **1950–2023** (Penn World Table) — pre-1950 still estimated |
| Food Production | 1900–2020 | ⚠️ **1961–2024** (FAOSTAT). Pre-1961 via HYDE cropland × yield estimates |
| CO₂ / Pollution | 1900–2020 | ✅ **1751–2024** (OWID/GCP 1751+, NOAA 1958+, EDGAR 1970+) |
| Nonrenewable Resources | 1900–2020 | ⚠️ **~1900–2024** (USGS). Sparse pre-1950 |
| Industrial Production | 1900–2020 | ✅ **1950–2023** (PWT, UNIDO, OECD). Pre-1950 via Maddison industrial estimates |
| HDI / Welfare | 1900–2020 | ⚠️ **1990–2023** (UNDP). Pre-1990 via Gapminder life expectancy + literacy proxies |
| Temperature | 1900–2020 | ✅ **1750–present** (Berkeley Earth + NASA GISS) |
| Ecological Footprint | 1900–2020 | ⚠️ **1961–2024** (Footprint Network) |

**Remaining gaps:**
- Capital stock pre-1950 (requires reconstruction from GDP + assumed investment rates)
- Food production pre-1961 (HYDE cropland area helps but not yield per hectare)
- HDI pre-1990 (proxy-able via component data)
- Mineral reserves pre-1900 (no systematic global data exists)

---

## Recommended Implementation Strategy

### Phase 1: Quick Wins (1–2 days, no auth, direct download)
1. **Nebel 2023 proxy CSVs** — PLOS ONE supplement, highest priority for NRMSD
2. **GCP Fossil CO₂** — Single XLSX download, 1750–2023, all countries
3. **Energy Inst. Stat. Review** — Single Excel workbook, 1965–2024, all fuels
4. **NOAA CO₂** — One-line `pd.read_csv()` from a fixed URL
5. **World Bank** — Simple `requests.get()` to a REST endpoint
6. **OWID** — `owid-catalog` library or direct CSV download
7. **USGS** — Download the annual MCS CSV
8. **PRIMAP-hist** — Direct CSV from Zenodo, multi-gas 1750+

### Phase 2: Portal Downloads (2–3 days)
9. **UN Population** — Download WPP 2024 CSV from the portal
10. **UNIDO** — Download INDSTAT 4 from the portal
11. **UNDP HDR** — Download from Data Futures portal
12. **FAOSTAT + FBS Bulk** — Download food balance sheets from the portal
13. **CEDS** — Download from Zenodo (NOT GitHub), 7 pollutants × 12 sectors
14. **Footprint Network** — Register for free Public Data Package

### Phase 3: Free Registration (1–2 days)
15. **EIA** — Register for free key, access 100+ years of US energy data
16. **FRED** — Register for free key, wire via `fredapi`
17. **IHME GBD** — Free registration, download cause-of-death data
18. **HMD** — Free registration (1–2 day approval), download life tables

### Phase 4: SDMX Integration (1–2 days)
19. **OECD** — `sdmx1` library handles the protocol
20. **IMF WEO** — `weo` package (PyPI) handles everything
21. **UN Comtrade** — Wire commodity API for resource stock reconstruction

### Phase 5: Validation Anchors (modern period)
22. **NASA Earthdata** — Free Earthdata login, satellite emissions
23. **Climate TRACE** — Open data download, asset-level emissions
24. **Climate Watch** — CSV download, UNFCCC sector data
25. **Global Carbon Atlas** — Land-use CO₂ flux download

### Phase 6: Historical Reconstruction
26. **Pre-1950 data** — Maddison + HYDE for GDP, population, land use
27. **Pre-1961 food data** — HYDE cropland proxy × estimated yields (wide NRMSD tolerance)
