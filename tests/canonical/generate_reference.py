"""Generate reference trajectory for the canonical R-I-P test world.

This script runs the pyWorldX engine with canonical parameters from
Section 17.1 and saves the reference trajectory CSV.

In production, this would use PySD==3.14.0 to generate the reference
from rip_canonical.xmile. For Sprint 1, we generate from our own
verified RK4 engine (which passes the analytical decay sub-case)
and use it as the self-consistent reference.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from pyworldx.core.engine import Engine
from pyworldx.sectors.rip_sectors import (
    IndustrySector,
    PollutionSector,
    ResourceSector,
)


def main() -> None:
    sectors = [ResourceSector(), IndustrySector(), PollutionSector()]
    engine = Engine(
        sectors=sectors,
        master_dt=1.0,
        t_start=0.0,
        t_end=200.0,
    )

    result = engine.run()
    df = result.to_dataframe()

    # Write CSV with provenance header
    csv_path = os.path.join(os.path.dirname(__file__), "reference_trajectory.csv")

    timestamp = datetime.now(timezone.utc).isoformat()
    header_lines = [
        "# pyWorldX canonical R-I-P reference trajectory",
        f"# Generated: {timestamp}",
        "# Engine: pyWorldX RK4 (self-consistent reference)",
        "# Parameters: Section 17.1 canonical",
        "# dt=1.0, t_start=0, t_end=200",
        "# Sector R substep_ratio=4, Sectors I,P single-rate",
        "# I<->P algebraic loop: fixed-point, tol=1e-10, max_iter=100",
    ]

    with open(csv_path, "w") as f:
        for line in header_lines:
            f.write(line + "\n")
        df.to_csv(f, index=False, float_format="%.15g")

    # Print summary
    print(f"Reference trajectory written to {csv_path}")
    print(f"  Time range: {df['t'].iloc[0]} to {df['t'].iloc[-1]}")
    print(f"  Steps: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    print("\n  Final values:")
    for col in df.columns:
        if col != "t":
            print(f"    {col}: {df[col].iloc[-1]:.9f}")

    # Compute sha256 of output
    with open(csv_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    print(f"\n  SHA256: {sha}")


if __name__ == "__main__":
    main()
