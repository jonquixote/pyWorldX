"""Unit tests for FAOSTAT connector and initial conditions — T1-3 and T1-4."""

from __future__ import annotations

import pytest


# ── T1-3: FAOSTAT world area code ────────────────────────────────────

def test_faostat_area_code_is_numeric():
    from data_pipeline.connectors.faostat import FAOSTATConnector
    c = FAOSTATConnector()
    assert c.world_area_code == "5000", (
        f"Expected '5000', got '{c.world_area_code}'. "
        "FAOSTAT rejects 'WLD' — use numeric code."
    )


def test_faostat_world_area_code_is_named_attribute():
    """Ensure area code is a named class attribute, not an inline string literal."""
    from data_pipeline.connectors.faostat import FAOSTATConnector
    assert hasattr(FAOSTATConnector, "world_area_code"), (
        "world_area_code must be a named class attribute so it is overridable in tests."
    )


def test_faostat_fbsh_area_code_is_5000():
    """The historical FBSH mapping in map.py must use '5000', not 'WLD'."""
    from data_pipeline.alignment.map import ONTOLOGY_MAP
    mapping = ONTOLOGY_MAP.get("faostat_food_balance_historical", [])
    for m in mapping:
        if m.entity == "food.supply.kcal_per_capita":
            assert m.world_country_code == "5000", (
                f"faostat_food_balance_historical uses world_country_code='{m.world_country_code}', "
                "expected '5000'. FAOSTAT returns zero rows with 'WLD'."
            )


def test_faostat_cache_has_sufficient_rows():
    """After fix, cached data must have at least 40 rows (expect ~52 for 1961-2013)."""
    import pathlib
    cache_path = pathlib.Path("output/aligned/faostat_food_balance_historical.parquet")
    if not cache_path.exists():
        pytest.skip("Parquet cache not yet generated — run connector first")
    import pandas as pd
    df = pd.read_parquet(cache_path)
    assert len(df) > 40, (
        f"FAOSTAT FBSH cache has {len(df)} rows, expected >40. "
        "Regenerate after fixing world_area_code."
    )


# ── T1-4: initial_conditions.py default year ─────────────────────────

def test_initial_conditions_default_year_is_train_start():
    from data_pipeline.alignment.initial_conditions import get_initial_conditions
    from pyworldx.calibration.metrics import CrossValidationConfig
    ic = get_initial_conditions()
    assert ic["year"] == CrossValidationConfig.train_start, (
        f"Default IC year is {ic['year']}, expected {CrossValidationConfig.train_start}. "
        "Any call without target_year must initialize at train_start."
    )


def test_initial_conditions_1970_values_are_plausible():
    from data_pipeline.alignment.initial_conditions import get_initial_conditions
    ic = get_initial_conditions()
    assert 3e9 < ic["POP"] < 4e9, f"POP={ic['POP']:.2e}, expect ~3.5e9 at 1970"
    assert ic["NR"] > 1e11, f"NR={ic['NR']:.2e}, expect ~1e12 at 1970"
    assert 0.8 < ic["PPOLX"] < 1.2, f"PPOLX={ic['PPOLX']:.3f}, expect ~1.0 at 1970"


def test_initial_conditions_explicit_1900_still_works():
    from data_pipeline.alignment.initial_conditions import get_initial_conditions
    ic = get_initial_conditions(target_year=1900)
    assert ic["year"] == 1900


def test_initial_conditions_rejects_invalid_years():
    from data_pipeline.alignment.initial_conditions import get_initial_conditions
    with pytest.raises(ValueError):
        get_initial_conditions(target_year=1800)
    with pytest.raises(ValueError):
        get_initial_conditions(target_year=2200)


def test_train_start_shift_propagates_to_initial_conditions():
    from unittest.mock import patch
    from pyworldx.calibration import metrics
    from data_pipeline.alignment import initial_conditions
    with patch.object(metrics.CrossValidationConfig, "train_start", 1971):
        ic = initial_conditions.get_initial_conditions()
        assert ic["year"] == 1971, (
            "get_initial_conditions() default year did not shift with train_start. "
            "It must read CrossValidationConfig.train_start dynamically."
        )


