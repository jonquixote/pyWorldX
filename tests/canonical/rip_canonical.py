"""
Python model 'rip_canonical.py'
Translated using PySD
"""

from pathlib import Path

from pysd.py_backend.statefuls import Integ
from pysd import Component

__pysd_version__ = "3.14.0"

__data = {"scope": None, "time": lambda: 0}

_root = Path(__file__).parent


component = Component()

#######################################################################
#                          CONTROL VARIABLES                          #
#######################################################################

_control_vars = {
    "initial_time": lambda: 0,
    "final_time": lambda: 200,
    "time_step": lambda: 1,
    "saveper": lambda: time_step(),
}


def _init_outer_references(data):
    for key in data:
        __data[key] = data[key]


@component.add(name="Time")
def time():
    """
    Current time of the model.
    """
    return __data["time"]()


@component.add(name="INITIAL TIME", comp_type="Constant", comp_subtype="Normal")
def initial_time():
    """
    The initial time for the simulation.
    """
    return __data["time"].initial_time()


@component.add(name="FINAL TIME", comp_type="Constant", comp_subtype="Normal")
def final_time():
    """
    The final time for the simulation.
    """
    return __data["time"].final_time()


@component.add(name="TIME STEP", comp_type="Constant", comp_subtype="Normal")
def time_step():
    """
    The time step for the simulation.
    """
    return __data["time"].time_step()


@component.add(
    name="SAVEPER",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time_step": 1},
)
def saveper():
    """
    The save time step for the simulation.
    """
    return __data["time"].saveper()


#######################################################################
#                           MODEL VARIABLES                           #
#######################################################################


@component.add(name="k_ext", comp_type="Constant", comp_subtype="Normal")
def k_ext():
    return 0.01


@component.add(
    name="industrial_output",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={
        "a": 1,
        "beta": 2,
        "k": 1,
        "extraction_rate": 1,
        "pollution_efficiency": 1,
    },
)
def industrial_output():
    """
    IO = A * K^beta * extraction_rate^(1-beta) * pollution_efficiency
    """
    return (
        a() * k() ** beta() * extraction_rate() ** (1 - beta()) * pollution_efficiency()
    )


@component.add(name="alpha", comp_type="Constant", comp_subtype="Normal")
def alpha():
    return 0.2


@component.add(name="delta", comp_type="Constant", comp_subtype="Normal")
def delta():
    return 0.05


@component.add(name="A", comp_type="Constant", comp_subtype="Normal")
def a():
    return 1.0


@component.add(name="beta", comp_type="Constant", comp_subtype="Normal")
def beta():
    return 0.7


@component.add(
    name="pollution_fraction",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"p_1": 2, "p_half": 1},
)
def pollution_fraction():
    """
    Hill function: P / (P + P_half)
    """
    return p_1() / (p_1() + p_half())


@component.add(
    name="pollution_efficiency",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"gamma": 1, "pollution_fraction": 1},
)
def pollution_efficiency():
    """
    pollution_efficiency = 1 - gamma * pollution_fraction
    """
    return 1 - gamma() * pollution_fraction()


@component.add(name="mu", comp_type="Constant", comp_subtype="Normal")
def mu():
    return 0.1


@component.add(name="tau_p", comp_type="Constant", comp_subtype="Normal")
def tau_p():
    return 20


@component.add(name="P_half", comp_type="Constant", comp_subtype="Normal")
def p_half():
    return 500


@component.add(name="gamma", comp_type="Constant", comp_subtype="Normal")
def gamma():
    return 0.3


@component.add(
    name="extraction_rate",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"k_ext": 1, "r": 1, "industrial_output": 1, "pollution_fraction": 1},
)
def extraction_rate():
    """
    extraction_rate = k_ext * R * industrial_output * (1 - pollution_fraction)
    """
    return k_ext() * r() * industrial_output() * (1 - pollution_fraction())


@component.add(
    name="investment",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"alpha": 1, "industrial_output": 1},
)
def investment():
    """
    investment = alpha * industrial_output
    """
    return alpha() * industrial_output()


@component.add(
    name="depreciation",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"delta": 1, "k": 1},
)
def depreciation():
    """
    depreciation = delta * K
    """
    return delta() * k()


@component.add(
    name="pollution_inflow",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"mu": 1, "industrial_output": 1},
)
def pollution_inflow():
    """
    pollution_inflow = mu * industrial_output
    """
    return mu() * industrial_output()


@component.add(
    name="pollution_outflow",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"p_1": 1, "tau_p": 1},
)
def pollution_outflow():
    """
    pollution_outflow = P / tau_p
    """
    return p_1() / tau_p()


@component.add(
    name="R",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_r": 1},
    other_deps={"_integ_r": {"initial": {}, "step": {"extraction_rate": 1}}},
)
def r():
    """
    Non-renewable resource stock (resource_units)
    """
    return _integ_r()


_integ_r = Integ(lambda: -extraction_rate(), lambda: 1000, "_integ_r")


@component.add(
    name="K",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_k": 1},
    other_deps={
        "_integ_k": {"initial": {}, "step": {"investment": 1, "depreciation": 1}}
    },
)
def k():
    """
    Industrial capital stock (capital_units)
    """
    return _integ_k()


_integ_k = Integ(lambda: investment() - depreciation(), lambda: 100, "_integ_k")


@component.add(
    name="P",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_p_1": 1},
    other_deps={
        "_integ_p_1": {
            "initial": {},
            "step": {"pollution_inflow": 1, "pollution_outflow": 1},
        }
    },
)
def p_1():
    """
    Persistent pollution stock (pollution_units)
    """
    return _integ_p_1()


_integ_p_1 = Integ(
    lambda: pollution_inflow() - pollution_outflow(), lambda: 0, "_integ_p_1"
)
