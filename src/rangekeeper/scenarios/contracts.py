"""Immutable market method contracts used without importing numerical execution."""

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
import math


@dataclass(frozen=True, slots=True)
class Parameter:
    default: float | None
    lower: float | None = None
    upper: float | None = None
    lower_closed: bool = True
    upper_closed: bool = True

    def check(self, name, value):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"non-finite scenario parameter: {name}")
        if self.lower is not None and (
            value < self.lower or value == self.lower and not self.lower_closed
        ):
            raise ValueError(f"scenario parameter below its bound: {name}")
        if self.upper is not None and (
            value > self.upper or value == self.upper and not self.upper_closed
        ):
            raise ValueError(f"scenario parameter above its bound: {name}")


DIRECT = MappingProxyType(
    dict(
        initial_value=Parameter(0.05, 0, lower_closed=False),
        growth_rate=Parameter(0.02),
        cap_rate=Parameter(0.05, 0, lower_closed=False),
        volatility_per_period=Parameter(0.03, 0),
        autoregression=Parameter(0.2),
        mean_reversion=Parameter(0.1),
        space_period=Parameter(10.0, 0, lower_closed=False),
        space_phase=Parameter(0.0),
        space_amplitude=Parameter(0.1),
        space_asymmetry=Parameter(0.0, -1, 1, False, False),
        asset_period=Parameter(10.0, 0, lower_closed=False),
        asset_phase=Parameter(2.0),
        asset_amplitude=Parameter(0.005),
        asset_asymmetry=Parameter(0.0, -1, 1, False, False),
        noise_lower=Parameter(-0.02),
        noise_upper=Parameter(0.02),
        shock_likelihood=Parameter(0.02, 0, 1),
        shock_dissipation=Parameter(0.5, 0, 1),
        shock_impact=Parameter(-0.2),
    )
)
ESTIMATED = MappingProxyType(
    {
        **{
            name: rule
            for name, rule in DIRECT.items()
            if name not in {"space_phase", "asset_phase", "asset_period"}
        },
        "space_phase_proportion": Parameter(0.0),
        "asset_phase_difference": Parameter(0.1),
        "asset_period_difference": Parameter(0.0),
    }
)
INDEPENDENT = MappingProxyType(
    {
        "space_factor": Parameter(None),
        "asset_cap": Parameter(None, 0, lower_closed=False),
    }
)
_OUTPUTS = MappingProxyType(
    {
        name: int(name in {"implied_reversion_cap_rates", "returns"})
        for name in (
            "trend",
            "autoregressive_returns",
            "cumulative_volatility",
            "space_cycle",
            "asset_cycle",
            "space_market",
            "asset_market",
            "asset_true_value",
            "space_market_price_factors",
            "noise_effect",
            "shock_effect",
            "noisy_value",
            "historical_value",
            "implied_reversion_cap_rates",
            "returns",
        )
    }
)


@dataclass(frozen=True, slots=True)
class Method:
    parameters: Mapping[str, Parameter]
    scalar_parameters: bool
    arrays: tuple[str, ...]
    output_offsets: Mapping[str, int]


_METHODS = MappingProxyType(
    {
        "market": Method(DIRECT, True, ("innovations", "noise", "events"), _OUTPUTS),
        "market.estimates": Method(
            ESTIMATED, True, ("innovations", "noise", "events"), _OUTPUTS
        ),
        "market.independent": Method(
            INDEPENDENT,
            False,
            tuple(INDEPENDENT),
            MappingProxyType(
                {
                    "space_market_price_factors": 0,
                    "asset_market": 0,
                    "historical_value": 0,
                }
            ),
        ),
    }
)


def method(name: str) -> Method:
    try:
        return _METHODS[name]
    except (KeyError, TypeError) as error:
        raise ValueError(f"unsupported scenario method: {name}") from error


def check_values(name, values):
    """Check known scalar parameters; omitted distributed parameters stay unassessed."""
    contract = method(name)
    for key, value in values.items():
        contract.parameters[key].check(key, value)
    if {"noise_lower", "noise_upper"} <= values.keys() and values[
        "noise_lower"
    ] > values["noise_upper"]:
        raise ValueError("noise lower bound exceeds upper bound")
    if (
        name == "market.estimates"
        and {"space_period", "asset_period_difference"} <= values.keys()
        and values["space_period"] + values["asset_period_difference"] <= 0
    ):
        raise ValueError("estimated asset period must be positive")


def check_inputs(name, parameters, arrays):
    """Check realized input support after distributed parameters have known values."""
    contract = method(name)
    check_values(name, parameters)
    if not contract.scalar_parameters:
        for key, values in arrays.items():
            for value in values:
                contract.parameters[key].check(key, value)
        return
    if any(
        not parameters["noise_lower"] <= value <= parameters["noise_upper"]
        for value in arrays["noise"]
    ):
        raise ValueError("noise draws outside declared support")
    if any(not 0 <= value <= 1 for value in arrays["events"]):
        raise ValueError("shock event draws must be in [0, 1]")
    if parameters["volatility_per_period"] == 0 and any(arrays["innovations"]):
        raise ValueError("zero volatility requires zero innovation draws")
