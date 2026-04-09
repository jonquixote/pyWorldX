"""Freshness assessment — days since source last updated."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data_pipeline.storage.metadata_db import list_all_sources


def compute_freshness(db_path: Path) -> pd.DataFrame:
    """Compute freshness for each source.

    Args:
        db_path: Path to the metadata SQLite database.

    Returns:
        DataFrame with freshness metrics per source.
    """
    sources = list_all_sources(db_path)
    if not sources:
        return pd.DataFrame()

    records = []
    now = datetime.now(timezone.utc)

    for s in sources:
        fetched = s.get("fetched_at", "")
        if fetched:
            try:
                ts = datetime.fromisoformat(fetched)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_hours = (now - ts).total_seconds() / 3600
                age_days = age_hours / 24
            except (ValueError, TypeError):
                age_hours = -1
                age_days = -1
        else:
            age_hours = -1
            age_days = -1

        records.append({
            "source_id": s["source_id"],
            "version": s.get("version", "N/A"),
            "fetched_at": fetched,
            "age_hours": round(age_hours, 1) if age_hours >= 0 else None,
            "age_days": round(age_days, 1) if age_days >= 0 else None,
        })

    return pd.DataFrame(records)
