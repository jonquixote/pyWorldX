"""v2 Scenario Suite (Phase 1 Task 6).

6 scenarios (+ 1 Nature variant) that stress-test the v2 architecture.
Each scenario exercises specific feedback loops that don't exist in v1.

All scenarios are Scenario factories that return Scenario objects
with appropriate parameter_overrides and policy_events.

Note: Some scenarios describe mechanisms that require v2 engine features
not yet implemented (e.g., stock destruction, energy ceiling toggle,
phosphorus recycling control). These scenarios define the conceptual
intent and use parameter_overrides where possible. Full execution
requires the corresponding engine features.
"""

from __future__ import annotations

from typing import Any, Callable

from pyworldx.scenarios.scenario import PolicyEvent, PolicyShape, Scenario


# ── Scenario 1: Carrington Event ──────────────────────────────────────


def carrington_event(
    destruction_year: float = 2030.0,
    ic_destruction_fraction: float = 0.5,
) -> Scenario:
    """50% instantaneous IC destruction → financial liquidity trap.

    Tests: re-industrialization prohibited by debt overhang.

    Note: Direct IC stock destruction requires engine-level stock
    modification (not yet supported by PolicyEvent). For now, this
    scenario documents the intent. Full execution requires adding
    a stock-destruction mechanism to the engine.
    """
    # Relative time: destruction_year - 1900 (engine uses t=0→1900)
    t_event = float(destruction_year - 1900)
    return Scenario(
        name="carrington_event",
        description=(
            f"Carrington-class solar storm destroys "
            f"{ic_destruction_fraction * 100:.0f}% of Industrial Capital "
            f"instantaneously at year {destruction_year}. "
            "Tests financial liquidity trap and whether "
            "re-industrialization is possible under debt overhang."
        ),
        start_year=1900,
        end_year=2200,
        policy_events=[
            # Simulate EMP-induced grid destruction: 5-year energy supply disruption
            # (direct IC stock destruction requires engine v3 stock-mutation API)
            PolicyEvent(
                target="supply_multiplier_fossil",
                shape=PolicyShape.STEP,
                t_start=t_event,
                t_end=t_event + 5.0,
                magnitude=-0.7,
                description=(
                    f"70% fossil energy disruption from year {destruction_year} "
                    "for 5 years (EMP grid collapse proxy)"
                ),
            ),
            PolicyEvent(
                target="supply_multiplier_technology",
                shape=PolicyShape.STEP,
                t_start=t_event,
                t_end=t_event + 5.0,
                magnitude=-0.8,
                description="80% technology energy disruption (electronics-dependent systems destroyed)",
            ),
        ],
        tags=["v2", "carrington", "stock_destruction", "stress_test"],
    )


# ── Scenario 2: Minsky Moment ────────────────────────────────────────


def minsky_moment() -> Scenario:
    """Total Debt > ΣV_c → Investment Rate → 0, broad-front collapse.

    Tests: financial contagion via collateral value collapse.
    """
    return Scenario(
        name="minsky_moment",
        description=(
            "Orchestrated Minsky Moment: debt accumulation exceeds collateral "
            "value, triggering Investment Rate → 0 and broad-front collapse."
        ),
        start_year=1900,
        end_year=2200,
        parameter_overrides={
            # Accelerate debt accumulation
            "finance.interest_rate": 0.06,
        },
        tags=["v2", "minsky", "stress_test"],
    )


# ── Scenario 2b: Minsky Moment (Nature variant) ──────────────────────


def minsky_nature() -> Scenario:
    """ESP → 0, AES drains IC → BeROI negative → industrial starvation.

    Tests: ecosystem collapse forcing artificial ecosystem services.
    """
    return Scenario(
        name="minsky_nature",
        description=(
            "Nature-variant Minsky Moment: Ecosystem Services Proxy (ESP) "
            "drops to zero, forcing Industrial Capital to fund Artificial "
            "Ecosystem Services (AES). BeROI goes negative, starving the "
            "industrial sector."
        ),
        start_year=1900,
        end_year=2200,
        tags=["v2", "minsky_nature", "stress_test"],
    )


