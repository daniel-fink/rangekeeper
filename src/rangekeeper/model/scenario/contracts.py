"""Immutable market method contracts used without importing numerical execution."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID
from rangekeeper.shared.validation import require, require_unique
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


def validate_plan(plan):
    """Check the complete passive plan against its market method contract."""
    from rangekeeper.model.distribution import Distribution

    contract = method(plan["method"])
    periods = plan["periods"]
    require(bool(periods), "scenario requires periods")
    require(
        all(p["start_inclusive"] < p["end_exclusive"] for p in periods),
        "invalid scenario period",
    )
    require(
        all(
            a["end_exclusive"] <= b["start_inclusive"]
            for a, b in zip(periods, periods[1:])
        ),
        "scenario periods overlap or are out of order",
    )
    params = plan["parameters"]
    require_unique(params, "name", "scenario parameter")
    expected = set(contract.parameters)
    require(
        {p["name"] for p in params} == expected, "scenario parameter inventory mismatch"
    )
    fixed = {}
    for p in params:
        q, d = p.get("quantity"), p.get("distribution")
        require(
            (q is None) != (d is None),
            "parameter requires exactly one quantity or distribution",
        )
        if q:
            fixed[p["name"]] = q["magnitude"]
            require(
                q["units"] == "dimensionless",
                "normalized market parameters require dimensionless units",
            )
        if d:
            Distribution.from_data(d).check()
            require(
                d["units"] == "dimensionless",
                "normalized distribution requires dimensionless units",
            )

    check_values(plan["method"], fixed)


def validate_realizations(provenance, scope):
    """Check captured input/output references and delayed observation declarations."""
    from rangekeeper.model.scope import resolve_reference, reference_key

    realizations = provenance.get("scenarios") or []
    require_unique(realizations, "id", "scenario realization")
    for item in realizations:
        validate_plan(item["plan"])
        for field in ("inputs", "outputs", "streams", "versions"):
            require_unique(item[field], "name", f"scenario {field}")
        if item.get("calculation") is not None:
            require_unique(
                item["calculation"]["versions"], "name", "calculation dependency"
            )
        _validate_contents(item, scope)
        tokens = [reference_key(a["target"]) for a in item["availability"]]
        require(len(tokens) == len(set(tokens)), "duplicate observation availability")
        for availability in item["availability"]:
            _, movement = resolve_reference(availability["target"], scope.targets)
            require(movement is not None, "scenario availability requires a Movement")
            if movement.get("date") is not None:
                require(
                    availability["available_at"] >= movement["date"],
                    "observation available before recorded date",
                )

        if item["outputs"]:
            availability = {
                reference_key(a["target"]): a["available_at"]
                for a in item["availability"]
            }
            for binding in item["outputs"]:
                delay = method(item["plan"]["method"]).output_offsets[binding["name"]]
                if delay:
                    value = scope.values[UUID(binding["value"])]
                    for index, movement in enumerate(value["flow"]["movements"]):
                        required = (
                            date.fromisoformat(
                                item["plan"]["periods"][index + delay]["end_exclusive"]
                            )
                            - timedelta(days=1)
                        ).isoformat()
                        actual = availability.get(
                            reference_key(dict(target=movement["id"]))
                        )
                        require(
                            actual is not None and actual >= required,
                            "forward-derived observation precedes its inputs",
                        )


def _validate_contents(item, scope):
    """Enforce complete captured shapes without importing generation algorithms."""
    from rangekeeper.model.scope import resolve_reference, reference_key

    plan = item["plan"]
    contract = method(plan["method"])
    arrays = set(contract.arrays)
    parameters = {p["name"]: p for p in plan["parameters"]}
    required = arrays | (set(parameters) if contract.scalar_parameters else set())
    require(
        {b["name"] for b in item["inputs"]} == required,
        "captured input inventory mismatch",
    )
    outputs = set(contract.output_offsets)
    require(
        not item["outputs"] or {b["name"] for b in item["outputs"]} == outputs,
        "captured output inventory mismatch",
    )
    availability = {
        reference_key(a["target"]): a["available_at"] for a in item["availability"]
    }
    expected_availability = set()
    captured, captured_arrays = {}, {}
    for field in ("inputs", "outputs"):
        for binding in item[field]:
            value, _ = resolve_reference(dict(target=binding["value"]), scope.targets)
            name = binding["name"]
            is_flow = field == "outputs" or name in arrays
            if is_flow:
                flow = value.get("flow")
                require(
                    flow is not None and flow["units"] == "dimensionless",
                    "scenario path must be a dimensionless Flow",
                )
                count = len(plan["periods"]) - (
                    contract.output_offsets[name] if field == "outputs" else 0
                )
                movements = flow["movements"]
                require(len(movements) == count, "scenario path length mismatch")
                for index, movement in enumerate(movements):
                    require(
                        movement.get("period") == plan["periods"][index]
                        and movement["key"] == f"p{index+1}",
                        "scenario path coordinate mismatch",
                    )
                    require(
                        movement.get("magnitude") is not None,
                        "captured scenario path cannot be unresolved",
                    )
                    token = reference_key(dict(target=movement["id"]))
                    expected_availability.add(token)
                    earliest = (
                        date.fromisoformat(plan["periods"][index]["end_exclusive"])
                        - timedelta(days=1)
                    ).isoformat()
                    require(
                        token in availability and availability[token] >= earliest,
                        "scenario observation precedes its period end",
                    )
                magnitudes = [m["magnitude"] for m in movements]
                if field == "inputs":
                    captured_arrays[name] = magnitudes
            else:
                quantity = value.get("quantity")
                require(
                    quantity is not None and quantity["units"] == "dimensionless",
                    "captured parameter must be a dimensionless Quantity",
                )
                magnitudes = [quantity["magnitude"]]
            if field == "inputs" and name in parameters:
                if contract.scalar_parameters:
                    captured[name] = magnitudes[0]
                parameter = parameters[name]
                if parameter.get("quantity") is not None:
                    require(
                        all(
                            x == parameter["quantity"]["magnitude"] for x in magnitudes
                        ),
                        "captured parameter differs from fixed plan input",
                    )
                else:
                    distribution = parameter["distribution"]
                    require(
                        all(
                            distribution["lower"] <= x <= distribution["upper"]
                            for x in magnitudes
                        ),
                        "captured parameter outside distribution support",
                    )
    check_inputs(plan["method"], captured, captured_arrays)
    require(
        set(availability) == expected_availability,
        "scenario availability inventory mismatch",
    )
