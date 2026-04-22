# Data Pipeline ↔ pyWorldX Integration Report

## Executive Summary

The data pipeline has **37 working connectors** producing empirical time-series data across population, emissions, GDP, food, temperature, and pollution domains. However, there is currently **no working bridge** between this data and the pyWorldX calibration system. This report describes the gap, proposes a concrete integration architecture, and maps every pipeline entity to its engine counterpart.

---

## Part 1: Current Architecture

### 1.1 What We Have

```
┌──────────────────────────────────────────────────────────────────────┐
│                       DATA PIPELINE (37 connectors)                  │
│  World Bank, OWID, FAOSTAT, EDGAR, GCP, NOAA, NASA GISS,           │
│  FRED, IEA, CEDS, HYDE, HMD, IHME, Maddison, PWT, ...             │
│                                                                      │
│  → Raw Parquet Store → Alignment/Transform → Aligned Parquet Store   │
│     source_id/*.parquet    ontology mapping      entity/*.parquet    │
│                                                                      │
│  Outputs: ConnectorResult / PipelineConnectorResult dataclass        │
│           pd.Series with year index + unit + provenance              │
└──────────────────────────────────────────────────────────────────────┘
                                ↓ (NOT YET CONNECTED)
┌──────────────────────────────────────────────────────────────────────┐
│                       pyWorldX ENGINE                                │
│  5 sectors: Population, Capital, Agriculture, Resources, Pollution   │
│  + Welfare (observer) + Adaptive Technology                         │
│                                                                      │
│  Calibration pipeline: ProfileLikelihood → Morris → NelderMead → Sobol│
│                                                                      │
│  Ontology Registry: VariableEntry with world3_name mapping           │
│  Parameter Registry: ParameterEntry with bounds + defaults           │
│  ConnectorResult: pd.Series (year-indexed) for NRMSD comparison      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 The Gap

The gap is at the **alignment layer**. Specifically:

1. **No automated entity-to-variable mapping**: The pipeline's `ONTOLOGY_MAP` maps raw sources to pipeline entities (e.g., `"population.total"`), but there's no mapping FROM pipeline entities TO engine variables (e.g., `"POP"`).

2. **No NRMSD target generation**: The calibration pipeline's `objective_fn` expects `dict[str, float] → float` (parameter vector → scalar NRMSD). Nobody has written the function that:
   - Takes calibrated parameters
   - Runs the engine
   - Compares engine trajectories against pipeline data
   - Returns composite NRMSD

3. **Unit mismatch**: The pipeline operates in real-world units (kt CO2, ppm, persons, $). The engine uses abstract "resource_units", "pollution_units", "food_units". No unit conversion layer exists.

4. **Temporal mismatch**: Most pipeline data covers 1960–2024. The engine runs 1900–2100. No temporal alignment or extrapolation logic exists.

5. **No reference model connector**: Without correct W3-03 table values, even if we had the bridge, calibration would optimize toward wrong targets.

---

## Part 2: Entity Mapping — Pipeline → Engine

### 2.1 Direct Mappings (Strong Empirical Anchors)

These pipeline entities map directly to engine variables with clear correspondence:

| Pipeline Entity | Engine Variable | Pipeline Sources | Coverage | Unit Mapping |
|---|---|---|---|---|
| `population.total` | `POP` | World Bank `SP.POP.TOTL`, Maddison, UN | 1960–2024 | 1:1 (persons) |
| `emissions.co2_fossil` | `PPOL` proxy | EDGAR, GCP, PRIMAP, OWID | 1970–2024 | Need scaling factor |
| `atmospheric.co2` | `PPOL` proxy | NOAA Mauna Loa, OWID | 1958–2024 | ppm → pollution_units |
| `temperature.anomaly` | (none — observational) | NASA GISS, Berkeley Earth | 1880–2024 | Validation only |
| `food.supply.kcal_per_capita` | `food_per_capita` | FAOSTAT FBS | 1961–2022 | kcal → veg_equiv_kg |
| `gdp.per_capita` | `industrial_output_per_capita` | World Bank, PWT, Maddison | 1960–2024 | 2015 USD → $ |
| `land.arable_hectares` | `AL` | FAOSTAT, HYDE | 1961–2022 | 1:1 (hectares) |
| `hdi.human_development_index` | `human_welfare_index` | UNDP HDR | 1990–2022 | 1:1 (index) |

### 2.2 Proxy Mappings (Require Transform Chain)

| Pipeline Entity | Engine Variable | Transform Needed |
|---|---|---|
| `industry.manufacturing_value_added` | `IC` | VA is flow, IC is stock — need stock estimation |
| `emissions.co2_total` × toxicity | `pollution_generation` | Apply IMTI, FRPM, IMEF constants |
| `energy.primary_consumption` | `NRUR` proxy | Energy → resource units scaling |
| `gdp.current_usd` | `industrial_output` | GDP ≈ IO + SO + food — need disaggregation |

### 2.3 Missing Entity Mappings (No Pipeline Source)

| Engine Variable | What's Needed | Potential Source |
|---|---|---|
| `NR` (nonrenewable stock) | Abstract aggregate resource stock | World3-03 reference run |
| `nr_fraction_remaining` | Depletion trajectory | World3-03 reference run |
| `IC` (industrial capital stock) | Capital stock, not flow | Penn World Tables (rgdpna × ck) |
| `SC` (service capital stock) | Service sector capital | PWT or Maddison |
| `PPOL` (persistent pollution) | Specific index, not CO2 alone | Composite indicator needed |
| `Land Fertility` | Soil quality index | FAOSTAT soil data (limited) |

---

## Part 3: Proposed Integration Architecture

### 3.1 Three-Layer Calibration Stack

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1: WORLD3-03 REFERENCE (Structural Correctness)          │
│                                                                    │
│  Source: Vensim MDL → parsed tables & constants + PyWorld3-03 runs │
│  Purpose: Verify our engine matches canonical W3-03 behavior      │
│  Metric: NRMSD(our_trajectory, w3_reference_trajectory)           │
│  Coverage: All 5 sectors, 1900-2100, all 10 scenarios             │
│  Target: NRMSD < 0.01 for base run                                │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 2: EMPIRICAL DATA (Real-World Calibration)                │
│                                                                    │
│  Source: 37 data pipeline connectors                               │
│  Purpose: Tune free parameters to match observed reality           │
│  Metric: NRMSD(our_trajectory, empirical_observation)              │
│  Coverage: Per-variable, 1960-2024 (varies)                       │
│  Target: NRMSD < 0.15 for population, food, GDP                  │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 3: USGS MINERAL DATA (Cross-Validation)                   │
│                                                                    │
│  Source: 93 USGS commodity summaries, 1996-2026                   │
│  Purpose: Validate resource depletion proxy dynamics               │
│  Metric: Correlation of aggregate extraction trend vs NRUR         │
│  Coverage: 93 minerals, 1996-2026                                  │
│  Target: Qualitative agreement (r > 0.7)                          │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Integration Components to Build

#### Component 1: `DataBridge` (Pipeline → Engine)

A module that translates pipeline `ConnectorResult` objects into engine-compatible calibration targets.

```python
# pyworldx/data/bridge.py
@dataclass
class CalibrationTarget:
    """A time-series target for NRMSD comparison."""
    variable_name: str        # Engine variable (e.g., "POP")
    years: np.ndarray         # Year indices
    values: np.ndarray        # Observed values
    unit: str                 # Standard unit
    weight: float = 1.0       # Weight in composite NRMSD
    source: str = ""          # Provenance

