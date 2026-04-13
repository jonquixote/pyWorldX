#!/usr/bin/env python3
"""pyWorldX — World3-03 simulation runner and scenario comparison.

Run the canonical Standard Run, Nebel 2024 recalibration, and policy scenarios.
Produces matplotlib figures and a text summary of key indicators.

Usage:
    python run_world3.py              # full run with plots
    python run_world3.py --no-plots   # text-only output
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pyworldx.core.engine import Engine
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.welfare import WelfareSector
from pyworldx.presets import WORLD3_03, NEBEL_2024, ModelPreset


# ── Constants ────────────────────────────────────────────────────────────

BASE_YEAR = 1900
T_START = 0.0
T_END = 200.0
DT = 1.0

# Sector parameter attr names keyed by registry parameter name
_PARAM_TO_SECTOR: dict[str, tuple[str, str]] = {
    "population.initial_population": ("population", "initial_population"),
    "capital.initial_ic": ("capital", "initial_ic"),
    "capital.icor": ("capital", "icor"),
    "capital.alic": ("capital", "alic"),
    "capital.alsc": ("capital", "alsc"),
    "agriculture.initial_land_fertility": ("agriculture", "initial_land_fertility"),
    "agriculture.sfpc": ("agriculture", "sfpc"),
    "pollution.ahl70": ("pollution", "ahl70"),
    "pollution.pptd": ("pollution", "pptd"),
    "resources.initial_nr": ("resources", "initial_nr"),
    "resources.policy_year": ("resources", "policy_year"),
    "pollution.initial_ppol": ("pollution", "initial_ppol"),
}


# ── Engine builder ───────────────────────────────────────────────────────

def _build_sectors() -> list[Any]:
    """Create the 6 World3-03 sectors."""
    return [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        WelfareSector(),
    ]


def _apply_overrides(sectors: list[Any], overrides: dict[str, float]) -> None:
    """Apply parameter overrides to sector instances."""
    sector_map = {s.name: s for s in sectors}
    for param_name, value in overrides.items():
        mapping = _PARAM_TO_SECTOR.get(param_name)
        if mapping is None:
            continue
        sector_name, attr_name = mapping
        sector = sector_map.get(sector_name)
        if sector is not None and hasattr(sector, attr_name):
            setattr(sector, attr_name, value)


def run_preset(
    preset: ModelPreset,
    t_end: float = T_END,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Run a simulation with the given preset and return (years, trajectories)."""
    sectors = _build_sectors()
    if preset.parameter_overrides:
        _apply_overrides(sectors, preset.parameter_overrides)

    engine = Engine(
        sectors=sectors,
        master_dt=DT,
        t_start=T_START,
        t_end=t_end,
    )
    result = engine.run()
    years = result.time_index + BASE_YEAR
    return years, result.trajectories


