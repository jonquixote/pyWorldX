"""pyWorldX Data Pipeline — Pydantic schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceDef(BaseModel):
    """Definition of a data source."""

    source_id: str                        # e.g. "world_bank", "gcp", "pwt"
    name: str                             # Human-readable name
    tier: str = "B"                       # S, A, B, C priority
    auth_required: bool = False
    auth_type: Optional[str] = None       # "api_key", "registration", "login"
    url: Optional[str] = None
    format: str = "csv"                   # csv, xlsx, json, txt, netcdf
    expected_columns: list[str] = Field(default_factory=list)
    version: Optional[str] = None         # e.g. "WPP2024", "PWT11.0"


class FetchResult(BaseModel):
    """Result of a single source fetch operation."""

    source_id: str
    status: str                           # "success", "skipped", "error"
    records_fetched: int = 0
    checksum_sha256: Optional[str] = None
    source_version: Optional[str] = None
    fetched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error_message: Optional[str] = None
    cache_hit: bool = False


class QualityReport(BaseModel):
    """Data quality assessment report."""

    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    cross_source_checks: list[dict[str, Any]] = Field(default_factory=list)
    freshness: dict[str, dict[str, Any]] = Field(default_factory=dict)
    overall_status: str = "pending"       # "pass", "warn", "fail"