class DataBridge:
    """Connects data pipeline outputs to engine calibration."""
    
    def load_targets(
        self, aligned_dir: Path, entity_map: dict
    ) -> list[CalibrationTarget]:
        """Load aligned data as calibration targets."""
        ...
    
    def build_objective(
        self, targets: list[CalibrationTarget], engine_factory: Callable
    ) -> Callable[[dict[str, float]], float]:
        """Build NRMSD objective function from targets."""
        ...
```

#### Component 2: `World3ReferenceConnector`

A pipeline connector that produces canonical W3-03 trajectories.

```python
# data_pipeline/connectors/world3_reference.py
class World3ReferenceConnector:
    """Provides canonical World3-03 reference trajectories."""
    
    name = "world3_reference"
    
    def fetch(self, variable_name: str) -> ConnectorResult:
        """Return pre-computed W3-03 trajectory."""
        # Source: PyWorld3-03 Validation spreadsheet
        # or: Parsed MDL + forward integration
        ...
    
    def available_variables(self) -> list[str]:
        return [
            "population", "industrial_output", "food_per_capita",
            "nonrenewable_resources", "persistent_pollution",
            "nr_fraction_remaining", "life_expectancy",
            "human_welfare_index", "ecological_footprint",
        ]
```

#### Component 3: `USGSMineralsConnector` Enhancement

Currently a basic fetcher. Needs aggregation logic:

```python
# data_pipeline/connectors/usgs.py (enhanced)
class USGSMineralsConnector:
    """Aggregates 93 USGS mineral commodities into proxy indices."""
    
    def fetch(self, variable_name: str) -> ConnectorResult:
        if variable_name == "resource_extraction_index":
            # Aggregate world production across all commodities
            # Normalize to 1996 baseline
            ...
        elif variable_name == "reserve_depletion_ratio":
            # cumulative_extraction / reserves for each commodity
            # Weighted average
            ...
