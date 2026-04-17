"""pyWorldX Data Pipeline — Configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from the pipeline directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
PIPELINE_DIR = Path(__file__).resolve().parent


class PipelineConfig(BaseModel):
    """Settings for the data pipeline."""
    model_config = {"populate_by_name": True, "extra": "ignore"}

    # Date ranges
    calibration_start: int = 1900
    calibration_end: int = 2020

    # API keys (read from env vars at init)
    fred_api_key: Optional[str] = None
    eia_api_key: Optional[str] = None
    faostat_token: Optional[str] = None

    def __init__(self, **data: Any) -> None:
        import os
        # Read from env as fallback
        if not data.get("fred_api_key"):
            data["fred_api_key"] = os.environ.get("FRED_API_KEY")
        if not data.get("eia_api_key"):
            data["eia_api_key"] = os.environ.get("EIA_API_KEY")
        if not data.get("faostat_token"):
            data["faostat_token"] = os.environ.get("FAOSTAT_TOKEN")
        # Path overrides from env vars (for CI/testing)
        if not data.get("raw_dir"):
            env_raw = os.environ.get("DATA_PIPELINE_RAW_DIR")
            if env_raw:
                data["raw_dir"] = Path(env_raw)
        if not data.get("aligned_dir"):
            env_aligned = os.environ.get("DATA_PIPELINE_ALIGNED_DIR")
            if env_aligned:
                data["aligned_dir"] = Path(env_aligned)
        if not data.get("cache_dir"):
            env_cache = os.environ.get("DATA_PIPELINE_CACHE_DIR")
            if env_cache:
                data["cache_dir"] = Path(env_cache)
        if not data.get("metadata_db"):
            env_db = os.environ.get("DATA_PIPELINE_METADATA_DB")
            if env_db:
                data["metadata_db"] = Path(env_db)
        super().__init__(**data)

    # Cache settings
    cache_dir: Path = Field(default=PIPELINE_DIR / ".cache")
    cache_ttl_days: int = 7  # Re-fetch if source is older than this

    # Storage paths
    raw_dir: Path = Field(default=PIPELINE_DIR / "data" / "raw")
    aligned_dir: Path = Field(default=PIPELINE_DIR / "data" / "aligned")
    metadata_db: Path = Field(default=PIPELINE_DIR / "data" / "metadata.sqlite")

    # Parallel fetch settings
    max_workers: int = 8
    request_timeout_seconds: int = 30
    retry_attempts: int = 3

    # Quality thresholds
    max_gap_years: int = 3  # Flag gaps longer than this
    outlier_z_threshold: float = 3.0
