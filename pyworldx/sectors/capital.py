"""World3-03 Capital sector with Cobb-Douglas production function.

Calibrated to wrld3-03.mdl (Vensim, September 29 2005).
Phase 2 upgrade: Cobb-Douglas production (Q81, Q64).

Stocks: IC (industrial capital), SC (service capital), LUFD (delayed labor utilization fraction)
Flows:  IC investment/depreciation, SC investment/depreciation, LUFD delay smoothing

  IO   = A · K^α · R^β · H^(1-α-β) · CUF      (Cobb-Douglas, Q81)
  SO   = SC * CUF / SCOR
  FIOAI = 1 - FIOAA - FIOAS - FIOAC   (residual)

  where:
    K = IC (industrial capital stock)
    R = (1 - FCAOR)  — resource availability proxy
    H = human_capital_multiplier (0-1 index from HumanCapitalSector)
    α = 0.25  (physical capital elasticity)
    β = 0.20  (resource/energy elasticity)
    1-α-β = 0.55  (human capital / skilled labor elasticity)
    A = TFP constant, calibrated so IO(1900) = 6.65×10¹⁰

Labor subsector (Phase D):
  labor_force = (P2 + P3) * LFPF
  jobs = JPICU*IC + JPSCU*SC + JPHA*AL
  LUF = jobs / labor_force
  CUF = CUF_Table(LUFD)

Key W3-03 corrections:
  - ALIC1 = 14 years  ->  depreciation = 1/14
  - IO includes (1-FCAOR) resource cost feedback via Cobb-Douglas R input
  - FIOAS table corrected to W3-03 values
  - FIOAI is a residual, not a separate table
  - FIOAC (consumption fraction) via ISOPC table
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.table_functions import table_lookup


# ── Nonlinear depreciation multiplier ─────────────────────────────────

def depreciation_multiplier(maintenance_ratio: float) -> float:
    """φ(MaintenanceRatio) — nonlinear depreciation acceleration.

    DESIGN NOTE: The notebooks (q11, q54) specify the behavioral shape
    (flat at 1.0 when ratio >= 1.0, spikes to 2.0-4.0x below 1.0) but do
    NOT specify a precise formula. This quadratic function satisfies the
    boundary conditions: φ(1.0)=1.0, φ(0.0)=4.0, monotonic.

    φ = 1 + 3 × (1 - ratio)²
    """
    if maintenance_ratio >= 1.0:
        return 1.0
    if maintenance_ratio <= 0.0:
        return 4.0
    # Quadratic: φ = 1 + 3 × (1 - ratio)²
    return min(1.0 + 3.0 * (1.0 - maintenance_ratio) ** 2, 4.0)


# ── W3-03 canonical tables ────────────────────────────────────────────

# Fraction of IO to services: FIOAS1(SOPC/ISOPC)
# MDL: FIOAS1  X = SOPC/ISOPC ratio
_FIOAS_X = (0.0, 0.5, 1.0, 1.5, 2.0)
_FIOAS_Y = (0.3, 0.2, 0.1, 0.05, 0.0)

# Fraction of IO to consumption: FIOACV(IOPC/IOPC_DESIRED)
# MDL: FIOACV  (indicator autonomous consumption)
_FIOACV_X = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
_FIOACV_Y = (0.3, 0.32, 0.34, 0.36, 0.38, 0.43, 0.73, 0.77, 0.81, 0.82, 0.83)

# Jobs per industrial capital unit: JPICU(IOPC)
_JPICU_X = (50.0, 200.0, 350.0, 500.0, 650.0, 800.0)
_JPICU_Y = (0.00037, 0.00018, 0.00012, 9e-05, 7e-05, 6e-05)

# Jobs per service capital unit: JPSCU(SOPC)
_JPSCU_X = (50.0, 200.0, 350.0, 500.0, 650.0, 800.0)
_JPSCU_Y = (0.0011, 0.0006, 0.00035, 0.0002, 0.00015, 0.00015)

# Jobs per hectare: JPH(AIPH)
_JPH_X = (2.0, 6.0, 10.0, 14.0, 18.0, 22.0, 26.0, 30.0)
_JPH_Y = (2.0, 0.5, 0.4, 0.3, 0.27, 0.24, 0.2, 0.2)

# Capacity utilization fraction: CUF(LUFD)
_CUF_X = (1.0, 3.0, 5.0, 7.0, 9.0, 11.0)
_CUF_Y = (1.0, 0.9, 0.7, 0.3, 0.1, 0.1)


# ── W3-03 constants ───────────────────────────────────────────────────

_IC0 = 2.1e11       # initial industrial capital (1900)
_SC0 = 1.44e11      # initial service capital (1900)
_ICOR1 = 3.0        # industrial capital-output ratio (years) — kept for SO
_SCOR1 = 1.0        # service capital-output ratio (years)
_ALIC1 = 14.0       # average life of industrial capital (years)
_ALSC1 = 20.0       # average life of service capital (years)

# ── Cobb-Douglas production function parameters (Q81, Q64) ────────────
#
# Q = A · K^α · R^β · H^γ · CUF
#   α = 0.25  (physical capital elasticity)
#   β = 0.20  (resource/energy elasticity)
#   γ = 0.55  (human capital elasticity, = 1 - α - β)
#
# TFP calibration (A):
#   At 1900: K=2.1e11, R=(1-0.05)=0.95, H=0.3, CUF=1.0
#   A = 6.65e10 / (K^0.25 · R^0.20 · H^0.55 · 1.0)
#   A = 6.65e10 / (676.947 · 0.98979 · 0.51572 · 1.0)
#   A ≈ 1.924445e+08
_CD_ALPHA = 0.25     # physical capital elasticity
_CD_BETA = 0.20      # resource/energy elasticity
_CD_GAMMA = 0.55     # human capital elasticity (1 - α - β)
_CD_TFP = 1.924445e8  # total factor productivity, calibrated to IO(1900)=6.65e10
_ENERGY_INTENSITY_CAPITAL = 1.5  # energy_units demanded per industrial_output_unit

# Indicated service output per capita: ISOPC(IOPC)
# MDL: ISOPCT  X = IOPC, from 0 to 1600 step 200
_ISOPC_X = (0.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0, 1600.0)
_ISOPC_Y = (40.0, 300.0, 640.0, 1000.0, 1220.0, 1450.0, 1650.0, 1800.0, 2000.0)
_LFPF = 0.75        # labor force participation fraction
_LUFDT = 2.0        # labor utilization fraction delay time (years)
_IOPC0 = 40.3       # initial IOPC (1900): IO0 / POP0 = 6.65e10 / 1.65e9
_IET = 3.0          # income expectation averaging time (years)


class CapitalSector:
    """World3-03 Capital sector with Cobb-Douglas production (Q81).

    Production function: IO = A · K^α · R^β · H^γ · CUF
      K = IC, R = (1-FCAOR), H = human_capital_multiplier
      α=0.25, β=0.20, γ=0.55

    Stocks: IC (industrial capital), SC (service capital), LUFD
    Reads:  fcaor, POP, food_per_capita, service_output_per_capita,
            P2, P3, AL, aiph, human_capital_multiplier
    Writes: IC, SC, industrial_output, industrial_output_per_capita,
            service_output, service_output_per_capita,
            frac_io_to_industry, frac_io_to_services, frac_io_to_agriculture,
            frac_io_to_consumption, labor_force, capacity_utilization_fraction
    """

    name = "capital"
    version = "3.03-cd"
    timestep_hint: float | None = None

    # Parameters (W3-03)
    initial_ic: float = _IC0
    initial_sc: float = _SC0
    icor: float = _ICOR1
    scor: float = _SCOR1
    alic: float = _ALIC1
    alsc: float = _ALSC1
    resource_elasticity: float = _CD_BETA  # Cobb-Douglas β; mutable for scenarios

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "IC": Quantity(self.initial_ic, "capital_units"),
            "SC": Quantity(self.initial_sc, "capital_units"),
            "LUFD": Quantity(1.0, "dimensionless"),
            "IOPCD": Quantity(_IOPC0, "industrial_output_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        ic = stocks["IC"].magnitude
        sc = stocks["SC"].magnitude
        lufd = stocks["LUFD"].magnitude
        iopcd = stocks["IOPCD"].magnitude

        # Read core inputs
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude
        fcaor = inputs.get("fcaor", Quantity(0.05, "dimensionless")).magnitude
        fioaa = inputs.get(
            "frac_io_to_agriculture", Quantity(0.1, "dimensionless")
        ).magnitude
        maintenance_ratio = inputs.get(
            "maintenance_ratio", Quantity(1.0, "dimensionless")
        ).magnitude
        
        # Labor inputs
        p2 = inputs.get("P2", Quantity(7.0e8, "persons")).magnitude
        p3 = inputs.get("P3", Quantity(1.9e8, "persons")).magnitude
        al = inputs.get("AL", Quantity(0.9e9, "hectares")).magnitude
        aiph = inputs.get("aiph", Quantity(2.0, "agricultural_inputs_per_hectare")).magnitude

        # To evaluate tables properly during algebraic loop resolution (where IO isn't stable),
        # we try to use the last stable IOPC/SOPC from inputs or just use a fallback guess.
        iopc_raw = inputs.get("industrial_output_per_capita", Quantity(40.0, "industrial_output_units")).magnitude
        sopc_raw = inputs.get("service_output_per_capita", Quantity(87.0, "service_output_units")).magnitude

        # ── Labor Subsector ───────────────────────────────────────────
        labor_force = (p2 + p3) * _LFPF

        # SEIR labor force multiplier (reduces labor when disease is present)
        seir_labor_mult = inputs.get(
            "labor_force_multiplier", Quantity(1.0, "dimensionless")
        ).magnitude
        effective_labor = labor_force * seir_labor_mult

        pjis = ic * table_lookup(iopc_raw, _JPICU_X, _JPICU_Y)
        pjss = sc * table_lookup(sopc_raw, _JPSCU_X, _JPSCU_Y)
        pjas = al * table_lookup(aiph, _JPH_X, _JPH_Y)
        jobs = pjis + pjss + pjas

        luf = jobs / max(effective_labor, 1.0)
        cuf = table_lookup(lufd, _CUF_X, _CUF_Y)
        
        d_lufd = (luf - lufd) / max(_LUFDT, 1e-6)

        # ── Industrial output (Cobb-Douglas, Q81) ─────────────────────
        # IO = A · K^α · R^β · H^γ · CUF
        #   K = IC (industrial capital)
        #   R = (1 - FCAOR) — resource availability (0-1)
        #   H = human_capital_multiplier (0-1 index)
        h_raw = inputs.get(
            "human_capital_multiplier", Quantity(0.3, "dimensionless")
        ).magnitude

        # Guard against zero/negative inputs for fractional exponents
        k_input = max(ic, 1.0)
        r_input = max(1.0 - fcaor, 1e-6)
        h_input = max(h_raw, 1e-6)

        io = (
            _CD_TFP
            * k_input ** _CD_ALPHA
            * r_input ** self.resource_elasticity
            * h_input ** _CD_GAMMA
            * cuf
        )
        iopc = io / max(pop, 1.0)

        # ── Service output ────────────────────────────────────────────
        so = sc * cuf / self.scor
        sopc = so / max(pop, 1.0)

        # ── IO allocation fractions ───────────────────────────────────
        # FIOAA: read from shared state (computed by agriculture sector)

        # FIOAS: services allocation based on service adequacy
        # ISOPC is dynamic in W3-03: rises with IOPC (economic development)
        isopc = table_lookup(iopc, _ISOPC_X, _ISOPC_Y)
        sopc_ratio = sopc / max(isopc, 1.0)
        fioas = table_lookup(sopc_ratio, _FIOAS_X, _FIOAS_Y)

        # FIOAC: consumption allocation based on income level
        # W3-03: ratio is IOPC / IOPC_desired (smoothed expectation)
        iopc_ratio = iopc / max(iopcd, 1.0)
        fioac = table_lookup(iopc_ratio, _FIOACV_X, _FIOACV_Y)

        # IOPCD: smooth IOPC desired (income expectation)
        d_iopcd = (iopc - iopcd) / max(_IET, 1e-6)

        # FIOAI: industrial investment is the residual
        fioai = max(1.0 - fioaa - fioas - fioac, 0.0)

        # Energy supply constraint: scale new investments when supply is insufficient
        esf = inputs.get(
            "energy_supply_factor", Quantity(1.0, "dimensionless")
        ).magnitude
        esf = max(0.0, min(esf, 1.0))

        # Financial resilience: gate investment when balance sheets are stressed
        fin_res = inputs.get(
            "financial_resilience", Quantity(1.0, "dimensionless")
        ).magnitude
        fin_res = max(0.0, min(fin_res, 1.0))

        investment_gate = esf * fin_res

        # ── Energy sector IO draw (capital conservation) ──────────────
        # Subtract energy sector investments before allocating remaining IO
        fossil_inv = inputs.get(
            "fossil_sector_investment", Quantity(0.0, "capital_units")
        ).magnitude
        tech_inv = inputs.get(
            "tech_sector_investment", Quantity(0.0, "capital_units")
        ).magnitude
        sust_inv = inputs.get(
            "sust_sector_investment", Quantity(0.0, "capital_units")
        ).magnitude
        energy_sector_draw = fossil_inv + tech_inv + sust_inv
        io_for_capital = max(io - energy_sector_draw, 0.0)

        # ── Investment and depreciation flows ─────────────────────────
        ic_investment = io_for_capital * fioai * investment_gate
        sc_investment = io_for_capital * fioas * investment_gate
        phi = depreciation_multiplier(maintenance_ratio)
        ic_depreciation = (ic / self.alic) * phi
        sc_depreciation = (sc / self.alsc) * phi

        energy_demand_capital = io * _ENERGY_INTENSITY_CAPITAL

        return {
            "d_IC": Quantity(ic_investment - ic_depreciation, "capital_units"),
            "d_SC": Quantity(sc_investment - sc_depreciation, "capital_units"),
            "d_LUFD": Quantity(d_lufd, "dimensionless"),
            "d_IOPCD": Quantity(d_iopcd, "industrial_output_units"),
            "industrial_output": Quantity(io, "industrial_output_units"),
            "industrial_output_per_capita": Quantity(iopc, "industrial_output_units"),
            "service_output": Quantity(so, "service_output_units"),
            "service_output_per_capita": Quantity(sopc, "service_output_units"),
            "frac_io_to_industry": Quantity(fioai, "dimensionless"),
            "frac_io_to_services": Quantity(fioas, "dimensionless"),
            "frac_io_to_consumption": Quantity(fioac, "dimensionless"),
            "labor_force": Quantity(labor_force, "persons"),
            "capacity_utilization_fraction": Quantity(cuf, "dimensionless"),
            "energy_demand_capital": Quantity(energy_demand_capital, "energy_units"),
        }

    def declares_reads(self) -> list[str]:
        return [
            "fcaor",
            "POP",
            "P2",
            "P3",
            "AL",
            "aiph",
            "food_per_capita",
            "frac_io_to_agriculture",
            "industrial_output_per_capita",
            "service_output_per_capita",
            "maintenance_ratio",
            "human_capital_multiplier",
            "labor_force_multiplier",
            "energy_supply_factor",
            "financial_resilience",
            "fossil_sector_investment",
            "tech_sector_investment",
            "sust_sector_investment",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "IC",
            "SC",
            "LUFD",
            "IOPCD",
            "industrial_output",
            "industrial_output_per_capita",
            "service_output",
            "service_output_per_capita",
            "frac_io_to_industry",
            "frac_io_to_services",
            "frac_io_to_consumption",
            "labor_force",
            "capacity_utilization_fraction",
            "energy_demand_capital",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return [
            {
                "name": "capital_pollution_loop",
                "variables": [
                    "industrial_output",
                    "pollution_index",
                    "pollution_efficiency",
                ],
                "scope": "cross_sector",
                "solver": "fixed_point",
                "tol": 1e-10,
                "max_iter": 100,
            }
        ]

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EMPIRICALLY_ANCHORED,
            "equation_source": EquationSource.SYNTHESIZED_FROM_PRIMARY_LITERATURE,
            "world7_alignment": WORLD7Alignment.APPROXIMATE,
            "approximations": [
                "FIOAC table simplified normalization",
                "Cobb-Douglas IO = A·K^0.25·R^0.20·H^0.55·CUF (Q81)",
                "R proxy: (1-FCAOR) resource availability",
            ],
            "free_parameters": [
                "scor", "alic", "alsc", "maintenance_ratio",
                "_CD_TFP", "_CD_ALPHA", "_CD_BETA", "_CD_GAMMA",
            ],
            "conservation_groups": [],
            "observables": [
                "IC",
                "SC",
                "industrial_output",
                "industrial_output_per_capita",
                "service_output",
                "service_output_per_capita",
                "labor_force",
                "capacity_utilization_fraction",
            ],
            "unit_notes": "capital_units, industrial_output_units",
        }