# ── Scenario 3: Absolute Decoupling (Null Hypothesis) ────────────────


def absolute_decoupling() -> Scenario:
    """Thermodynamic overrides prove decoupling requires violating physics.

    Per Q22, the full set of overrides is:
      1. β=0 in Cobb-Douglas (zero resource dependency) — parameter_override ✅
      2. FCAOR clamped to 0.05 (minimal resource cost) — parameter_override ✅
      3. 65% Energy Ceiling disabled (unlimited energy) — requires engine support
      4. TNDS for R&D set to 0 (free innovation) — requires engine support
      5. 100% Phosphorus Recycling Rate at zero energy cost — requires engine support

    Result: GDP grows without bound — proving that infinite decoupling
    is only possible by breaking thermodynamic constraints.

    Note: Overrides 3-5 require v2 engine features (CentralRegistrar toggle,
    TNDS parameter, phosphorus recycling control). Parameters 1-2 are
    implemented via parameter_overrides.
    """
    return Scenario(
        name="absolute_decoupling",
        description=(
            "Null hypothesis test: thermodynamic overrides that should "
            "produce infinite GDP growth, proving absolute decoupling "
            "requires violating physical laws. "
            "Implemented: β=0 (Cobb-Douglas), FCAOR clamped to 0.05. "
            "Pending: energy ceiling toggle, TNDS=0, phosphorus recycling."
        ),
        start_year=1900,
        end_year=2200,
        parameter_overrides={
            # Override 1: β=0 (zero resource dependency in Cobb-Douglas)
            "capital.resource_elasticity": 0.0,
            # Override 2: FCAOR clamped to 0.05
            "resources.fcaor_min": 0.05,
            "resources.fcaor_max": 0.05,
        },
        policy_events=[
            # Override 3 (partial): ramp fossil supply to near-zero by 2100 (t=200)
            # simulating "unlimited clean energy" by eliminating fossil constraints
            PolicyEvent(
                target="supply_multiplier_fossil",
                shape=PolicyShape.RAMP,
                t_start=0.0,
                t_end=200.0,
                rate=-1.0 / 200.0,
                description="Ramp fossil supply multiplier to 0 over 200 years (energy ceiling disabled proxy)",
            ),
            # Override 3 (complementary): ramp sustainable energy up
            PolicyEvent(
                target="supply_multiplier_sustainable",
                shape=PolicyShape.RAMP,
                t_start=0.0,
                t_end=200.0,
                rate=2.0 / 200.0,
                description="Ramp sustainable energy multiplier to 3× over 200 years (unlimited clean energy)",
            ),
        ],
        tags=["v2", "decoupling", "null_hypothesis"],
    )


# ── Scenario 4: AI Growth vs. Stagnation ─────────────────────────────


def ai_entropy_trap(
    ai_fraction: float = 0.06,
    ai_co2_intensity: float = 0.15,
    ai_ewaste: float = 3.5e-4,
) -> Scenario:
    """AI as entropy trap: scaling AI increases pollution despite efficiency.

    Tests: AI growth increases pollution peak by ~4% due to energy
    and e-waste intensity overcoming computational efficiency gains.
    """
    return Scenario(
        name="ai_entropy_trap",
        description=(
            "AI Growth scenario: 6% of IO allocated to AI by 2050. "
            "AI acts as entropy trap — energy and e-waste intensity "
            "overcome efficiency gains, increasing pollution peak by ~4%."
        ),
        start_year=1900,
        end_year=2200,
        parameter_overrides={
            "capital.frac_io_ai_2050": ai_fraction,
            "pollution.ai_co2_intensity": ai_co2_intensity,
            "pollution.ai_ewaste_intensity": ai_ewaste,
        },
        tags=["v2", "ai", "entropy_trap"],
    )


# ── Scenario 5: Giant Leap / Energiewende ─────────────────────────────


