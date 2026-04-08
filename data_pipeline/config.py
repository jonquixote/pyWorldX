"""pyWorldX Data Pipeline — Configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
PIPELINE_DIR = Path(__file__).resolve().parent


class PipelineConfig(BaseModel):
    """Settings for the data pipeline."""

    # Date ranges
    calibration_start: int = 1900
    calibration_end: int = 2020

    # API keys (set via env vars or .env file)
    fred_api_key: Optional[str] = None
    eia_api_key: Optional[str] = None

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

    class Config:
        env_prefix = "PYWORLDX_DP_"
