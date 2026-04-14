"""Data pipeline — connectors, transformations, and caching.

Architecture
------------
pyWorldX uses a two-layer data architecture:

1. **data_pipeline/** (production ingest layer)
   27 working connectors for real-world data sources (World Bank, FAOSTAT,
   FRED, NOAA, etc.).  Handles API access, caching, retries, rate limiting.

2. **pyworldx/data/** (calibration interface)
   - ``connectors/base.py`` — ``DataConnector`` protocol and ``ConnectorResult``
   - ``connectors/csv_connector.py`` — loads local CSV/Parquet files
   - ``bridge.py`` — ``DataBridge`` translates between data_pipeline entities
     and engine variable names via ``ENTITY_TO_ENGINE_MAP``

The DataBridge is the integration point: calibration code calls
``DataBridge.fetch()`` which delegates to data_pipeline connectors,
translates entity names to engine variable names, and returns results
in the format the engine expects.

Dead stub connectors (world_bank, fred, faostat, etc.) that duplicated
data_pipeline functionality were removed in Phase 0 (v0.2.9).
"""