def run_scenario(
    name: str,
    overrides: dict[str, float],
    base_preset: ModelPreset = WORLD3_03,
    t_end: float = T_END,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Run a scenario with merged overrides on top of a preset."""
    merged = dict(base_preset.parameter_overrides)
    merged.update(overrides)

    sectors = _build_sectors()
    _apply_overrides(sectors, merged)

    engine = Engine(
        sectors=sectors,
        master_dt=DT,
        t_start=T_START,
        t_end=t_end,
    )
    result = engine.run()
    years = result.time_index + BASE_YEAR
    return years, result.trajectories


# ── Text output ──────────────────────────────────────────────────────────

def _val_at_year(years: np.ndarray, traj: np.ndarray, year: float) -> float:
    return float(np.interp(year, years, traj))


def _peak_info(years: np.ndarray, traj: np.ndarray) -> tuple[float, float]:
    idx = np.argmax(traj)
    return float(years[idx]), float(traj[idx])


def print_summary(
    label: str,
    years: np.ndarray,
    trajs: dict[str, np.ndarray],
) -> None:
    """Print a formatted summary of key indicators."""
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}")

    pop = trajs.get("POP", np.zeros(1))
    io = trajs.get("industrial_output", np.zeros(1))
    nr = trajs.get("NR", np.zeros(1))
    ppol = trajs.get("PPOL", np.zeros(1))
    fpc = trajs.get("food_per_capita", np.zeros(1))
    le = trajs.get("life_expectancy")
    hwi = trajs.get("human_welfare_index")
    trajs.get("ecological_footprint")

    milestones = [1900, 1970, 2000, 2025, 2050, 2075, 2100]
    print(f"\n  {'Year':>6}  {'Pop (B)':>9}  {'IO (T$)':>9}  {'NR (%)':>8}  "
          f"{'Pollution':>10}  {'FPC':>7}  {'LE':>5}")
    print(f"  {'-' * 6}  {'-' * 9}  {'-' * 9}  {'-' * 8}  {'-' * 10}  {'-' * 7}  {'-' * 5}")

    for yr in milestones:
        if yr < years[0] or yr > years[-1]:
            continue
        p = _val_at_year(years, pop, yr) / 1e9
        i = _val_at_year(years, io, yr) / 1e12
        n = _val_at_year(years, nr, yr) / _val_at_year(years, nr, years[0]) * 100
        pp = _val_at_year(years, ppol, yr)
        f = _val_at_year(years, fpc, yr)
        l_str = ""
        if le is not None:
            l_str = f"{_val_at_year(years, le, yr):5.1f}"
        print(f"  {yr:>6}  {p:>9.2f}  {i:>9.3f}  {n:>7.1f}%  "
              f"{pp:>10.1f}  {f:>7.1f}  {l_str:>5}")

    # Peak values
    print(f"\n  Peak population:       {_peak_info(years, pop)[1] / 1e9:.2f} B "
          f"in {_peak_info(years, pop)[0]:.0f}")
    print(f"  Peak industrial output:{_peak_info(years, io)[1] / 1e12:.3f} T$ "
          f"in {_peak_info(years, io)[0]:.0f}")
    pp_peak_yr, pp_peak_val = _peak_info(years, ppol)
    print(f"  Peak pollution:        {pp_peak_val:.1f} "
          f"in {pp_peak_yr:.0f}")

    # Resource depletion
    nr_final = _val_at_year(years, nr, years[-1])
    nr_initial = _val_at_year(years, nr, years[0])
    print(f"  Resources remaining:   {nr_final / nr_initial * 100:.1f}% "
          f"by {years[-1]:.0f}")

    if hwi is not None:
        hwi_peak_yr, hwi_peak_val = _peak_info(years, hwi)
        print(f"  Peak welfare (HWI):    {hwi_peak_val:.3f} "
              f"in {hwi_peak_yr:.0f}")

    print()


def print_comparison(
    labels: list[str],
    runs: list[tuple[np.ndarray, dict[str, np.ndarray]]],
) -> None:
    """Print side-by-side comparison of key milestones."""
    print(f"\n{'=' * 70}")
    print("  COMPARISON — Key Indicators at 2050")
    print(f"{'=' * 70}\n")

    header = f"  {'Metric':<25}"
    for label in labels:
        header += f"  {label:>14}"
    print(header)
    print(f"  {'-' * 25}" + f"  {'-' * 14}" * len(labels))

    metrics = [
        ("Population (B)", "POP", 1e9, 1),
        ("Industrial Output (T$)", "industrial_output", 1e12, 3),
        ("Food per Capita", "food_per_capita", 1.0, 1),
        ("Resources Remaining %", "NR", None, 1),  # special handling
        ("Pollution Index", "PPOL", 1.0, 1),
        ("Life Expectancy", "life_expectancy", 1.0, 1),
        ("Welfare (HWI)", "human_welfare_index", 1.0, 3),
        ("Ecological Footprint", "ecological_footprint", 1.0, 2),
    ]

    for name, key, scale, decimals in metrics:
        row = f"  {name:<25}"
        for years, trajs in runs:
            traj = trajs.get(key)
            if traj is None:
                row += f"  {'N/A':>14}"
                continue
            val = _val_at_year(years, traj, 2050)
            if key == "NR":
                nr0 = _val_at_year(years, traj, years[0])
                pct = val / nr0 * 100 if nr0 > 0 else 0
                row += f"  {pct:>13.1f}%"
            else:
                row += f"  {val / scale:>14.{decimals}f}"
        print(row)

    # Peak year comparison
    print(f"\n  {'Peak Year':<25}", end="")
    for label in labels:
        print(f"  {label:>14}", end="")
    print()
    print(f"  {'-' * 25}" + f"  {'-' * 14}" * len(labels))

    for name, key in [
        ("Population", "POP"),
        ("Industrial Output", "industrial_output"),
        ("Pollution", "PPOL"),
    ]:
        row = f"  {name:<25}"
        for years, trajs in runs:
            traj = trajs.get(key)
            if traj is None:
                row += f"  {'N/A':>14}"
            else:
                peak_yr = years[np.argmax(traj)]
                row += f"  {peak_yr:>14.0f}"
        print(row)
    print()


# ── Plotting ─────────────────────────────────────────────────────────────

def _ensure_output_dir() -> Path:
    out = Path("output")
    out.mkdir(exist_ok=True)
    return out


def plot_standard_run(
    years: np.ndarray,
    trajs: dict[str, np.ndarray],
    title: str = "World3-03 Standard Run",
    filename: str = "standard_run.png",
) -> None:
    """Plot the classic 5-variable Limits to Growth chart."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 8))

    pop = trajs["POP"] / 1e9
    io = trajs["industrial_output"]
    io_norm = io / np.max(io) * np.max(pop) * 0.8
    nr = trajs["NR"]
    nr_norm = nr / nr[0] * np.max(pop) * 0.9
    ppol = trajs["PPOL"]
    ppol_norm = ppol / np.max(ppol) * np.max(pop) * 0.7
    fpc = _smooth_series(trajs["food_per_capita"], 7)
    fpc_norm = fpc / np.max(fpc) * np.max(pop) * 0.6

    ax.plot(years, pop, color="#2196F3", linewidth=2.5, label="Population")
    ax.plot(years, io_norm, color="#FF9800", linewidth=2.5, label="Industrial Output")
    ax.plot(years, nr_norm, color="#4CAF50", linewidth=2.5, label="Resources")
    ax.plot(years, ppol_norm, color="#F44336", linewidth=2.5, label="Pollution")
    ax.plot(years, fpc_norm, color="#9C27B0", linewidth=2.5, label="Food per Capita")

    ax.set_xlim(1900, 2100)
    ax.set_xlabel("Year", fontsize=13)
    ax.set_ylabel("Relative Scale (Population in Billions)", fontsize=13)
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.legend(loc="upper left", fontsize=11, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.axvline(x=2025, color="gray", linestyle="--", alpha=0.5, label="_nolegend_")
    ax.text(2027, ax.get_ylim()[1] * 0.95, "Today", fontsize=9, color="gray")

    fig.tight_layout()
    out = _ensure_output_dir()
    fig.savefig(out / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out / filename}")


def _smooth_series(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Moving average smoothing for plot lines."""
    if len(values) < window:
        return values
    kernel = np.ones(window) / window
    smoothed = np.convolve(values, kernel, mode="same")
    # Preserve endpoints
    half = window // 2
    smoothed[:half] = values[:half]
    smoothed[-half:] = values[-half:]
    return smoothed


def plot_comparison(
    labels: list[str],
    runs: list[tuple[np.ndarray, dict[str, np.ndarray]]],
    filename: str = "preset_comparison.png",
) -> None:
    """Plot side-by-side comparison of presets across key variables."""
    import matplotlib.pyplot as plt

    # Variables that benefit from plot-level smoothing
    smooth_keys = {"food_per_capita", "life_expectancy"}

    variables = [
        ("Population", "POP", 1e9, "Billions"),
        ("Industrial Output", "industrial_output", 1e12, "Trillions $/yr"),
        ("Food per Capita", "food_per_capita", 1.0, "veg equiv kg/yr"),
        ("Resources (NR)", "NR", 1e12, "Trillion resource units"),
        ("Persistent Pollution", "PPOL", 1.0, "Pollution units"),
        ("Life Expectancy", "life_expectancy", 1.0, "Years"),
    ]

    colors = ["#2196F3", "#FF5722", "#4CAF50", "#9C27B0", "#FF9800"]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for idx, (name, key, scale, unit) in enumerate(variables):
        ax = axes[idx]
        for i, (label, (years, trajs)) in enumerate(zip(labels, runs)):
            traj = trajs.get(key)
            if traj is not None:
                plotdata = _smooth_series(traj, 7) if key in smooth_keys else traj
                ax.plot(years, plotdata / scale, color=colors[i % len(colors)],
                        linewidth=2, label=label)

        ax.set_title(name, fontsize=12, fontweight="bold")
        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel(unit, fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(1900, 2100)
        ax.axvline(x=2025, color="gray", linestyle="--", alpha=0.3)

    fig.suptitle("pyWorldX — Cross-Preset Trajectory Comparison",
                 fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = _ensure_output_dir()
    fig.savefig(out / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out / filename}")


def plot_scenarios(
    labels: list[str],
    runs: list[tuple[np.ndarray, dict[str, np.ndarray]]],
    filename: str = "scenarios.png",
) -> None:
    """Plot scenario comparison focused on the most divergent variables."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    variables = [
        ("Population", "POP", 1e9, "Billions"),
        ("Industrial Output", "industrial_output", 1e12, "Trillions $/yr"),
        ("Resources (NR)", "NR", 1e12, "Trillion resource units"),
        ("Persistent Pollution", "PPOL", 1.0, "Pollution units"),
    ]

    colors = ["#2196F3", "#4CAF50", "#FF5722", "#9C27B0", "#FF9800", "#795548"]

    for idx, (name, key, scale, unit) in enumerate(variables):
        ax = axes[idx]
        for i, (label, (years, trajs)) in enumerate(zip(labels, runs)):
            traj = trajs.get(key)
            if traj is not None:
                lw = 2.5 if i == 0 else 1.8
                ls = "-" if i == 0 else "--"
                ax.plot(years, traj / scale, color=colors[i % len(colors)],
                        linewidth=lw, linestyle=ls, label=label)

        ax.set_title(name, fontsize=12, fontweight="bold")
        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel(unit, fontsize=10)
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(1900, 2100)
        ax.axvline(x=2025, color="gray", linestyle="--", alpha=0.3)

    fig.suptitle("pyWorldX — Policy Scenario Comparison",
                 fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = _ensure_output_dir()
    fig.savefig(out / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out / filename}")


def plot_welfare_dashboard(
    labels: list[str],
    runs: list[tuple[np.ndarray, dict[str, np.ndarray]]],
    filename: str = "welfare_dashboard.png",
) -> None:
    """Plot welfare-focused indicators: HWI, LE, EF."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    colors = ["#2196F3", "#FF5722", "#4CAF50", "#9C27B0"]

    panels = [
        ("Human Welfare Index", "human_welfare_index", 1.0),
        ("Life Expectancy", "life_expectancy", 1.0),
        ("Ecological Footprint", "ecological_footprint", 1.0),
    ]

    for idx, (name, key, scale) in enumerate(panels):
        ax = axes[idx]
        for i, (label, (years, trajs)) in enumerate(zip(labels, runs)):
            traj = trajs.get(key)
            if traj is not None:
                ax.plot(years, traj / scale, color=colors[i % len(colors)],
                        linewidth=2, label=label)
        ax.set_title(name, fontsize=12, fontweight="bold")
        ax.set_xlabel("Year", fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(1900, 2100)
        ax.axvline(x=2025, color="gray", linestyle="--", alpha=0.3)

    fig.suptitle("pyWorldX — Welfare Indicators",
                 fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = _ensure_output_dir()
    fig.savefig(out / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out / filename}")


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="pyWorldX — World3-03 Simulation Runner"
    )
    parser.add_argument(
        "--no-plots", action="store_true",
        help="Text output only (skip matplotlib plots)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  pyWorldX — Limits to Growth World3-03 Simulation Engine")
    print("=" * 70)

    # ── 1. W3-03 Standard Run ────────────────────────────────────────
    print("\n[1/4] Running World3-03 Standard Run (1900-2100)...")
    w3_years, w3_trajs = run_preset(WORLD3_03)
    print_summary("World3-03 Standard Run (Meadows et al. 2004)", w3_years, w3_trajs)

    # ── 2. Nebel 2024 Recalibration ──────────────────────────────────
    print("[2/4] Running Nebel 2024 Recalibration (1900-2100)...")
    nebel_years, nebel_trajs = run_preset(NEBEL_2024)
    print_summary("Nebel 2024 Recalibration (DOI: 10.1111/jiec.13442)", nebel_years, nebel_trajs)

    # ── 3. Policy Scenarios ──────────────────────────────────────────
    print("[3/4] Running policy scenarios...")

    scenarios: list[tuple[str, dict[str, float]]] = [
        (
            "Pollution Control",
            {"pollution.pptd": 10.0, "pollution.ahl70": 0.8},
        ),
        (
            "Resource Discovery (2x)",
            {"resources.initial_nr": 2.0e12},
        ),
        (
            "Agricultural Investment",
            {"agriculture.initial_land_fertility": 900.0, "agriculture.sfpc": 280.0},
        ),
        (
            "Capital Longevity",
            {"capital.alic": 28.0, "capital.alsc": 35.0},
        ),
    ]

    scenario_runs: list[tuple[str, tuple[np.ndarray, dict[str, np.ndarray]]]] = [
        ("Standard Run", (w3_years, w3_trajs)),
    ]

    for scenario_name, overrides in scenarios:
        print(f"  - {scenario_name}...")
        s_years, s_trajs = run_scenario(scenario_name, overrides)
        scenario_runs.append((scenario_name, (s_years, s_trajs)))
        print_summary(f"Scenario: {scenario_name}", s_years, s_trajs)

    # ── 4. Comparisons ───────────────────────────────────────────────
    print("[4/4] Generating comparisons...")

    preset_labels = ["W3-03 Standard", "Nebel 2024"]
    preset_runs = [(w3_years, w3_trajs), (nebel_years, nebel_trajs)]
    print_comparison(preset_labels, preset_runs)

    scenario_labels = [name for name, _ in scenario_runs]
    scenario_data = [data for _, data in scenario_runs]
    print_comparison(scenario_labels, scenario_data)

    # ── 5. Export to CSV ─────────────────────────────────────────────
    out_dir = _ensure_output_dir()
    for label, (yrs, trs) in [("w3_03", (w3_years, w3_trajs)),
                               ("nebel_2024", (nebel_years, nebel_trajs))]:
        df = pd.DataFrame({"year": yrs})
        for key in ["POP", "industrial_output", "food_per_capita",
                     "NR", "PPOL", "life_expectancy",
                     "human_welfare_index", "ecological_footprint"]:
            if key in trs:
                df[key] = trs[key]
        csv_path = out_dir / f"{label}_trajectories.csv"
        df.to_csv(csv_path, index=False)
        print(f"  Exported: {csv_path}")

    # ── 6. Plots ─────────────────────────────────────────────────────
    if not args.no_plots:
        try:
            print("\nGenerating plots...")
            plot_standard_run(w3_years, w3_trajs)
            plot_standard_run(
                nebel_years, nebel_trajs,
                title="Nebel 2024 Recalibration",
                filename="nebel_2024.png",
            )
            plot_comparison(preset_labels, preset_runs)
            plot_scenarios(scenario_labels, scenario_data)
            plot_welfare_dashboard(
                preset_labels + [s[0] for s in scenario_runs[1:]],
                preset_runs + [s[1] for s in scenario_runs[1:]],
            )
            print(f"\nAll plots saved to {out_dir}/")
        except ImportError:
            print("\n  matplotlib not available — skipping plots.")
            print("  Install with: pip install matplotlib")

    print("\n" + "=" * 70)
    print("  Simulation complete.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
