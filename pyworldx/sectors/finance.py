"""FinanceSector — Liquid Funds + 3 Debt Pool ODEs (Phase 1 Task 2).

Merges WILIAM Cobb-Douglas production with endogenous financial dynamics.
Implements the physical → financial linkage from Q05, Q10, Q53.

Stocks:
  - L (Liquid Funds): dL/dt = Profit + LoanTaking + MoneyPrinting
                              - Investments - Interest - OperationCosts - TNDS_AES
  - D_g (General Debt): dD_g/dt = LoanTakingRate - D_g / 30yr
  - D_s (Speculative Debt): crisis-response borrowing, same amortization
  - D_p (Pension Debt): aging liabilities accumulation

Key mechanisms:
  - 150% Debt-to-GDP ceiling with gradual governance multiplier
  - Capital collateralization: V_c = Stock × Price for IC, SC, AL
  - Physical monetization: Revenue = Q × p, Profit = Revenue - Cost
  - Military drain on Liquid Funds (fixes WILIAM bug where military
    is computed but not subtracted)
  - Maintenance Gap linkage: L depletion → MaintenanceRatio < 1.0
    → φ(MaintenanceRatio) spikes → capital depreciates faster

Loop avoidance (Q53): IC, L, D are all Stocks (Integrators), not
auxiliary variables. The levels buffer equations, breaking
simultaneous algebraic dependency (State-Gating).
"""

from __future__ import annotations

from pyworldx.core.metadata import EquationSource, ValidationStatus, WORLD7Alignment
from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext


# ── Constants ─────────────────────────────────────────────────────────

_L0 = 1.0e11          # initial Liquid Funds (1900)
_DG0 = 0.0             # initial General Debt
_DS0 = 0.0             # initial Speculative Debt
_DP0 = 0.0             # initial Pension Debt
_DEBT_REPAYMENT = 30.0  # debt amortization time (years)
_INTEREST_RATE = 0.03   # annual interest rate on total debt
_DEBT_GDP_CEILING = 1.5  # 150% Debt-to-GDP ceiling
_MILITARY_FRACTION = 0.02    # fraction of output to military
_INVESTMENT_FRACTION = 0.25  # fraction of profit reinvested into capital
_MAINTENANCE_COST_FRACTION = 0.1  # fraction of IC value for maintenance
_LABOR_COST_FRACTION = 0.15  # fraction of output as labor cost
_RESOURCE_COST_FRACTION = 0.05  # fraction of output as resource extraction cost


def governance_multiplier(debt_gdp_ratio: float) -> float:
    """Gradual gating function for debt ceiling (Q05).

    Returns loan availability multiplier (0.0-1.0).
    Loan availability decreases gradually as ratio approaches 1.5,
    not a sudden cliff. Fully blocked at ratio >= 1.5.

    Uses a smooth ramp from 1.0 (at ratio=0) to 0.0 (at ratio>=1.5):
      g(r) = max(0, 1 - (r / ceiling)^2)
    """
    if debt_gdp_ratio <= 0.0:
        return 1.0
    if debt_gdp_ratio >= _DEBT_GDP_CEILING:
        return 0.0
    ratio = debt_gdp_ratio / _DEBT_GDP_CEILING
    return max(0.0, 1.0 - ratio * ratio)


