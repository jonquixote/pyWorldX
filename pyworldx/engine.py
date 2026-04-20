"""pyworldx.engine — Engine factory for calibration.

Exposes ``build_sector_engine_factory`` which is the single entry-point
used by the empirical calibration CLI (empirical.py) and any other
caller that needs a::

    engine_factory: Callable[[dict[str, float]],
                              tuple[dict[str, np.ndarray], np.ndarray]]

The factory always runs the *full* six-sector World3 model because the
sectors are tightly coupled (population ↔ capital ↔ agriculture ↔
resources ↔ pollution ↔ welfare).  The ``sector`` argument passed to
``build_sector_engine_factory`` merely documents *which sector's*
parameters the caller intends to tune — it does not restrict the
simulation.

Parameter injection strategy
-----------------------------
Two classes of free parameters exist in ``parameters.py``:

1. **Constructor-settable** — mapped in ``_CONSTRUCTOR_PARAMS``.
   Applied once at sector instantiation via ``setattr``.

2. **Runtime levers** — mapped in ``_RUNTIME_PARAMS``.
   Injected into ``shared`` at every timestep via
   ``Engine(exogenous_injector=...)``.  The key written into ``shared``
   is the bare suffix after the dot (e.g. ``"population.len_scale"``
   → ``"len_scale"``), which is the key each sector reads from its
   ``inputs`` / ``shared`` dict.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from pyworldx.core.engine import Engine
from pyworldx.sectors.population import PopulationSector
from pyworldx.sectors.capital import CapitalSector
from pyworldx.sectors.agriculture import AgricultureSector
from pyworldx.sectors.resources import ResourcesSector
from pyworldx.sectors.pollution import PollutionSector
from pyworldx.sectors.welfare import WelfareSector

__all__ = ["build_sector_engine_factory"]

# ── Simulation constants (mirror run_world3.py) ──────────────────────────
_BASE_YEAR: float = 1900.0
_T_START: float = 0.0
_T_END: float = 200.0
_DT: float = 1.0

# ── Constructor-settable parameters ─────────────────────────────────────
# Maps canonical param name → (sector_name, attr_name).
# These are applied once via setattr() when the sector is instantiated.
_CONSTRUCTOR_PARAMS: dict[str, tuple[str, str]] = {
    "population.initial_population": ("population", "initial_population"),
    "capital.initial_ic":            ("capital",     "initial_ic"),
    "capital.icor":                  ("capital",     "icor"),
    "capital.alic":                  ("capital",     "alic"),
    "capital.alsc":                  ("capital",     "alsc"),
    "agriculture.initial_al":        ("agriculture", "initial_al"),
    "agriculture.initial_land_fertility": ("agriculture", "initial_land_fertility"),
    "agriculture.land_development_rate":  ("agriculture", "land_development_rate"),
    "agriculture.sfpc":              ("agriculture", "sfpc"),
    "resources.initial_nr":          ("resources",   "initial_nr"),
    "resources.policy_year":         ("resources",   "policy_year"),
    "pollution.initial_ppol":        ("pollution",   "initial_ppol"),
    "pollution.ahl70":               ("pollution",   "ahl70"),
    "pollution.pptd":                ("pollution",   "pptd"),
}

# ── Runtime lever parameters ─────────────────────────────────────────────
# Maps canonical param name → shared-state key.
# These are injected into Engine.shared at every timestep via
# exogenous_injector so that sector.compute() can read them from inputs.
_RUNTIME_PARAMS: dict[str, str] = {
    "population.len_scale":  "len_scale",
    "population.mtfn_scale": "mtfn_scale",
}

# All known sectors — used to validate the sector arg.
_KNOWN_SECTORS: frozenset[str] = frozenset({
    "population",
    "capital",
    "agriculture",
    "resources",
    "pollution",
    "welfare",
})


def _build_sectors(params: dict[str, float]) -> list[Any]:
    """Instantiate all six World3 sectors and apply constructor overrides."""
    sectors: list[Any] = [
        PopulationSector(),
        CapitalSector(),
        AgricultureSector(),
        ResourcesSector(),
        PollutionSector(),
        WelfareSector(),
    ]
    sector_map = {s.name: s for s in sectors}

    for param_name, value in params.items():
        mapping = _CONSTRUCTOR_PARAMS.get(param_name)
        if mapping is None:
            continue
        sector_name, attr_name = mapping
        sector = sector_map.get(sector_name)
        if sector is not None and hasattr(sector, attr_name):
            setattr(sector, attr_name, value)

    return sectors


def _make_exogenous_injector(
    params: dict[str, float],
) -> Callable[[float], dict[str, float]] | None:
    """Return an exogenous_injector for runtime lever params, or None."""
    levers: dict[str, float] = {}
    for param_name, shared_key in _RUNTIME_PARAMS.items():
        if param_name in params:
            levers[shared_key] = params[param_name]

    if not levers:
        return None

    # Capture levers in closure — constant across all timesteps.
    def _injector(_t: float) -> dict[str, float]:
        return levers

    return _injector


def build_sector_engine_factory(
    sector: str,
) -> Callable[
    [dict[str, float]],
    tuple[dict[str, np.ndarray], np.ndarray],
]:
    """Return a calibration-compatible engine factory scoped to *sector*.

    The returned callable has the signature expected by
    ``EmpiricalCalibrationRunner.run`` and ``DataBridge.build_objective``::

        engine_factory(params: dict[str, float])
            -> (trajectories: dict[str, np.ndarray],
                time_index:   np.ndarray)

    where ``time_index`` contains calendar years (1900 … 2100).

    Args:
        sector: Name of the sector whose parameters will be tuned
                (e.g. ``"population"``).  Must be one of the six
                canonical World3 sectors.  The full model is always
                simulated regardless of this value.

    Returns:
        A callable suitable for passing to the calibration pipeline.

    Raises:
        ValueError: If *sector* is not a recognised World3 sector name.
    """
    if sector not in _KNOWN_SECTORS:
        raise ValueError(
            f"Unknown sector {sector!r}. "
            f"Valid sectors: {sorted(_KNOWN_SECTORS)}"
        )

    def _factory(
        params: dict[str, float],
    ) -> tuple[dict[str, np.ndarray], np.ndarray]:
        sectors = _build_sectors(params)
        injector = _make_exogenous_injector(params)

        engine = Engine(
            sectors=sectors,
            master_dt=_DT,
            t_start=_T_START,
            t_end=_T_END,
            exogenous_injector=injector,
        )

        result = engine.run()

        time_index: np.ndarray = result.time_index + _BASE_YEAR
        trajectories: dict[str, np.ndarray] = result.trajectories

        return trajectories, time_index

    return _factory
