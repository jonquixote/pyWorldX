"""Unit tests for ClimateSector (100% line+branch coverage)."""
from __future__ import annotations


from pyworldx.core.quantities import Quantity
from pyworldx.sectors.base import RunContext
from pyworldx.sectors.climate import (
    ClimateSector,
    _K_AERO, _TAU_AERO, _HEAT_SHOCK_THRESHOLD, _HEAT_SHOCK_CRITICAL,
)


def _ctx() -> RunContext:
    return RunContext(master_dt=1.0, t_start=0.0, t_end=200.0, shared_state={})


def _inputs(
    io: float = 7.9e11,
    pollution_gen: float = 0.0,
    supply_mult: float = 1.0,
    ghg_rf: float | None = None,
) -> dict[str, Quantity]:
    d = {
        "industrial_output": Quantity(io, "industrial_output_units"),
        "pollution_generation": Quantity(pollution_gen, "pollution_units"),
        "supply_multiplier_climate": Quantity(supply_mult, "dimensionless"),
    }
    if ghg_rf is not None:
        d["ghg_radiative_forcing"] = Quantity(ghg_rf, "W_per_m2")
    return d


class TestClimateSector:
    def test_init_stocks(self) -> None:
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        assert "T" in stocks
        assert "A" in stocks
        assert stocks["T"].magnitude == 0.0
        assert stocks["A"].magnitude == 1.0

    def test_aerosol_quasi_equilibrium_formula(self) -> None:
        """A = K_AERO * io * tau_aero exactly."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        io_val = 7.9e11
        out = s.compute(0.0, stocks, _inputs(io=io_val), ctx)
        expected = _K_AERO * io_val * _TAU_AERO
        assert abs(out["aerosol_index"].magnitude - expected) < 1e-20

    def test_da_always_zero(self) -> None:
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["d_A"].magnitude == 0.0

    def test_ghg_rf_from_input_preferred(self) -> None:
        """When ghg_radiative_forcing is in inputs, use it instead of CO2-proxy."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out_proxy = s.compute(0.0, stocks, _inputs(pollution_gen=0.0), ctx)
        out_direct = s.compute(0.0, stocks, _inputs(ghg_rf=5.0), ctx)
        # Direct GHG RF=5.0 >> proxy (log CO2 ≈ 0 with zero emissions)
        assert out_direct["d_T"].magnitude > out_proxy["d_T"].magnitude

    def test_radiative_forcing_ghg_in_output(self) -> None:
        """rf_ghg from direct input appears in output as radiative_forcing_ghg."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(ghg_rf=3.7), ctx)
        assert abs(out["radiative_forcing_ghg"].magnitude - 3.7) < 1e-10

    def test_co2_proxy_fallback(self) -> None:
        """With high pollution_gen and no direct GHG input, rf_ghg > 0."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(pollution_gen=1.0e14), ctx)
        assert out["radiative_forcing_ghg"].magnitude > 0.0

    def test_heat_shock_below_threshold(self) -> None:
        """T < threshold → heat_shock_multiplier = 1.0."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = {"T": Quantity(0.0, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["heat_shock_multiplier"].magnitude == 1.0

    def test_heat_shock_exactly_at_threshold(self) -> None:
        """T == threshold → heat_shock_multiplier = 1.0."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = {"T": Quantity(_HEAT_SHOCK_THRESHOLD, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["heat_shock_multiplier"].magnitude == 1.0

    def test_heat_shock_between_threshold_and_critical(self) -> None:
        """T between threshold and critical → 0 < multiplier < 1."""
        s = ClimateSector()
        ctx = _ctx()
        mid_t = (_HEAT_SHOCK_THRESHOLD + _HEAT_SHOCK_CRITICAL) / 2.0
        stocks = {"T": Quantity(mid_t, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert 0.0 < out["heat_shock_multiplier"].magnitude < 1.0

    def test_heat_shock_at_critical(self) -> None:
        """T >= critical → heat_shock_multiplier = 0.0."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = {"T": Quantity(_HEAT_SHOCK_CRITICAL, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["heat_shock_multiplier"].magnitude == 0.0

    def test_heat_shock_above_critical(self) -> None:
        """T >> critical → heat_shock_multiplier = 0.0."""
        s = ClimateSector()
        ctx = _ctx()
        stocks = {"T": Quantity(10.0, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out = s.compute(0.0, stocks, _inputs(), ctx)
        assert out["heat_shock_multiplier"].magnitude == 0.0

    def test_energy_demand_proportional_to_abs_T(self) -> None:
        s = ClimateSector()
        ctx = _ctx()
        stocks_lo = {"T": Quantity(1.0, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        stocks_hi = {"T": Quantity(3.0, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out_lo = s.compute(0.0, stocks_lo, _inputs(), ctx)
        out_hi = s.compute(0.0, stocks_hi, _inputs(), ctx)
        assert abs(out_hi["energy_demand_climate"].magnitude / out_lo["energy_demand_climate"].magnitude - 3.0) < 0.01

    def test_dt_positive_with_strong_ghg(self) -> None:
        s = ClimateSector()
        ctx = _ctx()
        stocks = {"T": Quantity(0.0, "deg_C_anomaly"), "A": Quantity(1.0, "dimensionless")}
        out = s.compute(0.0, stocks, _inputs(ghg_rf=5.0, io=0.0), ctx)
        assert out["d_T"].magnitude > 0.0

    def test_all_outputs_are_quantities(self) -> None:
        s = ClimateSector()
        ctx = _ctx()
        stocks = s.init_stocks(ctx)
        out = s.compute(0.0, stocks, _inputs(), ctx)
        for k, v in out.items():
            assert isinstance(v, Quantity), f"{k} is not a Quantity"

    def test_declares_reads(self) -> None:
        s = ClimateSector()
        reads = s.declares_reads()
        assert "ghg_radiative_forcing" in reads
        assert "supply_multiplier_climate" in reads

    def test_declares_writes(self) -> None:
        s = ClimateSector()
        writes = s.declares_writes()
        assert "heat_shock_multiplier" in writes
        assert "energy_demand_climate" in writes
        assert "temperature_anomaly" in writes
