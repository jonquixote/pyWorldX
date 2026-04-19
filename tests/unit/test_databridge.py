"""Unit tests for DataBridge zero-guard and cache checks — T2-3 and T2-4."""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

from pyworldx.data.bridge import DataBridge, DataBridgeError
from pyworldx.calibration.metrics import CrossValidationConfig


@pytest.fixture
def bridge(tmp_path):
    return DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())


# ── T2-3: Zero-guard in _normalize_to_index ──────────────────────────

def test_normalize_divides_by_base_year(bridge):
    s = pd.Series({1968: 2.0, 1970: 4.0, 1975: 8.0})
    result = bridge._normalize_to_index(s, base_year=1970)
    assert result[1968] == pytest.approx(0.5)
    assert result[1970] == pytest.approx(1.0)
    assert result[1975] == pytest.approx(2.0)


def test_normalize_zero_base_falls_back_to_nearby_nonzero(bridge):
    s = pd.Series({1969: 0.0, 1970: 0.0, 1971: 3.5, 1975: 7.0})
    result = bridge._normalize_to_index(s, base_year=1970)
    # 1971 = 3.5 is the fallback base; 1975 / 3.5 = 2.0
    assert result[1975] == pytest.approx(2.0)
    assert result[1971] == pytest.approx(1.0)


def test_normalize_no_nonzero_raises_databridge_error(bridge):
    s = pd.Series({1965: 0.0, 1970: 0.0, 1975: 0.0})
    with pytest.raises(DataBridgeError, match="no non-zero base value"):
        bridge._normalize_to_index(s, base_year=1970)


def test_normalize_result_contains_no_inf_or_nan(bridge):
    s = pd.Series({1970: 1.0, 1980: 2.0, 1990: 0.0})  # zero mid-series is fine
    result = bridge._normalize_to_index(s, base_year=1970)
    assert not result.isin([np.inf, -np.inf]).any()
    assert not result.isna().any()


def test_normalize_base_year_is_config_train_start(bridge):
    """Callers must pass config.train_start — never a literal int."""
    s = pd.Series({CrossValidationConfig.train_start: 1.0, 1980: 2.0})
    result = bridge._normalize_to_index(s, base_year=CrossValidationConfig.train_start)
    assert result[CrossValidationConfig.train_start] == pytest.approx(1.0)


# ── T2-4: Parquet cache staleness check ──────────────────────────────

def test_load_targets_raises_databridge_error_when_parquet_missing(bridge):
    with pytest.raises(DataBridgeError, match="Parquet cache missing"):
        bridge.load_targets()


def test_load_targets_error_names_the_connector(tmp_path):
    b = DataBridge(aligned_dir=tmp_path, config=CrossValidationConfig())
    try:
        b.load_targets()
    except DataBridgeError as e:
        assert "python -m data_pipeline" in str(e), (
            "DataBridgeError must include the command to regenerate the cache."
        )


def test_load_targets_warns_on_stale_cache(tmp_path, caplog):
    import logging, time, os
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    # Create a parquet that is artificially old
    p = aligned / "population_total__un_wpp.parquet"
    pd.DataFrame({"year": [1970], "value": [3.5e9]}).to_parquet(p)
    # Back-date modification time by 40 days
    old_time = time.time() - (40 * 86400)
    os.utime(p, (old_time, old_time))
    b = DataBridge(aligned_dir=aligned, config=CrossValidationConfig())
    with caplog.at_level(logging.WARNING):
        try:
            b.load_targets()
        except DataBridgeError:
            pass  # other caches missing; we only care about the stale warning
    assert any(
        "stale" in r.message.lower() or "days old" in r.message.lower()
        for r in caplog.records
    ), (
        "DataBridge must warn when a cached Parquet file is older than cache_ttl days."
    )


def test_databridge_has_cache_ttl_attribute():
    """cache_ttl must be a named class attribute on DataBridge, not a magic number."""
    assert hasattr(DataBridge, "cache_ttl"), (
        "DataBridge.cache_ttl must be a class attribute (default 30 days)"
    )