def energiewende(
    fossil_phaseout_start: float = 2020.0,
    fossil_phaseout_end: float = 2060.0,
    ndi_target: float = 0.36,
) -> Scenario:
    """90% fossil phase-out 2020-2060 with Implementation Delay + Material Drag.

    Tests: Non-Discretionary Investment rises from 24% to 36% as massive
    capital reallocation is required for energy transition infrastructure.

    Note: The time-varying fossil phaseout ramp requires a dynamic
    policy mechanism (PolicyShape.RAMP on a phaseout parameter).
    For now, the scenario documents the intent. Full execution
    requires a time-varying energy mix parameter.
    """
    return Scenario(
        name="energiewende",
        description=(
            f"Giant Leap / Energiewende: 90% fossil phase-out between "
            f"{fossil_phaseout_start} and {fossil_phaseout_end}. "
            "Tests Implementation Delay + Material Drag. "
            f"NDI rises to {ndi_target * 100:.0f}%."
        ),
        start_year=1900,
        end_year=2200,
        policy_events=[
            # Ramp fossil supply multiplier from 1.0 → 0.1 over the phaseout window
            PolicyEvent(
                target="supply_multiplier_fossil",
                shape=PolicyShape.RAMP,
                t_start=float(fossil_phaseout_start - 1900),
                t_end=float(fossil_phaseout_end - 1900),
                rate=-0.9 / (fossil_phaseout_end - fossil_phaseout_start),
                description=(
                    f"Fossil phaseout: 90% reduction in fossil supply "
                    f"between {fossil_phaseout_start} and {fossil_phaseout_end}"
                ),
            ),
            # Ramp sustainable supply multiplier to compensate
            PolicyEvent(
                target="supply_multiplier_sustainable",
                shape=PolicyShape.RAMP,
                t_start=float(fossil_phaseout_start - 1900),
                t_end=float(fossil_phaseout_end - 1900),
                rate=2.0 / (fossil_phaseout_end - fossil_phaseout_start),
                description=(
                    f"Renewable scale-up: 2× sustainable supply multiplier "
                    f"between {fossil_phaseout_start} and {fossil_phaseout_end}"
                ),
            ),
        ],
        tags=["v2", "energiewende", "transition"],
    )


# ── Scenario 6: Contagious Disintegration (Lifeboating) ──────────────


def lifeboating(
    fpc_threshold: float = 230.0,
    debt_gdp_threshold: float = 1.5,
) -> Scenario:
    """FPC < 230 or Debt/GDP > 150% → C_scale 1.0→0.0.

    Tests: contagion of collapse across regional network.
    C_scale drop severs trade linkages between regions.
    """
    return Scenario(
        name="lifeboating",
        description=(
            "Contagious Disintegration / Lifeboating: When FPC drops below "
            f"{fpc_threshold} or Debt/GDP exceeds {debt_gdp_threshold * 100:.0f}%, "
            "connectivity scale (C_scale) drops from 1.0 to 0.0, severing "
            "trade linkages and triggering contagion of collapse."
        ),
        start_year=1900,
        end_year=2200,
        parameter_overrides={
            "regional.fpc_lifeboating_threshold": fpc_threshold,
            "regional.debt_gdp_lifeboating_threshold": debt_gdp_threshold,
        },
        tags=["v2", "lifeboating", "contagion"],
    )


# ── Registry ──────────────────────────────────────────────────────────

V2_SCENARIOS: dict[str, Callable[..., Scenario]] = {
    "carrington_event": carrington_event,
    "minsky_moment": minsky_moment,
    "minsky_nature": minsky_nature,
    "absolute_decoupling": absolute_decoupling,
    "ai_entropy_trap": ai_entropy_trap,
    "energiewende": energiewende,
    "lifeboating": lifeboating,
}


def build_v2_scenario(name: str, **kwargs: Any) -> Scenario:
    """Build a v2 scenario by name.

    Raises KeyError if the scenario name is not recognized.
    """
    if name not in V2_SCENARIOS:
        available = ", ".join(sorted(V2_SCENARIOS.keys()))
        raise KeyError(f"Unknown v2 scenario '{name}'. Available: {available}")
    return V2_SCENARIOS[name](**kwargs)


def list_v2_scenarios() -> list[str]:
    """Return names of all available v2 scenarios."""
    return sorted(V2_SCENARIOS.keys())
