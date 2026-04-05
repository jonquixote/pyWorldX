"""Canonical R-I-P test world sectors (Section 17.1).

Three minimal sectors implementing Resources (R), Industry (I), and
Pollution (P) with exact parameters from the spec.  No ontology, no
adapters, no data connectors — just the math.

Sector R: sub-stepped at 4:1 (timestep_hint=0.25)
Sector I: single-rate, coupled to P via algebraic loop
Sector P: single-rate, coupled to I via algebraic loop
"""

from __future__ import annotations

from pyworldx.core.quantities import (
    CAPITAL_UNITS,
    DIMENSIONLESS,
    INDUSTRIAL_OUTPUT_UNITS,
    POLLUTION_UNITS,
    RESOURCE_UNITS,
    Quantity,
)
from pyworldx.sectors.base import RunContext


# ── Canonical Parameters (Section 17.1) ──────────────────────────────────

K_EXT = 0.01
ALPHA = 0.2
DELTA = 0.05
A = 1.0
BETA = 0.7
MU = 0.1
TAU_P = 20.0
P_HALF = 500.0
GAMMA = 0.3

R0 = 1000.0
K0 = 100.0
P0 = 0.0


# ── Sector R (Resources) — sub-stepped at 4:1 ───────────────────────────

class ResourceSector:
    """Non-renewable resource stock with extraction driven by industry.

    Stock:  R (resource units, initial=1000)
    Flow:   extraction_rate = k_ext * R * industrial_output * (1 - pollution_fraction)
    Reads:  industrial_output, pollution_fraction (frozen at master-step boundary)
    Writes: R, extraction_rate
    """

    name: str = "resources"
    version: str = "1.0.0"
    timestep_hint: float | None = 0.25  # 4:1 sub-stepping at master dt=1.0

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"R": Quantity(R0, RESOURCE_UNITS)}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        r = stocks["R"].magnitude
        io = inputs["industrial_output"].magnitude
        pf = inputs["pollution_fraction"].magnitude

        extraction_rate = K_EXT * r * io * (1.0 - pf)

        return {
            "d_R": Quantity(-extraction_rate, RESOURCE_UNITS),
            "extraction_rate": Quantity(extraction_rate, RESOURCE_UNITS),
        }

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []  # No intra-sector loops

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": "reference_matched",
            "equation_source": "canonical_test_world",
            "world7_alignment": "none",
            "approximations": [],
            "free_parameters": {"k_ext": K_EXT},
            "conservation_groups": ["nonrenewable_resource_mass"],
            "observables": ["extraction_rate"],
            "unit_notes": "resource_units",
            "preferred_substep_integrator": "rk4",
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output", "pollution_fraction"]

    def declares_writes(self) -> list[str]:
        return ["R", "extraction_rate"]


# ── Sector I (Industry) — single-rate ────────────────────────────────────

class IndustrySector:
    """Industrial capital with Cobb-Douglas production.

    Stock:      K (capital units, initial=100)
    Flows:      investment = alpha * industrial_output
                depreciation = delta * K
    Auxiliary:  industrial_output = A * K^beta * extraction_rate^(1-beta)
                    * capital_productivity_factor(pollution_efficiency)
                where: capital_productivity_factor(pe) = pe  (linear passthrough)
    Reads:      extraction_rate (from R), pollution_efficiency (from P — SIMULTANEOUS)
    Writes:     K, industrial_output
    """

    name: str = "industry"
    version: str = "1.0.0"
    timestep_hint: float | None = None  # runs at master step

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"K": Quantity(K0, CAPITAL_UNITS)}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        k = stocks["K"].magnitude
        er = inputs["extraction_rate"].magnitude
        pe = inputs["pollution_efficiency"].magnitude

        # Cobb-Douglas with capital_productivity_factor(pe) = pe
        industrial_output = A * (k ** BETA) * (er ** (1.0 - BETA)) * pe

        investment = ALPHA * industrial_output
        depreciation = DELTA * k
        d_k = investment - depreciation

        return {
            "d_K": Quantity(d_k, CAPITAL_UNITS),
            "industrial_output": Quantity(industrial_output, INDUSTRIAL_OUTPUT_UNITS),
        }

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [
            {
                "name": "industry_pollution_feedback",
                "variables": ["industrial_output", "pollution_efficiency"],
                "scope": "cross_sector",
                "solver": "fixed_point",
                "tol": 1e-10,
                "max_iter": 100,
            }
        ]

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": "reference_matched",
            "equation_source": "canonical_test_world",
            "world7_alignment": "none",
            "approximations": ["capital_productivity_factor is linear passthrough"],
            "free_parameters": {
                "alpha": ALPHA, "delta": DELTA, "A": A, "beta": BETA,
            },
            "conservation_groups": [],
            "observables": ["industrial_output"],
            "unit_notes": "capital_units, industrial_output_units",
        }

    def declares_reads(self) -> list[str]:
        return ["extraction_rate", "pollution_efficiency"]

    def declares_writes(self) -> list[str]:
        return ["K", "industrial_output"]


# ── Sector P (Pollution) — single-rate ───────────────────────────────────

class PollutionSector:
    """Persistent pollution with Hill function transition.

    Stock:      P (pollution units, initial=0)
    Flows:      pollution_inflow  = mu * industrial_output
                pollution_outflow = P / tau_p
    Auxiliary:  pollution_fraction   = P / (P + P_half)
                pollution_efficiency = 1 - gamma * pollution_fraction
    Reads:      industrial_output (from I — SIMULTANEOUS, I<->P loop)
    Writes:     P, pollution_fraction, pollution_efficiency
    """

    name: str = "pollution"
    version: str = "1.0.0"
    timestep_hint: float | None = None  # runs at master step

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {"P": Quantity(P0, POLLUTION_UNITS)}

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        p = stocks["P"].magnitude
        io = inputs["industrial_output"].magnitude

        pollution_inflow = MU * io
        pollution_outflow = p / TAU_P
        d_p = pollution_inflow - pollution_outflow

        pollution_fraction = p / (p + P_HALF) if (p + P_HALF) != 0.0 else 0.0
        pollution_efficiency = 1.0 - GAMMA * pollution_fraction

        return {
            "d_P": Quantity(d_p, POLLUTION_UNITS),
            "pollution_fraction": Quantity(pollution_fraction, DIMENSIONLESS),
            "pollution_efficiency": Quantity(pollution_efficiency, DIMENSIONLESS),
        }

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [
            {
                "name": "industry_pollution_feedback",
                "variables": ["industrial_output", "pollution_efficiency"],
                "scope": "cross_sector",
                "solver": "fixed_point",
                "tol": 1e-10,
                "max_iter": 100,
            }
        ]

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": "reference_matched",
            "equation_source": "canonical_test_world",
            "world7_alignment": "none",
            "approximations": [],
            "free_parameters": {
                "mu": MU, "tau_p": TAU_P, "P_half": P_HALF, "gamma": GAMMA,
            },
            "conservation_groups": [],
            "observables": ["pollution_fraction", "pollution_efficiency"],
            "unit_notes": "pollution_units",
        }

    def declares_reads(self) -> list[str]:
        return ["industrial_output"]

    def declares_writes(self) -> list[str]:
        return ["P", "pollution_fraction", "pollution_efficiency"]