```

#### Component 4: `EmpiricalCalibrationRunner`

Ties everything together:

```python
# pyworldx/calibration/empirical.py
class EmpiricalCalibrationRunner:
    """Runs calibration against empirical data."""
    
    def __init__(
        self,
        aligned_dir: Path,
        usgs_dir: Path,
        reference_dir: Path | None = None,
    ):
        self.bridge = DataBridge()
        self.targets = self.bridge.load_targets(aligned_dir, ENTITY_TO_ENGINE_MAP)
    
    def run(self, registry: ParameterRegistry) -> PipelineReport:
        """Execute the calibration pipeline with empirical targets."""
        objective = self.bridge.build_objective(self.targets, self._engine_factory)
        return run_calibration_pipeline(objective, registry)
```

---

## Part 4: What Each Existing Connector Provides

### Population & Demographics

| Connector | Pipeline Entity | Engine Variable | Quality |
|---|---|---|---|
| `world_bank` SP.POP.TOTL | `population.total` | `POP` | ⭐⭐⭐ Excellent |
| `maddison` | `gdp.maddison` | GDP proxy | ⭐⭐⭐ 1820-2022 |
| `un_population` | `population.total` | `POP` validation | ⭐⭐⭐ |
| `hmd` | mortality data | `death_rate` validation | ⭐⭐ |
| `ihme_gbd` | disease burden / LE | `life_expectancy` validation | ⭐⭐ |
| `gapminder` | LE, pop by country | `life_expectancy` validation | ⭐⭐ |

### Industrial & Economic

| Connector | Pipeline Entity | Engine Variable | Quality |
|---|---|---|---|
| `world_bank` NY.GDP.MKTP.CD | `gdp.current_usd` | `industrial_output` proxy | ⭐⭐⭐ |
| `world_bank` NV.IND.MANF.ZS | `industry.manufacturing_share` | `frac_io_to_industry` | ⭐⭐ |
| `pwt` | GDP, capital stock | `IC`, `industrial_output` | ⭐⭐⭐ |
| `fred` | US economic indicators | US-only validation | ⭐ |
| `imf_weo` | GDP forecasts | Forward-looking validation | ⭐⭐ |
| `unido` | Manufacturing VA | `IC` proxy | ⭐⭐ |

### Agriculture & Food

| Connector | Pipeline Entity | Engine Variable | Quality |
|---|---|---|---|
| `faostat` | food supply, cropland | `food_per_capita`, `AL` | ⭐⭐⭐ |
| `owid` | yield, fertilizer | `land_yield` validation | ⭐⭐ |
| `hyde` | historical land use | `AL` (1900-1960) | ⭐⭐ Pre-1960 |

### Pollution & Climate

| Connector | Pipeline Entity | Engine Variable | Quality |
|---|---|---|---|
| `edgar` | CO2 by sector | `pollution_generation` proxy | ⭐⭐⭐ |
| `gcp` | global carbon budget | `pollution_generation` proxy | ⭐⭐⭐ |
| `noaa` | Mauna Loa CO2 | `pollution_index` proxy | ⭐⭐⭐ |
| `nasa_giss` | temperature anomaly | Validation only | ⭐⭐⭐ |
| `ceds` | historical emissions | `pollution_generation` 1750-2019 | ⭐⭐⭐ |
| `primap` | national PRIMAPhist | Validation / decomposition | ⭐⭐ |
| `climate_trace` | sector emissions | Decomposition validation | ⭐⭐ |
| `berkeley_earth` | temperature | Validation | ⭐⭐ |

### Resources

| Connector | Pipeline Entity | Engine Variable | Quality |
|---|---|---|---|
| `usgs` | 93 mineral commodities | `NR` proxy (indirect) | ⭐ Indirect |
| `eia` | energy data | `NRUR` proxy (energy) | ⭐⭐ US-centric |
| `ei_review` | BP/EI energy review | Energy → resources | ⭐⭐ |

### Welfare & Development

| Connector | Pipeline Entity | Engine Variable | Quality |
|---|---|---|---|
| `undp` | HDI data | `human_welfare_index` | ⭐⭐⭐ |
| `footprint_network` | Ecological footprint | `ecological_footprint` | ⭐⭐ |

---

## Part 5: Unit Conversion Strategy

The biggest integration challenge is **unit conversion** between real-world data and World3-03's abstract units.

### Proposed Approach: Normalization Bridges

Rather than converting real-world units to abstract World3 units (which is mathematically meaningless), we normalize both to **relative indices** for NRMSD comparison:

```
Engine output:  POP_engine(t)  → POP_engine(t) / POP_engine(1970)  = normalized engine trajectory
Observed data:  POP_observed(t) → POP_observed(t) / POP_observed(1970) = normalized empirical trajectory
NRMSD:          compare normalized trajectories
```

This works because NRMSD cares about the **shape** and **timing** of trajectories, not absolute magnitudes.

For stocks with abstract units (NR, PPOL), we use the World3-03 reference trajectory as the normalization target:
```
NR_engine(t)    / NR_engine(1970)     vs.  NR_reference(t) / NR_reference(1970)
```

---

## Part 6: Integration Roadmap

### Phase 0: Fix Engine Tables (PREREQUISITE)
Before any calibration makes sense, fix the sector tables to match W3-03.
Without this, calibration will find parameters that compensate for wrong tables.

### Phase 1: Build the Bridge
1. Create `pyworldx/data/bridge.py` — DataBridge class
2. Define `ENTITY_TO_ENGINE_MAP` constant
3. Implement normalization and NRMSD comparison
4. Add temporal alignment (linear interpolation to engine timesteps)

### Phase 2: World3-03 Reference Layer
1. Create `data_pipeline/connectors/world3_reference.py`
2. Parse Vensim MDL tables into structured JSON
3. Import PyWorld3-03 validation data
4. Target: Engine NRMSD < 0.01 vs W3-03 reference

### Phase 3: Empirical Calibration
1. Create `pyworldx/calibration/empirical.py` — EmpiricalCalibrationRunner
2. Build composite NRMSD objective from bridge targets
3. Run calibration pipeline with empirical targets
4. Report per-variable and composite NRMSD scores

### Phase 4: USGS Cross-Validation
1. Enhance `data_pipeline/connectors/usgs.py` with aggregation
2. Build resource depletion proxy index
3. Compare against engine NRUR trajectory
4. Report correlation metrics

---

## Part 7: Key Design Decisions Needed

> [!IMPORTANT]
> ### Q1: What is the calibration baseline year?
> World3-03 initializes at 1900, but most empirical data starts at 1960. Should we:
> - (a) Calibrate only against 1960-2024 data (ignoring 1900-1959)?
> - (b) Use HYDE/Maddison for 1900-1960 coverage?
> - (c) Start the engine at 1960 with empirically-derived initial conditions?

> [!IMPORTANT]
> ### Q2: Which scenarios to support?
> W3-03 has 10 named scenarios (Standard Run, Comprehensive Technology, etc.) that differ by POLICY_YEAR and table switching. Should we:
> - (a) Implement all 10 scenarios as parameter presets?
> - (b) Start with Standard Run only?
> - (c) Implement the scenario system but calibrate against Standard Run?

> [!IMPORTANT]
> ### Q3: How to weight the NRMSD composite?
> With 8+ calibration variables, how should we weight them? Options:
> - (a) Equal weights (simplest)
> - (b) Weight by data quality rating (⭐-⭐⭐⭐)
> - (c) Weight by sector importance in feedback loops
> - (d) Use Sobol sensitivity analysis to determine weights

---

## References & External Sources

### Model Reference Files

1. **`wrld3-03.mdl`** — Canonical World3-03 model file (Vensim format). The authoritative source for all equations, table functions, and initial conditions.
   - URL: `https://vensim.com/documentation/Models/Sample/WRLD3-03/wrld3-03.mdl`