class FinanceSector:
    """Financial sector with Liquid Funds + 3 distinct Debt Pool ODEs.

    Merges WILIAM Cobb-Douglas production output with endogenous
    financial dynamics. Sub-stepped for stiff equation handling.

    Stocks: L, D_g, D_s, D_p
    Reads:  industrial_output, IC, SC, AL, POP
    Writes: liquid_funds, total_debt, debt_to_gdp, maintenance_ratio,
            loan_availability, revenue, profit, military_spending,
            collateral_value, financial_resilience
    """

    name = "finance"
    version = "1.0.0"
    timestep_hint: float | None = None  # single-rate for now

    def __init__(
        self,
        initial_liquid_funds: float = _L0,
        interest_rate: float = _INTEREST_RATE,
        debt_repayment_time: float = _DEBT_REPAYMENT,
        military_fraction: float = _MILITARY_FRACTION,
        investment_fraction: float = _INVESTMENT_FRACTION,
        leverage_fraction: float = 0.0,
    ) -> None:
        self.initial_liquid_funds = initial_liquid_funds
        self.interest_rate = interest_rate
        self.debt_repayment_time = debt_repayment_time
        self.military_fraction = military_fraction
        self.investment_fraction = investment_fraction
        self.leverage_fraction = leverage_fraction

    def init_stocks(self, ctx: RunContext) -> dict[str, Quantity]:
        return {
            "L": Quantity(self.initial_liquid_funds, "capital_units"),
            "D_g": Quantity(_DG0, "capital_units"),
            "D_s": Quantity(_DS0, "capital_units"),
            "D_p": Quantity(_DP0, "capital_units"),
        }

    def compute(
        self,
        t: float,
        stocks: dict[str, Quantity],
        inputs: dict[str, Quantity],
        ctx: RunContext,
    ) -> dict[str, Quantity]:
        L = stocks["L"].magnitude
        D_g = stocks["D_g"].magnitude
        D_s = stocks["D_s"].magnitude
        D_p = stocks["D_p"].magnitude

        # Read from shared state
        io = inputs.get(
            "industrial_output", Quantity(7.9e11, "industrial_output_units")
        ).magnitude
        ic = inputs.get("IC", Quantity(2.1e11, "capital_units")).magnitude
        sc = inputs.get("SC", Quantity(1.44e11, "capital_units")).magnitude
        al = inputs.get("AL", Quantity(0.9e9, "hectares")).magnitude
        pop = inputs.get("POP", Quantity(1.65e9, "persons")).magnitude

        # ── Physical → Financial Linkage (Q53) ────────────────────────
        # Revenue = Q × p (endogenous market price, simplified as IO)
        revenue = io

        # Cost = μ×K (maintenance) + σ×R (resources) + ω×L (labor)
        maintenance_cost = _MAINTENANCE_COST_FRACTION * ic
        resource_cost = _RESOURCE_COST_FRACTION * io
        labor_cost = _LABOR_COST_FRACTION * io
        total_cost = maintenance_cost + resource_cost + labor_cost

        # Profit = Revenue - Cost → dL/dt inflow
        profit = max(revenue - total_cost, 0.0)

        # ── Military drain (fixes WILIAM bug) ─────────────────────────
        military_spending = self.military_fraction * io

        # ── Capital Collateralization ─────────────────────────────────
        # V_c = Stock × Price (simplified: price = 1 unit of output per capital)
        collateral_ic = ic * 1.0
        collateral_sc = sc * 1.0
        collateral_al = al * 0.001  # land has lower price per unit
        collateral_value = collateral_ic + collateral_sc + collateral_al

        # ── Debt Dynamics ─────────────────────────────────────────────
        total_debt = D_g + D_s + D_p
        gdp = max(io, 1.0)
        debt_to_gdp = total_debt / gdp

        # Interest payments = total_debt × interest_rate
        interest_payments = total_debt * self.interest_rate

        # ── Investment computation for leverage term ──────────────────
        # Required early for loan_taking_rate that includes leverage term
        investments = profit * self.investment_fraction

        # Loan availability gated by governance multiplier
        gov_mult = governance_multiplier(debt_to_gdp)
        loan_deficit = max(-L, 0.0)  # only borrow when L < 0 or threatened
        loan_taking_rate = (loan_deficit + investments * self.leverage_fraction) * gov_mult

        # ── Financial Resilience ──────────────────────────────────────
        # When ΣV_c < Debt → investment rate → 0 (Minsky Moment)
        financial_resilience = collateral_value / max(total_debt, 1.0)
        # investment_rate_mult reserved for Phase 2 engine wiring:
        # min(financial_resilience, 1.0) when total_debt > 0 else 1.0

        # ── Maintenance Ratio ─────────────────────────────────────────
        # Actual maintenance depends on available Liquid Funds
        required_maintenance = maintenance_cost
        actual_maintenance = min(L * 0.3, required_maintenance)  # can allocate up to 30% of L
        maintenance_ratio = actual_maintenance / max(required_maintenance, 1.0)
        maintenance_ratio = max(0.0, min(maintenance_ratio, 2.0))

        # ── TNDS: Total Non-Discretionary Spending (AES + education + damages)
        tnds_aes = inputs.get(
            "tnds_aes", Quantity(0.0, "capital_units")
        ).magnitude
        tnds_education = inputs.get(
            "education_tnds", Quantity(0.0, "capital_units")
        ).magnitude
        tnds_damages = inputs.get(
            "damages_tnds", Quantity(0.0, "capital_units")
        ).magnitude
        total_tnds = tnds_aes + tnds_education + tnds_damages

        # ── Liquid Funds ODE ──────────────────────────────────────────
        # dL/dt = Profit + Loans - Investments - Interest - Military - TNDS
        dL = (profit
              + loan_taking_rate
              - investments
              - interest_payments
              - military_spending
              - total_tnds)

        # ── Debt Pool ODEs ────────────────────────────────────────────
        # General debt: new loans - amortization
        dD_g = loan_taking_rate - D_g / max(self.debt_repayment_time, 1.0)

        # Speculative debt: activated during crises (debt_to_gdp > 1.0)
        spec_trigger = max(debt_to_gdp - 1.0, 0.0)
        dD_s = spec_trigger * io * 0.01 - D_s / max(self.debt_repayment_time, 1.0)

        # Pension debt: grows with aging population (simplified)
        pension_rate = max(pop * 0.001 - D_p * 0.01, 0.0)
        dD_p = pension_rate - D_p / max(self.debt_repayment_time * 2, 1.0)

        return {
            "d_L": Quantity(dL, "capital_units"),
            "d_D_g": Quantity(dD_g, "capital_units"),
            "d_D_s": Quantity(dD_s, "capital_units"),
            "d_D_p": Quantity(dD_p, "capital_units"),
            "liquid_funds": Quantity(L, "capital_units"),
            "total_debt": Quantity(total_debt, "capital_units"),
            "debt_to_gdp": Quantity(debt_to_gdp, "dimensionless"),
            "maintenance_ratio": Quantity(maintenance_ratio, "dimensionless"),
            "loan_availability": Quantity(gov_mult, "dimensionless"),
            "revenue": Quantity(revenue, "industrial_output_units"),
            "profit": Quantity(profit, "capital_units"),
            "military_spending": Quantity(military_spending, "capital_units"),
            "collateral_value": Quantity(collateral_value, "capital_units"),
            "financial_resilience": Quantity(
                financial_resilience, "dimensionless"
            ),
        }

    def declares_reads(self) -> list[str]:
        return [
            "industrial_output",
            "IC",
            "SC",
            "AL",
            "POP",
            "tnds_aes",
            "education_tnds",
            "damages_tnds",
        ]

    def declares_writes(self) -> list[str]:
        return [
            "L",
            "D_g",
            "D_s",
            "D_p",
            "liquid_funds",
            "total_debt",
            "debt_to_gdp",
            "maintenance_ratio",
            "loan_availability",
            "revenue",
            "profit",
            "military_spending",
            "collateral_value",
            "financial_resilience",
        ]

    def algebraic_loop_hints(self) -> list[dict[str, object]]:
        return []

    def metadata(self) -> dict[str, object]:
        return {
            "validation_status": ValidationStatus.EXPERIMENTAL,
            "equation_source": EquationSource.ADAPTER_DERIVED,
            "world7_alignment": WORLD7Alignment.APPROXIMATE,
            "approximations": [
                "Simplified revenue = IO (endogenous pricing deferred)",
                "Fixed cost fractions (maintenance, resources, labor)",
                "Collateral pricing simplified (price = 1.0)",
                "Pension liability simplified (population-based)",
            ],
            "free_parameters": [
                "initial_liquid_funds",
                "interest_rate",
                "debt_repayment_time",
                "military_fraction",
            ],
            "conservation_groups": [],
            "observables": [
                "liquid_funds",
                "total_debt",
                "debt_to_gdp",
                "maintenance_ratio",
                "financial_resilience",
            ],
            "unit_notes": "capital_units, dimensionless ratios",
        }
