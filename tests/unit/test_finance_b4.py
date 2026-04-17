"""Task B4: finance.py must aggregate ALL TNDS sources (tnds_aes, education_tnds, damages_tnds)."""
from __future__ import annotations

from pyworldx.sectors.finance import FinanceSector
from pyworldx.core.quantities import Quantity
from tests._phase2_helpers import make_ctx, base_shared


def _stocks() -> dict:
    return {
        "L": Quantity(1e11, "capital_units"),
        "D_g": Quantity(0.0, "capital_units"),
        "D_s": Quantity(0.0, "capital_units"),
        "D_p": Quantity(0.0, "capital_units"),
    }


def test_tnds_sources_in_declares_reads() -> None:
    """finance.py must declare reads for all three TNDS sources."""
    fs = FinanceSector()
    reads = fs.declares_reads()
    assert "education_tnds" in reads, f"education_tnds not in declares_reads: {reads}"
    assert "damages_tnds" in reads, f"damages_tnds not in declares_reads: {reads}"
    assert "tnds_aes" in reads, f"tnds_aes not in declares_reads: {reads}"


def test_education_tnds_reduces_dL() -> None:
    """Adding education_tnds must decrease dL compared to zero."""
    ctx = make_ctx()
    fs = FinanceSector()

    shared_no_edu = base_shared()
    shared_no_edu["education_tnds"] = Quantity(0.0, "capital_units")
    shared_no_edu["damages_tnds"] = Quantity(0.0, "capital_units")

    shared_with_edu = base_shared()
    shared_with_edu["education_tnds"] = Quantity(5e9, "capital_units")
    shared_with_edu["damages_tnds"] = Quantity(0.0, "capital_units")

    r_no = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_no_edu, ctx=ctx)
    r_with = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_with_edu, ctx=ctx)

    assert r_with["d_L"].magnitude < r_no["d_L"].magnitude, (
        f"education_tnds must reduce dL: no_edu={r_no['d_L'].magnitude:.4g} "
        f"with_edu={r_with['d_L'].magnitude:.4g}"
    )


def test_damages_tnds_reduces_dL() -> None:
    """Adding damages_tnds must decrease dL compared to zero."""
    ctx = make_ctx()
    fs = FinanceSector()

    shared_no = base_shared()
    shared_no["education_tnds"] = Quantity(0.0, "capital_units")
    shared_no["damages_tnds"] = Quantity(0.0, "capital_units")

    shared_with = base_shared()
    shared_with["education_tnds"] = Quantity(0.0, "capital_units")
    shared_with["damages_tnds"] = Quantity(3e9, "capital_units")

    r_no = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_no, ctx=ctx)
    r_with = fs.compute(t=50.0, stocks=_stocks(), inputs=shared_with, ctx=ctx)

    assert r_with["d_L"].magnitude < r_no["d_L"].magnitude, (
        f"damages_tnds must reduce dL: no_dmg={r_no['d_L'].magnitude:.4g} "
        f"with_dmg={r_with['d_L'].magnitude:.4g}"
    )


def test_all_tnds_additive() -> None:
    """Total TNDS reduction = sum of individual reductions (linearity)."""
    ctx = make_ctx()
    fs = FinanceSector()

    base = base_shared()
    base["education_tnds"] = Quantity(0.0, "capital_units")
    base["damages_tnds"] = Quantity(0.0, "capital_units")
    base["tnds_aes"] = Quantity(0.0, "capital_units")

    combined = base_shared()
    combined["education_tnds"] = Quantity(2e9, "capital_units")
    combined["damages_tnds"] = Quantity(3e9, "capital_units")
    combined["tnds_aes"] = Quantity(1e9, "capital_units")

    r_base = fs.compute(t=50.0, stocks=_stocks(), inputs=base, ctx=ctx)
    r_combined = fs.compute(t=50.0, stocks=_stocks(), inputs=combined, ctx=ctx)

    expected_reduction = 2e9 + 3e9 + 1e9
    actual_reduction = r_base["d_L"].magnitude - r_combined["d_L"].magnitude
    assert abs(actual_reduction - expected_reduction) < expected_reduction * 0.01, (
        f"TNDS reduction {actual_reduction:.4g} ≠ expected {expected_reduction:.4g}"
    )