2. **MetaSD World3-03 package** — Downloadable zip with Vensim and STELLA versions, hosted by Tom Fiddaman.
   - URL: `https://metasd.com/2010/04/world3-03/`

3. **PyWorld3-03** — Python port of World3-03 by Charles Vanwynsberghe. Used as secondary reference for table values and validation trajectories.
   - GitHub: `https://github.com/cvanwynsberghe/pyworld3`

### Academic References

4. **Meadows, D.H., Randers, J. & Meadows, D.L. (2004).** *Limits to Growth: The 30-Year Update.* Chelsea Green Publishing.
   - ISBN: 978-1-931498-58-6

5. **Herrington, G. (2021).** "Update to limits to growth: Comparing the World3 model with empirical data." *Journal of Industrial Ecology*, 25(3), 614–626.
   - DOI: `https://doi.org/10.1111/jiec.13084`
   - Provides empirical trajectory comparisons for population, industrial output, food, pollution (2020 data vs W3-03 scenarios)

6. **Meadows, D.L. et al. (1974).** *Dynamics of Growth in a Finite World.* Wright-Allen Press.
   - ISBN: 978-0-96040-0-4

### Population & Demographics Data Sources

7. **World Bank Open Data** — `SP.POP.TOTL` (total population), `SP.DYN.LE00.IN` (life expectancy).
   - API: `https://api.worldbank.org/v2/`
   - Portal: `https://data.worldbank.org/`

