"""pyWorldX Data Pipeline — SQLite metadata database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional


def init_db(db_path: Path) -> None:
    """Create metadata tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS source_versions (
            source_id TEXT PRIMARY KEY,
            version TEXT,
            checksum_sha256 TEXT,
            records_fetched INTEGER DEFAULT 0,
            fetched_at TEXT,
            url TEXT,
            format TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS fetch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            status TEXT,
            records_fetched INTEGER DEFAULT 0,
            checksum_sha256 TEXT,
            fetched_at TEXT,
            error_message TEXT,
            cache_hit INTEGER DEFAULT 0,
            duration_seconds REAL
        );

        CREATE TABLE IF NOT EXISTS transform_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transform_name TEXT,
            status TEXT,
            input_sources TEXT,
            output_entities TEXT,
            records_written INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS quality_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT,
            entity TEXT,
            metric_name TEXT,
            metric_value REAL,
            status TEXT,
            details TEXT
        );
    """)
    conn.commit()
    conn.close()


def record_fetch(
    db_path: Path,
    source_id: str,
    status: str,
    records: int = 0,
    checksum: Optional[str] = None,
    fetched_at: Optional[str] = None,
    error_message: Optional[str] = None,
    cache_hit: bool = False,
    duration: float = 0.0,
) -> None:
    """Log a fetch operation to the metadata database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO fetch_log
            (source_id, status, records_fetched, checksum_sha256,
             fetched_at, error_message, cache_hit, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (source_id, status, records, checksum, fetched_at,
         error_message, int(cache_hit), duration),
    )
    conn.commit()
    conn.close()


def record_source_version(
    db_path: Path,
    source_id: str,
    version: str,
    checksum: str,
    records: int = 0,
    fetched_at: Optional[str] = None,
    url: Optional[str] = None,
    fmt: str = "csv",
    notes: Optional[str] = None,
) -> None:
    """Record or update a source version in the metadata database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT OR REPLACE INTO source_versions
            (source_id, version, checksum_sha256, records_fetched,
             fetched_at, url, format, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (source_id, version, checksum, records, fetched_at, url, fmt, notes),
    )
    conn.commit()
    conn.close()


def record_transform(
    db_path: Path,
    transform_name: str,
    status: str,
    input_sources: str,
    output_entities: str,
    records_written: int = 0,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Log a transform operation to the metadata database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO transform_log
            (transform_name, status, input_sources, output_entities,
             records_written, started_at, completed_at, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (transform_name, status, input_sources, output_entities,
         records_written, started_at, completed_at, error_message),
    )
    conn.commit()
    conn.close()


def get_source_info(db_path: Path, source_id: str) -> Optional[dict[str, Any]]:
    """Get the latest version info for a source."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM source_versions WHERE source_id = ?", (source_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_all_sources(db_path: Path) -> list[dict[str, Any]]:
    """List all sources with their latest version info."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM source_versions ORDER BY source_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
