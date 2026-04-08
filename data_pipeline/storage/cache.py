"""pyWorldX Data Pipeline — HTTP response cache with TTL + content-hash."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

import requests

from data_pipeline.config import PipelineConfig


def content_hash(response: requests.Response) -> str:
    """SHA-256 hash of response content."""
    return hashlib.sha256(response.content).hexdigest()


def fetch_with_cache(
    url: str,
    cache_dir: Path,
    source_id: str,
    ttl_days: int = 7,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 30,
) -> tuple[bytes, str, bool]:
    """Fetch a URL with disk-based caching.

    Args:
        url: URL to fetch.
        cache_dir: Directory for cached responses.
        source_id: Source identifier (used in cache filename).
        ttl_days: Time-to-live in days. 0 = always re-fetch.
        headers: Optional HTTP headers.
        params: Optional query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (content, content_hash, cache_hit).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Sanitize source_id for filename
    safe_id = source_id.replace("/", "_").replace("\\", "_")
    cache_file = cache_dir / f"{safe_id}.cache"
    meta_file = cache_dir / f"{safe_id}.meta"

    # Check if cache is fresh
    if cache_file.exists() and meta_file.exists() and ttl_days > 0:
        age_seconds = time.time() - meta_file.stat().st_mtime
        if age_seconds < ttl_days * 86400:
            return cache_file.read_bytes(), _file_hash(cache_file), True

    # Fetch from network
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()

    # Write to cache
    cache_file.write_bytes(response.content)
    meta_file.write_text(f"fetched={time.time()}\nurl={url}\n")

    return response.content, content_hash(response), False


def clear_cache(cache_dir: Path, source_id: Optional[str] = None) -> int:
    """Clear cached responses.

    Args:
        cache_dir: Directory containing cached responses.
        source_id: If provided, only clear this source's cache.
                   If None, clear all cached responses.

    Returns:
        Number of cache files removed.
    """
    if not cache_dir.exists():
        return 0

    count = 0
    for ext in ("*.cache", "*.meta"):
        for f in cache_dir.glob(ext):
            if source_id is None:
                f.unlink()
                count += 1
            elif source_id.replace("/", "_").replace("\\", "_") in f.stem:
                f.unlink()
                count += 1
    return count


def cache_status(cache_dir: Path, source_id: str, ttl_days: int = 7) -> dict:
    """Check cache status for a source.

    Returns:
        Dict with 'exists', 'age_hours', 'fresh', 'size_bytes'.
    """
    safe_id = source_id.replace("/", "_").replace("\\", "_")
    cache_file = cache_dir / f"{safe_id}.cache"
    meta_file = cache_dir / f"{safe_id}.meta"

    if not cache_file.exists() or not meta_file.exists():
        return {"exists": False, "age_hours": None, "fresh": False, "size_bytes": 0}

    age_seconds = time.time() - cache_file.stat().st_mtime
    return {
        "exists": True,
        "age_hours": round(age_seconds / 3600, 1),
        "fresh": age_seconds < ttl_days * 86400,
        "size_bytes": cache_file.stat().st_size,
    }


def _file_hash(path: Path) -> str:
    """SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
