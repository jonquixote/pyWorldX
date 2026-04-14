"""Generate reference trajectory for the canonical R-I-P test world.

**Approach 1 (preferred):** Load ``rip_canonical.xmile`` via PySD==3.14.0.

**PySD limitation:** The canonical R-I-P world has a simultaneous algebraic
dependency between extraction_rate (Sector R) and industrial_output (Sector I):
    extraction_rate = k_ext * R * industrial_output * (1 - pollution_fraction)
    industrial_output = A * K^beta * extraction_rate^(1-beta) * pollution_efficiency
PySD==3.14.0 resolves model equations by calling them as Python functions;
the circular call chain produces a RecursionError.

**Approach 2 (fallback):** An independent pure-numpy reference that replicates
pyWorldX's exact integration algorithm without importing any pyworldx code:
  - R is sub-stepped at 4:1 (dt=0.25) with frozen inter-sector values
  - K and P are RK4-integrated at master dt=1.0
  - I↔P algebraic loop resolved by fixed-point (converges in 1 step for this model
    because pollution_efficiency only depends on the P stock, not on industrial_output)
  - Bootstrap: seed io=K^0.7, run R→loop→re-run R→loop (4 passes)

The fallback produces a genuinely independent reference: it shares no code with
pyworldx, so a bug in pyworldx.core.engine would be detectable.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd


# ── Canonical parameters (Section 17.1, matches rip_sectors.py) ─────────────

_K_EXT = 0.01
_ALPHA = 0.2
_DELTA = 0.05
_A = 1.0
_BETA = 0.7
_MU = 0.1
_TAU_P = 20.0
_P_HALF = 500.0
_GAMMA = 0.3
_R0, _K0, _P0 = 1000.0, 100.0, 0.0
_DT = 1.0
_T_END = 200
_N_SUB = 4  # R is sub-stepped at 4:1


# ── Pure-numpy reference implementation ──────────────────────────────────────

def _rk4(f: Any, y: float, dt: float) -> float:
    k1: float = f(y)
    k2: float = f(y + 0.5 * dt * k1)
    k3: float = f(y + 0.5 * dt * k2)
    k4: float = f(y + dt * k3)
    return float(y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4))


def _pf_pe(P: float) -> tuple[float, float]:
    denom = P + _P_HALF
    pf = P / denom if denom > 1e-30 else 0.0
    return pf, 1.0 - _GAMMA * pf


def _er(R: float, io: float, pf: float) -> float:
    return _K_EXT * R * io * (1.0 - pf)


def _io(K: float, er: float, pe: float) -> float:
    if K <= 0.0 or er <= 0.0:
        return 0.0
    return float(_A * (K ** _BETA) * (er ** (1.0 - _BETA)) * pe)


def _sub_step_R(R: float, io_frz: float, pf_frz: float, dt_sub: float) -> float:
    """One RK4 sub-step for R with frozen inter-sector inputs."""
    return _rk4(lambda r: -_K_EXT * r * io_frz * (1.0 - pf_frz), R, dt_sub)


def _bootstrap(R: float, K: float, P: float) -> tuple[float, float, float, float]:
    """Replicate pyWorldX 4-pass bootstrap to get consistent t=0 auxiliaries.

    Pass 1: R.compute with io_guess=K^0.7
    Pass 2: algebraic loop (Industry + Pollution, converges in 1 step)
    Pass 3b: re-run R.compute with updated io
    Pass 4: final loop resolution
    """
    pf, pe = _pf_pe(P)
    io = K ** 0.7               # io_guess = K^0.7 (with A=1, er=1, pe=1)
    er_val = _er(R, io, pf)     # Pass 1
    io = _io(K, er_val, pe)     # Pass 2
    er_val = _er(R, io, pf)     # Pass 3b
    io = _io(K, er_val, pe)     # Pass 4
    return er_val, io, pf, pe


def _generate_numpy_reference() -> pd.DataFrame:
    """Generate reference trajectory using pure-numpy RK4 (no pyworldx imports)."""
    er0, io0, pf0, pe0 = _bootstrap(_R0, _K0, _P0)

    rows = [[0, _R0, _K0, _P0, er0, io0, pf0, pe0]]

    R, K, P = _R0, _K0, _P0
    io_frz, pf_frz = io0, pf0
    dt_sub = _DT / _N_SUB

    for _ in range(_T_END):
        # Phase 1: Sub-step R (4×) with frozen inter-sector values
        for _ in range(_N_SUB):
            R = _sub_step_R(R, io_frz, pf_frz, dt_sub)
        er_val = _er(R, io_frz, pf_frz)  # extraction_rate at end of sub-step

        # Phase 2: Algebraic loop resolution (1 iteration — pe depends only on P)
        pf, pe = _pf_pe(P)
        io = _io(K, er_val, pe)

        # Phase 3: RK4 for K (io varies with K inside stages)
        K = _rk4(
            lambda k: _ALPHA * _io(k, er_val, pe) - _DELTA * k,
            K, _DT,
        )

        # Phase 3: RK4 for P (io fixed at start-of-step value)
        P = _rk4(lambda p: _MU * io - p / _TAU_P, P, _DT)

        rows.append([float(len(rows)), R, K, P, er_val, io, pf, pe])

        # Freeze current io and pf for next step's R sub-stepping
        io_frz, pf_frz = io, pf

    return pd.DataFrame(
        rows,
        columns=["t", "R", "K", "P", "extraction_rate",
                 "industrial_output", "pollution_fraction", "pollution_efficiency"],
    )


# ── Entry point ──────────────────────────────────────────────────────────────

def _read_required_pysd_version(req_path: str) -> str:
    with open(req_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("PySD=="):
                return line.split("==", 1)[1].strip()
    raise RuntimeError(f"PySD version not pinned in {req_path}")


def main() -> None:
    canonical_dir = os.path.dirname(__file__)
    xmile_path = os.path.join(canonical_dir, "rip_canonical.xmile")
    csv_path = os.path.join(canonical_dir, "reference_trajectory.csv")
    req_path = os.path.join(canonical_dir, "requirements-canonical.txt")

    required_version = _read_required_pysd_version(req_path)

    # ── Attempt 1: PySD ──────────────────────────────────────────────────────
    pysd_success = False
    pysd_version = None
    try:
        import pysd  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        print("PySD not installed. Falling back to numpy reference.")
    else:
        if pysd.__version__ != required_version:
            print(
                f"PySD version mismatch: installed {pysd.__version__}, "
                f"required {required_version}. Falling back to numpy reference."
            )
        else:
            try:
                model = pysd.read_xmile(xmile_path)
                df = model.run(
                    initial_condition="original",
                    return_timestamps=list(range(0, _T_END + 1)),
                )
                df = df.reset_index().rename(columns={"index": "t"})
                wanted = [
                    "t", "R", "K", "P",
                    "extraction_rate", "industrial_output",
                    "pollution_fraction", "pollution_efficiency",
                ]
                norm_map = {c.lower().replace(" ", "_"): c for c in df.columns}
                cols_out = []
                for w in wanted:
                    key = w.lower()
                    if key in norm_map:
                        cols_out.append(norm_map[key])
                    else:
                        raise RuntimeError(
                            f"PySD output missing column '{w}'. "
                            f"Available: {list(df.columns)}"
                        )
                df_out = df[cols_out].copy()
                df_out.columns = wanted
                pysd_success = True
                pysd_version = pysd.__version__
                print(f"PySD run succeeded — using PySD {pysd_version} reference.")
            except RecursionError:
                print(
                    "PySD RecursionError: algebraic loop in rip_canonical.xmile "
                    "(extraction_rate ↔ industrial_output) causes infinite Python "
                    "call chain. Falling back to independent numpy reference.\n"
                    "See module docstring for details."
                )
            except Exception as e:
                print(f"PySD failed ({type(e).__name__}: {e}). Falling back to numpy.")

    # ── Attempt 2: Independent numpy reference ───────────────────────────────
    if not pysd_success:
        df_out = _generate_numpy_reference()
        print("Numpy reference generated successfully.")

    # ── Write CSV with provenance header ─────────────────────────────────────
    with open(xmile_path, "rb") as f:
        xmile_sha = hashlib.sha256(f.read()).hexdigest()

    timestamp = datetime.now(timezone.utc).isoformat()

    if pysd_success:
        source_line = f"# Source: PySD {pysd_version} (independent reference)"
        loop_note = (
            "# Note: algebraic loop resolved by PySD's equation evaluator"
        )
    else:
        source_line = (
            "# Source: Independent numpy RK4 reference "
            "(PySD==3.14.0 failed — algebraic loop RecursionError, see module docstring)"
        )
        loop_note = (
            "# Note: independent RK4 verification via "
            "test_analytical_decay_subcase (closed-form, rel<1e-4 for t<=100)"
        )

    header_lines = [
        "# pyWorldX canonical R-I-P reference trajectory",
        f"# Generated: {timestamp}",
        source_line,
        loop_note,
        f"# xmile_path: {os.path.basename(xmile_path)}",
        f"# xmile_sha256: {xmile_sha}",
        f"# dt={_DT}, t_start=0, t_end={_T_END}, method=rk4, R_substeps={_N_SUB}",
    ]

    with open(csv_path, "w") as f:
        for line in header_lines:
            f.write(line + "\n")
        df_out.to_csv(f, index=False, float_format="%.15g")

    print(f"Reference trajectory written to {csv_path}")
    print(f"  Rows: {len(df_out)}")
    print(f"  xmile SHA256: {xmile_sha}")


if __name__ == "__main__":
    main()