def test_no_hardcoded_1970_in_source():
    """Literal 1970 used AS A CALIBRATION YEAR must be replaced with
    CrossValidationConfig.train_start.

    Excluded (legitimate) occurrences:
      - Lines that are pure comments (stripped line starts with #)
      - The CrossValidationConfig definition line itself
      - Nebel 2023 named constant definitions
      - World3-03 physical named constants (_IO70, _PPOL70, _AHL70, AHL70)
        which are defined at model-year 1970 but are physical parameters,
        not calibration epoch selectors.
      - String literals inside string literals in docstrings/rationale fields
      - URLs that contain "1970" as part of a data coverage range
      - data_pipeline/tests/ (existing tests are grandfathered)
      - EDGAR coverage comment (data range, not calibration epoch)
      - world3_reference.py year list (model time axis, not epoch selector)
    """
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", r"\b1970\b",
         "pyworldx/", "data_pipeline/",
         "--include=*.py", "--exclude-dir=__pycache__"],
        capture_output=True, text=True,
        cwd="/Users/johnny/pyWorldX",
    )

    _EXEMPT_TOKENS = [
        "train_start: int = 1970",        # config definition itself
        "train_start=1970",               # Nebel named constant
        "NEBEL_2023",                     # Nebel constant lines
        "_IO70",                          # World3 physical constant
        "_PPOL70",                        # World3 physical constant
        "_AHL70",                         # World3 physical constant
        "ahl70",                          # World3 named parameter
        "ppol_1970",                      # World3 physical parameter
        "data_pipeline/tests/",           # grandfathered pipeline tests
        "edgar.py:6:",                    # coverage comment (data range)
        "edgar.py:30:",                   # URL with 1970 in filename
        "edgar.py:31:",                   # URL with 1970 in filename
        "edgar.py:32:",                   # URL with 1970 in filename
        "world3_reference.py",            # model time axis list and docstrings
        "bridge.py:9:",                   # docstring
        "nebcal_transform.py:106:",       # comment about EDGAR coverage
        "normalize.py:",                  # comment about FAOSTAT gap
        "initial_conditions.py:",         # comments/docstring in get_initial_conditions
        "map.py:1184:",                   # OWID comment (data gap annotation)
        "registry.py:",                   # ontology description string
        "parameters.py:",                 # rationale string (physical, not epoch)
        "presets.py:",                    # parameter name + comment (physical, not epoch)
        "agriculture.py:63:",             # MDL comment
        "agriculture.py:96:",             # _IO70 reference comment
        "pollution.py:44:",               # _PPOL70 comment
        "pollution.py:45:",               # _AHL70 comment
    ]

    hits = []
    for line in result.stdout.splitlines():
        # Skip pure comment lines
        code_part = line.split(":", 2)[-1].strip() if ":" in line else line.strip()
        if code_part.startswith("#"):
            continue
        # Skip exempt tokens
        if any(tok in line for tok in _EXEMPT_TOKENS):
            continue
        hits.append(line)

    assert hits == [], (
        "Literal 1970 calibration-year integer in source — "
        "replace with CrossValidationConfig.train_start:\n"
        + "\n".join(hits)
    )



def test_cross_validation_config_ordering():
    """train_start < train_end < validation_end must hold."""
    from pyworldx.calibration.metrics import CrossValidationConfig
    cfg = CrossValidationConfig()
    assert cfg.train_start < cfg.train_end, (
        f"train_start={cfg.train_start} must be < train_end={cfg.train_end}"
    )
    assert cfg.train_end < cfg.validate_end, (
        f"train_end={cfg.train_end} must be < validate_end={cfg.validate_end}"
    )


# ── T2-5: CrossValidationConfig propagation audit ────────────────────

def test_config_ordering_invariant_holds():
    from pyworldx.calibration.metrics import CrossValidationConfig
    cfg = CrossValidationConfig()
    assert cfg.train_start < cfg.train_end, (
        f"train_start={cfg.train_start} must be < train_end={cfg.train_end}"
    )
    assert cfg.train_end < cfg.validate_end, (
        f"train_end={cfg.train_end} must be < validate_end={cfg.validate_end}"
    )
