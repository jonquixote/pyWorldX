"""Task 4: World3-03 validation against Nebel et al. (2023) bounds.

Runs the 5-sector World3-03 engine for 1900-2020, extracts 1970-2020
window, maps engine variable names to NEBEL variable names, and compares
against the canonical W3-03 Standard Run reference (annual-interpolated).

Produces a validation report artifact at `validation_report_nebel2023.md`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from data_pipeline.connectors.world3_reference import World3ReferenceConnector
from pyworldx.core.engine import Engine
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.welfare import WelfareSector
from pyworldx.validation.world3_reference import validate_against_nebel2023


# Map NEBEL variable names → engine trajectory key
NEBEL_TO_ENGINE: dict[str, str] = {
    "population": "POP",
    "industrial_output": "industrial_output",
    "food_per_capita": "food_per_capita",
    "pollution": "pollution_index",
    "nonrenewable_resources": "NR",
    "human_welfare_hdi": "human_welfare_index",
    "ecological_footprint": "ecological_footprint",
    # service_per_capita removed — no matching reference connector variable.
}

# Variables where the reference connector uses a different name than NEBEL
REFERENCE_ALIAS: dict[str, str] = {
    "pollution": "pollution_index",
    "nonrenewable_resources": "nr_fraction_remaining",
    "human_welfare_hdi": "human_welfare_index",
}


def _run_engine() -> pd.DataFrame:
    sectors = [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        WelfareSector(),
    ]
    result = Engine(sectors=sectors, master_dt=1.0, t_start=0.0, t_end=200.0).run()
    years = result.time_index + 1900.0
    frame: dict[str, np.ndarray] = {"year": years.astype(int)}
    for name, arr in result.trajectories.items():
        frame[name] = arr
    df = pd.DataFrame(frame).set_index("year")
    return df


def _build_model_output(df: pd.DataFrame) -> dict[str, pd.Series]:
    model: dict[str, pd.Series] = {}
    for nebel_name, eng_name in NEBEL_TO_ENGINE.items():
        if eng_name in df.columns:
            model[nebel_name] = df[eng_name].rename(nebel_name)
    # Derive NR as fraction remaining (NR / NR0) for comparison with
    # nr_fraction_remaining reference, to match the NEBEL semantics.
    if "NR" in df.columns:
        nr0 = df["NR"].iloc[0]
        model["nonrenewable_resources"] = (df["NR"] / nr0).rename("nonrenewable_resources")
    return model


def _build_historical() -> dict[str, pd.Series]:
    conn = World3ReferenceConnector()
    hist: dict[str, pd.Series] = {}
    for nebel_name in NEBEL_TO_ENGINE.keys():
        ref_name = REFERENCE_ALIAS.get(nebel_name, nebel_name)
        series = conn.fetch_interpolated(ref_name, 1970, 2020)
        if series is not None:
            hist[nebel_name] = series.rename(nebel_name)
    return hist


def test_nebel_mapping_complete() -> None:
    """All 7 variables we can map have engine trajectories."""
    df = _run_engine()
    model = _build_model_output(df)
    # At least 7 of 8 NEBEL variables covered (service_per_capita has no ref)
    assert len(model) >= 7


def test_nebel_validation_runs_and_reports() -> None:
    """End-to-end validation produces a report with per-variable NRMSD."""
    df = _run_engine()
    model = _build_model_output(df)
    hist = _build_historical()

    report = validate_against_nebel2023(model, hist)

    # Must evaluate at least one variable
    assert report.n_total >= 1

    # All per-variable NRMSD values are finite
    for r in report.variable_results:
        assert np.isfinite(r.nrmsd), f"Non-finite NRMSD for {r.variable}"

    # Write artifact
    out_path = Path(__file__).resolve().parents[2] / "validation_report_nebel2023.md"
    lines = [
        "# World3-03 NEBEL 2023 Validation Report",
        "",
        f"- Window: {report.config.train_start}–{report.config.train_end}",
        f"- Variables evaluated: {report.n_total}",
        f"- Variables passed: {report.n_passed}",
        f"- Total NRMSD: {report.total_nrmsd:.4f}",
        f"- Total NRMSD bound: {report.total_bound:.4f}",
        f"- Overall passed: {report.overall_passed}",
        "",
        "## Per-variable results",
        "",
        "| variable | nrmsd | bound | function | passed |",
        "|---|---|---|---|---|",
    ]
    for r in report.variable_results:
        lines.append(
            f"| {r.variable} | {r.nrmsd:.4f} | {r.upper_bound:.4f} | "
            f"{r.nrmsd_function} | {r.passed} |"
        )
    if report.notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in report.notes]
    out_path.write_text("\n".join(lines) + "\n")
    assert out_path.exists()