8. **UN Population Division — World Population Prospects** — Population estimates and projections.
   - URL: `https://population.un.org/wpp/`
   - API: `https://population.un.org/dataportalapi/api/v1/`

9. **Maddison Project Database 2023** — Historical GDP per capita and population from 1 CE.
   - URL: `https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023`

10. **Human Mortality Database (HMD)** — Mortality rates and life tables by country.
    - URL: `https://www.mortality.org/`

11. **IHME Global Burden of Disease** — Disease burden, life expectancy, and mortality.
    - URL: `https://www.healthdata.org/research-analysis/gbd`

12. **Gapminder** — Life expectancy, population, income datasets.
    - URL: `https://www.gapminder.org/data/`
    - GitHub: `https://github.com/open-numbers/ddf--gapminder--systema_globalis`

### Industrial & Economic Data Sources

13. **Penn World Tables (PWT 10.01)** — Real GDP, capital stocks (`ck`), TFP.
    - URL: `https://www.rug.nl/ggdc/productivity/pwt/`
    - Key variables: `rgdpna` (real GDP), `ck` (capital stock), `ctfp` (TFP)

14. **IMF World Economic Outlook (WEO)** — GDP forecasts and macroeconomic indicators.
    - URL: `https://www.imf.org/en/Publications/WEO`
    - Data: `https://www.imf.org/en/Publications/WEO/weo-database/`

15. **FRED (Federal Reserve Economic Data)** — US economic time series.
    - URL: `https://fred.stlouisfed.org/`
    - API: `https://api.stlouisfed.org/fred/`

16. **UNIDO INDSTAT** — Manufacturing value added by country and sector.
    - URL: `https://stat.unido.org/`

### Agriculture & Food Data Sources

17. **FAOSTAT** — Food Balance Sheets (food supply kcal/capita/day), arable land, agricultural inputs.
    - URL: `https://www.fao.org/faostat/en/#data`
    - API: `https://fenixservices.fao.org/faostat/api/v1/`
    - Key domains: `FBS` (Food Balance Sheets), `RL` (Land Use), `RFN` (Fertilizers)

18. **HYDE 3.3 (History Database of the Global Environment)** — Historical land use from 10,000 BCE to 2023.
    - URL: `https://doi.org/10.24416/UU01-AEZZIT`
    - Documentation: `https://landuse.sites.uu.nl/`

