"""T0-1: Carbon cycle equilibrium gate.

Verifies that pre-industrial NPP equals plant respiration + litter flux at
C_land = 600 GtC. This must be true before any calibration run — if
(_K_RESP_PLANT + _K_LITTER) * C_LAND0 ≠ NPP0, the atmosphere gains or
loses carbon even with zero anthropogenic emissions, making all NRMSD
scores meaningless.
"""
from __future__ import annotations

from pyworldx.sectors.pollution_ghg import (
    _K_LITTER,
    _K_RESP_PLANT,
    _C_LAND0,
    _NPP0,
)


def test_carbon_equilibrium_constants_satisfy_npp_balance() -> None:
    """(_K_RESP_PLANT + _K_LITTER) × C_LAND0 must equal NPP0 within 0.5 GtC/yr."""
    flux = (_K_RESP_PLANT + _K_LITTER) * _C_LAND0
    assert abs(flux - _NPP0) < 0.5, (
        f"NPP balance violated: ({_K_RESP_PLANT} + {_K_LITTER}) × {_C_LAND0} "
        f"= {flux:.1f} GtC/yr ≠ NPP0={_NPP0} GtC/yr. "
        "Set _K_RESP_PLANT = _K_LITTER = 0.05."
    )


def test_k_resp_plant_is_correct() -> None:
    assert _K_RESP_PLANT == 0.05, (
        f"_K_RESP_PLANT={_K_RESP_PLANT}, expected 0.05. "
        "Previous value 0.03 caused unphysical pre-industrial carbon drawdown."
    )


def test_k_litter_is_correct() -> None:
    assert _K_LITTER == 0.05, (
        f"_K_LITTER={_K_LITTER}, expected 0.05. "
        "Previous value 0.035 caused unphysical pre-industrial carbon drawdown."
    )