19. **Our World in Data** — Agricultural yields, fertilizer use, food supply.
    - URL: `https://ourworldindata.org/`
    - GitHub: `https://github.com/owid/owid-datasets` and `https://github.com/owid/etl`

### Pollution & Climate Data Sources

20. **EDGAR v8.0 (Emissions Database for Global Atmospheric Research)** — CO2 emissions by sector and country.
    - URL: `https://edgar.jrc.ec.europa.eu/`
    - Dataset: `https://edgar.jrc.ec.europa.eu/dataset_ghg80`

21. **Global Carbon Project — Global Carbon Budget** — Fossil CO2 emissions, land-use change, ocean/land sinks.
    - URL: `https://www.globalcarbonproject.org/carbonbudget/`
    - Data: `https://doi.org/10.18160/GCP-2023`

22. **NOAA Global Monitoring Laboratory — Mauna Loa CO2** — Atmospheric CO2 concentration (1958-present).
    - URL: `https://gml.noaa.gov/ccgg/trends/data.html`
    - Direct CSV: `https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.csv`

23. **NASA GISS Surface Temperature Analysis (GISTEMP v4)** — Global temperature anomaly.
    - URL: `https://data.giss.nasa.gov/gistemp/`

24. **Berkeley Earth** — Global temperature record (land + ocean).
    - URL: `https://berkeleyearth.org/data/`

25. **CEDS (Community Emissions Data System)** — Historical emissions 1750-2019.
    - URL: `https://github.com/JGCRI/CEDS`
    - Data: `https://zenodo.org/records/4741285`

26. **PRIMAP-hist** — National historical emissions (composite dataset).
    - URL: `https://doi.org/10.5281/zenodo.7727475`

27. **Climate TRACE** — Sector-level emissions from satellite and ML.
    - URL: `https://climatetrace.org/`
    - API: `https://api.climatetrace.org/`

### Resource Data Sources

28. **USGS Mineral Commodity Summaries** — Annual world production, reserves, and prices for 93 minerals.
    - URL: `https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries`
    - Historical data: `https://www.usgs.gov/centers/national-minerals-information-center/historical-statistics-mineral-and-material-commodities`

29. **EIA (U.S. Energy Information Administration)** — Primary energy consumption, production.
    - URL: `https://www.eia.gov/`
    - API: `https://api.eia.gov/v2/`

30. **Energy Institute Statistical Review** (formerly BP Statistical Review) — Global energy data.
    - URL: `https://www.energyinst.org/statistical-review`

### Welfare & Development Data Sources

31. **UNDP Human Development Reports** — Human Development Index (HDI) data.
    - URL: `https://hdr.undp.org/data-center/human-development-index`
    - API: `https://hdr.undp.org/api/v1/`

32. **Global Footprint Network** — Ecological Footprint data.
    - URL: `https://www.footprintnetwork.org/`
    - Data: `https://data.footprintnetwork.org/`

### Internal Project Sources

33. **pyWorldX data pipeline connectors** — All 37 connector implementations:
    - [connectors/](file:///Users/johnny/pyWorldX/data_pipeline/connectors/)

34. **pyWorldX engine core** — Sector implementations, calibration pipeline, ontology:
    - [engine.py](file:///Users/johnny/pyWorldX/pyworldx/core/engine.py)
    - [base.py](file:///Users/johnny/pyWorldX/pyworldx/data/connectors/base.py) (ConnectorResult protocol)
    - [connector_result.py](file:///Users/johnny/pyWorldX/data_pipeline/export/connector_result.py) (PipelineConnectorResult bridge)
    - [initial_conditions.py](file:///Users/johnny/pyWorldX/data_pipeline/alignment/initial_conditions.py)
    - [map.py](file:///Users/johnny/pyWorldX/data_pipeline/alignment/map.py) (ONTOLOGY_MAP)
    - [pipeline.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/pipeline.py) (calibration pipeline)
    - [parameters.py](file:///Users/johnny/pyWorldX/pyworldx/calibration/parameters.py) (parameter registry)
    - [registry.py](file:///Users/johnny/pyWorldX/pyworldx/ontology/registry.py) (ontology registry)
